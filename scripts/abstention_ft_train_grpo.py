#!/usr/bin/env python3
"""GRPO abstention fine-tuning (companion to abstention_ft_train_{sft,dpo}.py).

Unlike DPO (offline, contrastive on fixed chosen/rejected pairs), GRPO is
on-policy: it samples a group of completions per prompt, scores each with a
*reward*, and does a group-relative policy-gradient update with a KL leash to
the reference. The reward here IS the consequence-asymmetry rubric:

    correct \\boxed{answer}     -> r_c   (default +1)
    \\boxed{UNSURE} abstention   -> r_a   (default  0)
    incorrect / mixed boxes     -> r_i   (default -25)
    no \\boxed{} at all          -> r_a (abstain, matches prompt contract) or
                                   r_i  (incorrect) via --unboxed

The (r_c, r_i, r_a) values are parsed per-row from the quantitative rubric text
embedded in the system prompt (so quant_m*, mix_*, and randomized quant_randi_*
rubrics all work); falls back to --reward_* if the prompt has no numeric rubric.

Because the escape region (unboxed "Final Answer: X") is *sampled and scored*
on-policy, GRPO does not suffer DPO's likelihood-displacement format collapse.
Defaults use the Dr. GRPO loss (loss_type=dr_grpo, scale_rewards=False) to avoid
GRPO's length-normalization bias, and mask_truncated_completions to not reward
runaway-length rollouts.

Supports google/gemma-4-E2B-it and Qwen/Qwen3.5-9B (qlora or full).

Example:
  python scripts/abstention_ft_train_grpo.py \
    --base_model google/gemma-4-E2B-it \
    --train_file data/abstention_ft/gemma4_e2b/dpo_n500_quant_m25_k512_p50.jsonl \
    --output_dir checkpoints/abstention_ft/grpo/gemma4_e2b_quant_m25_p50 \
    --peft_mode qlora --lora_r 16 --num_generations 8 \
    --max_completion_length 2048 --num_train_epochs 3 \
    --save_epochs 1 2 3 --report_to tensorboard wandb
"""
import argparse
import json
import os
import re
import sys

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from datasets import Dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import GRPOConfig, GRPOTrainer

from abstention_ft_train_sft import EpochSnapshotCallback, default_run_name

# Reuse the evaluator's exact boxed-answer extraction / UNSURE detection and the
# math grader, so the training reward matches how cells are scored downstream.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "evaluation"))
from grader import math_equal  # noqa: E402
from math_eval_cautious import extract_all_boxed, is_unsure  # noqa: E402

# Match both Gemma 4 (model.language_model.layers.N.…) and Qwen3.5 (model.layers.N.…).
TARGET_MODULES = r"model\.(language_model\.)?layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))"

# "scoring rubric: {r_c} for correct answer, {r_i} for incorrect answer, and {r_a} for abstaining"
_RUBRIC_RE = re.compile(
    r"rubric:\s*(-?\d+(?:\.\d+)?)\s*for correct answer,\s*"
    r"(-?\d+(?:\.\d+)?)\s*for incorrect answer, and\s*"
    r"(-?\d+(?:\.\d+)?)\s*for abstaining"
)


def _patch_selective_log_softmax(chunk_size: int = 1024) -> None:
    """Chunk-and-checkpoint trl's selective_log_softmax over the sequence dim.

    Gemma 4 has a 262k-token vocab; a full [batch, seq, vocab] log_softmax (and
    its fp32 temporary) over a group of completions OOMs even an 80GB A100. This
    processes the (seq, vocab) tensor in fixed seq-dim chunks inside
    torch.utils.checkpoint — functionally identical, far lower peak memory.
    """
    from trl.trainer import utils as _trl_utils
    from torch.utils.checkpoint import checkpoint

    def _chunked(logits, index):
        squeeze = index.ndim == logits.ndim - 1
        if squeeze:
            index = index.unsqueeze(-1)
        per_row = []
        for row_logits, row_index in zip(logits, index):
            seq_len = row_logits.shape[0]
            chunks = []
            for start in range(0, seq_len, chunk_size):
                end = min(start + chunk_size, seq_len)
                lg, ix = row_logits[start:end], row_index[start:end]

                def _compute(lg, ix):
                    return torch.nn.functional.log_softmax(lg, dim=-1).gather(-1, ix)

                if lg.requires_grad:
                    chunks.append(checkpoint(_compute, lg, ix, use_reentrant=False))
                else:
                    chunks.append(_compute(lg, ix))
            per_row.append(torch.cat(chunks, dim=0))
        out = torch.stack(per_row)
        return out.squeeze(-1) if squeeze else out

    _trl_utils.selective_log_softmax = _chunked
    try:
        from trl.trainer import grpo_trainer as _grpo
        if hasattr(_grpo, "selective_log_softmax"):
            _grpo.selective_log_softmax = _chunked
    except Exception:
        pass


def _patch_accelerate_fp32_conversion() -> None:
    """No-op accelerate's convert_outputs_to_fp32 (it would .float() the full
    [group, seq, 262k] logits under bf16 → ~tens of GiB). Our chunked
    log_softmax already upcasts only one small chunk at a time."""
    def _noop(model_forward):
        return model_forward

    from accelerate.utils import operations as _accel_ops
    from accelerate import accelerator as _accel_mod
    _accel_ops.convert_outputs_to_fp32 = _noop
    _accel_mod.convert_outputs_to_fp32 = _noop


_patch_selective_log_softmax()
_patch_accelerate_fp32_conversion()


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _prompt_messages(row):
    """Return the [system, user] message list for a build row.

    DPO files store this under `prompt`; SFT/SFT-box files store the full
    conversation under `messages` (drop the assistant target)."""
    if "prompt" in row and isinstance(row["prompt"], list):
        msgs = row["prompt"]
    elif "messages" in row:
        msgs = row["messages"]
    else:
        raise KeyError(f"row idx={row.get('idx')} has neither 'prompt' nor 'messages'")
    return [m for m in msgs if m.get("role") != "assistant"]


def _system_text(messages):
    for m in messages:
        if m.get("role") == "system":
            return m.get("content", "")
    return ""


def resolve_answers(train_file, answers_file):
    """idx -> ground-truth answer. Defaults to the sibling labeled_standard.jsonl,
    then falls back to omni_math_rule.jsonl at the repo root."""
    candidates = []
    if answers_file:
        candidates.append(answers_file)
    candidates.append(os.path.join(os.path.dirname(train_file), "labeled_standard.jsonl"))
    candidates.append(os.path.join(_REPO_ROOT, "omni_math_rule.jsonl"))
    for path in candidates:
        if path and os.path.exists(path):
            mapping = {}
            for r in read_jsonl(path):
                if "idx" in r and "answer" in r:
                    mapping[int(r["idx"])] = str(r["answer"])
            if mapping:
                print(f"[grpo] loaded {len(mapping)} answers from {path}")
                return mapping
    raise FileNotFoundError(
        "Could not resolve ground-truth answers. Pass --answers_file pointing to a "
        "jsonl with 'idx' and 'answer' fields (e.g. labeled_standard.jsonl)."
    )


def build_dataset(train_file, answers, default_rubric):
    rc_d, ri_d, ra_d = default_rubric
    rows = []
    missing = 0
    for row in read_jsonl(train_file):
        idx = int(row["idx"])
        # Prefer an inline ground-truth answer (GRPO build files carry one);
        # otherwise join by idx against the answers map (DPO/SFT build files).
        if row.get("answer") not in (None, ""):
            gt = str(row["answer"])
        elif idx in answers:
            gt = answers[idx]
        else:
            missing += 1
            continue
        messages = _prompt_messages(row)
        m = _RUBRIC_RE.search(_system_text(messages))
        if m:
            rc, ri, ra = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
        else:
            rc, ri, ra = rc_d, ri_d, ra_d
        rows.append({
            "prompt": messages,
            "answer": gt,
            "rc": rc, "ri": ri, "ra": ra,
            "idx": idx,
        })
    if missing:
        print(f"[grpo] WARNING: {missing} rows dropped (no answer for idx)")
    if not rows:
        raise ValueError("No usable training rows after joining answers.")
    print(f"[grpo] built {len(rows)} prompts")
    return Dataset.from_list(rows)


def _completion_text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):  # conversational: [{"role": "assistant", "content": ...}]
        return "".join(turn.get("content", "") for turn in c)
    return str(c)


def make_reward_fn(unboxed: str):
    """Reward = consequence-asymmetry rubric score of each completion, mirroring
    math_eval_cautious classification. `unboxed` in {abstain, incorrect}."""

    def reward(completions, answer, rc, ri, ra, **kwargs):
        out = []
        for comp, gt, r_c, r_i, r_a in zip(completions, answer, rc, ri, ra):
            text = _completion_text(comp)
            boxes = extract_all_boxed(text)
            if not boxes:
                out.append(r_a if unboxed == "abstain" else r_i)
                continue
            unsure_flags = [is_unsure(b) for b in boxes]
            if all(unsure_flags):
                out.append(r_a)            # genuine abstention
            elif any(unsure_flags):
                out.append(r_i)            # mixed UNSURE + real -> incorrect
            else:
                last = boxes[-1]
                try:
                    correct = math_equal(last, str(gt))
                except Exception:
                    correct = False
                out.append(r_c if correct else r_i)
        return out

    reward.__name__ = "rubric_reward"
    return reward


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model", required=True)
    p.add_argument("--train_file", required=True)
    p.add_argument("--output_dir", required=True)
    p.add_argument("--answers_file", default=None,
                   help="jsonl with idx+answer for grading. Default: sibling "
                        "labeled_standard.jsonl, then omni_math_rule.jsonl.")
    p.add_argument("--max_completion_length", type=int, default=2048)
    p.add_argument("--num_generations", type=int, default=8)
    p.add_argument("--learning_rate", type=float, default=1e-6)
    p.add_argument("--beta", type=float, default=0.04, help="KL coefficient to ref policy.")
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--top_p", type=float, default=1.0)
    p.add_argument("--top_k", type=int, default=None)
    p.add_argument("--loss_type", default="dr_grpo",
                   choices=["grpo", "dr_grpo", "bnpo"],
                   help="dr_grpo (default) removes GRPO's length-normalization bias.")
    p.add_argument("--scale_rewards", action="store_true",
                   help="Divide advantages by group std (GRPO default). Off by "
                        "default (Dr. GRPO) to avoid length/difficulty bias.")
    p.add_argument("--unboxed", choices=["abstain", "incorrect"], default="abstain",
                   help="How to score a completion with no \\boxed{} (default: "
                        "abstain, matching the prompt contract).")
    p.add_argument("--num_train_epochs", type=float, default=3)
    p.add_argument("--per_device_train_batch_size", type=int, default=8)
    p.add_argument("--gradient_accumulation_steps", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--logging_steps", type=int, default=1)
    p.add_argument("--peft_mode", choices=["qlora", "full"], default="qlora")
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--max_grad_norm", type=float, default=1.0)
    p.add_argument("--learning_rate_full", type=float, default=None)
    p.add_argument("--reward_correct", type=float, default=1.0)
    p.add_argument("--reward_incorrect", type=float, default=-25.0)
    p.add_argument("--reward_abstain", type=float, default=0.0)
    p.add_argument("--use_vllm", action="store_true",
                   help="Use vLLM for generation (much faster; colocate mode).")
    p.add_argument("--vllm_mode", default="colocate", choices=["colocate", "server"])
    p.add_argument("--vllm_gpu_memory_utilization", type=float, default=0.3)
    p.add_argument("--log_completions", action="store_true")
    p.add_argument("--save_epochs", type=float, nargs="+", default=None,
                   help="Save snapshots at each (fractional) epoch milestone into "
                        "{output_dir}/epoch-{tag}/, disabling default saves.")
    p.add_argument("--report_to", nargs="+", default=["tensorboard"])
    p.add_argument("--logging_dir", default=None)
    p.add_argument("--run_name", default=None)
    args = p.parse_args()

    if args.save_epochs:
        bad = [ep for ep in args.save_epochs if ep > args.num_train_epochs + 1e-9]
        if bad:
            raise ValueError(f"--save_epochs exceed --num_train_epochs: {bad}")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    tokenizer.padding_side = "left"  # required for batched generation

    # Only needed for DPO/SFT-source files (which lack inline answers). GRPO
    # build files carry `answer` per row, so a missing answers map is fine.
    try:
        answers = resolve_answers(args.train_file, args.answers_file)
    except FileNotFoundError as e:
        print(f"[grpo] no answer map ({e}); relying on inline 'answer' fields.")
        answers = {}
    train_dataset = build_dataset(
        args.train_file, answers,
        (args.reward_correct, args.reward_incorrect, args.reward_abstain),
    )

    if args.peft_mode == "qlora":
        model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            ),
            device_map="auto",
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
        )
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model)
        peft_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=TARGET_MODULES,
        )
    elif args.peft_mode == "full":
        model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        model.config.use_cache = False
        peft_config = None
    else:
        raise ValueError(f"Unknown --peft_mode: {args.peft_mode}")

    lr = args.learning_rate
    if args.peft_mode == "full" and args.learning_rate_full is not None:
        lr = args.learning_rate_full

    run_name = args.run_name or default_run_name(
        method="grpo",
        base_model=args.base_model,
        lr=lr,
        lora_r=args.lora_r if args.peft_mode == "qlora" else None,
        train_file=args.train_file,
    )
    os.environ.setdefault("WANDB_NAME", run_name)

    grpo_args = GRPOConfig(
        output_dir=args.output_dir,
        num_generations=args.num_generations,
        max_completion_length=args.max_completion_length,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        beta=args.beta,
        loss_type=args.loss_type,
        scale_rewards=args.scale_rewards,
        mask_truncated_completions=True,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=lr,
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.0,
        max_grad_norm=args.max_grad_norm,
        bf16=True,
        gradient_checkpointing=True,
        logging_steps=args.logging_steps,
        log_completions=args.log_completions,
        save_strategy="no" if args.save_epochs else "epoch",
        save_total_limit=None if args.save_epochs else 1,
        seed=args.seed,
        report_to=args.report_to,
        logging_dir=args.logging_dir or os.path.join(args.output_dir, "runs"),
        run_name=run_name,
        remove_unused_columns=False,
        chat_template_kwargs={"enable_thinking": True},
        use_vllm=args.use_vllm,
        vllm_mode=args.vllm_mode,
        vllm_gpu_memory_utilization=args.vllm_gpu_memory_utilization,
    )

    snapshot_cb = None
    if args.save_epochs:
        snapshot_cb = EpochSnapshotCallback(args.save_epochs, args.output_dir, tokenizer)

    trainer = GRPOTrainer(
        model=model,
        reward_funcs=make_reward_fn(args.unboxed),
        args=grpo_args,
        train_dataset=train_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
        callbacks=[snapshot_cb] if snapshot_cb else None,
    )
    if snapshot_cb is not None:
        snapshot_cb.attach(trainer)

    trainer.train()

    if not args.save_epochs:
        trainer.save_model(args.output_dir)
        tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
