#!/usr/bin/env python3
import argparse
import json
import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from datasets import Dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import DPOConfig, DPOTrainer

from abstention_ft_train_sft import EpochSnapshotCallback

TARGET_MODULES = r"model\.language_model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))"


def _patch_selective_log_softmax(chunk_size: int = 1024) -> None:
    """Chunk-and-checkpoint trl.trainer.utils.selective_log_softmax over the sequence dim.

    Why: Gemma 4 E2B has a 262k-token vocab, so on a long DPO example
    (~14k tokens, chosen+rejected stacked → batch 2) the raw logits tensor
    is ~15 GiB in bf16 (~30 GiB fp32). The stock impl loops over batch but
    keeps each full [seq, vocab] row materialized; `F.log_softmax` then
    upcasts to fp32 internally, allocating another ~15 GiB temporary, and
    autograd needs to keep the full pre-softmax logits alive for backward.
    Even an 80GB A100 OOMs.

    The fix processes the (seq, vocab) tensor in fixed-size seq-dim chunks
    inside `torch.utils.checkpoint` so (a) the fp32 log-softmax temporary
    is only one chunk's worth (~1 GiB at chunk_size=1024 for Gemma's
    vocab), and (b) backward recomputes per chunk instead of saving the
    full logits. Functionally identical to the stock implementation.
    """
    from trl.trainer import utils as _trl_utils
    from torch.utils.checkpoint import checkpoint

    def _chunked_selective_log_softmax(logits, index):
        squeeze = index.ndim == logits.ndim - 1
        if squeeze:
            index = index.unsqueeze(-1)

        per_row_outs = []
        for row_logits, row_index in zip(logits, index):
            seq_len = row_logits.shape[0]
            chunk_outs = []
            for start in range(0, seq_len, chunk_size):
                end = min(start + chunk_size, seq_len)
                lg_chunk = row_logits[start:end]
                ix_chunk = row_index[start:end]

                def _compute(lg, ix):
                    logps = torch.nn.functional.log_softmax(lg, dim=-1)
                    return logps.gather(dim=-1, index=ix)

                # use_reentrant=False is required for non-leaf inputs (logits has grad_fn)
                if lg_chunk.requires_grad:
                    out = checkpoint(_compute, lg_chunk, ix_chunk, use_reentrant=False)
                else:
                    out = _compute(lg_chunk, ix_chunk)
                chunk_outs.append(out)
            per_row_outs.append(torch.cat(chunk_outs, dim=0))
        per_token_logps = torch.stack(per_row_outs)
        if squeeze:
            per_token_logps = per_token_logps.squeeze(-1)
        return per_token_logps

    _trl_utils.selective_log_softmax = _chunked_selective_log_softmax
    # The DPOTrainer imports the symbol at module load time, so rebind there too.
    from trl.trainer import dpo_trainer as _dpo_trainer
    _dpo_trainer.selective_log_softmax = _chunked_selective_log_softmax


_patch_selective_log_softmax()


def _patch_accelerate_fp32_conversion() -> None:
    """Replace `accelerate.utils.convert_outputs_to_fp32` with a no-op.

    Why: with `bf16=True`, `Accelerator.prepare_model` wraps the model's
    forward in a function that calls `.float()` on every output tensor.
    For a Gemma DPO step (chosen+rejected stacked → batch 2 at ~14k
    tokens, vocab 262144) that means an unconditional
    2 × 14701 × 262144 × 4 B ≈ 30 GiB allocation just to upcast the
    logits — instant OOM even after every other memory fix. We don't
    need fp32 outputs: the chunked selective_log_softmax above upcasts
    only one small chunk at a time inside log_softmax.

    Two rebinds are needed because `accelerate/accelerator.py` does
    `from accelerate.utils import ..., convert_outputs_to_fp32, ...`
    at module load time, so patching only the source module is too late.
    """
    def _noop(model_forward):
        return model_forward

    from accelerate.utils import operations as _accel_ops
    from accelerate import accelerator as _accel_mod
    _accel_ops.convert_outputs_to_fp32 = _noop
    _accel_mod.convert_outputs_to_fp32 = _noop


_patch_accelerate_fp32_conversion()


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def render_prompt(tokenizer, messages):
    if tokenizer.chat_template is not None:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True,
        )
    return f"{messages[0]['content']}\n\nProblem:\n{messages[1]['content']}\n\nAnswer:\n"


def n_tokens(tokenizer, text):
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def load_dataset(path, tokenizer, max_len):
    rows = []
    for row in read_jsonl(path):
        prompt = render_prompt(tokenizer, row["prompt"])
        if n_tokens(tokenizer, prompt + row["chosen"]) > max_len or n_tokens(tokenizer, prompt + row["rejected"]) > max_len:
            raise ValueError(f"Overlength DPO example idx={row.get('idx')} > {max_len}")
        rows.append({"prompt": prompt, "chosen": row["chosen"], "rejected": row["rejected"]})
    return Dataset.from_list(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model", required=True)
    p.add_argument("--train_file", required=True)
    p.add_argument("--output_dir", required=True)
    p.add_argument("--max_seq_length", type=int, default=65536)
    p.add_argument("--learning_rate", type=float, default=5e-6)
    p.add_argument("--dpo_beta", type=float, default=0.1)
    p.add_argument("--num_train_epochs", type=float, default=3)
    p.add_argument("--per_device_train_batch_size", type=int, default=1)
    p.add_argument("--gradient_accumulation_steps", type=int, default=16)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--logging_steps", type=int, default=1)
    p.add_argument("--peft_mode", choices=["qlora", "full"], default="qlora")
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--max_grad_norm", type=float, default=1.0)
    p.add_argument("--learning_rate_full", type=float, default=None)
    p.add_argument(
        "--save_epochs",
        type=float,
        nargs="+",
        default=None,
        help="If set, save snapshots at each (fractional) epoch milestone into "
             "{output_dir}/epoch-{tag}/, disabling the default end-of-epoch saves. "
             "All values must be <= --num_train_epochs.",
    )
    p.add_argument(
        "--report_to",
        nargs="+",
        default=["tensorboard"],
        help="HF Trainer report_to integrations (tensorboard, wandb, none, ...).",
    )
    p.add_argument(
        "--logging_dir",
        default=None,
        help="Directory for TB event files. Default: {output_dir}/runs.",
    )
    args = p.parse_args()

    if args.save_epochs:
        bad = [ep for ep in args.save_epochs if ep > args.num_train_epochs + 1e-9]
        if bad:
            raise ValueError(
                f"--save_epochs values exceed --num_train_epochs={args.num_train_epochs}: {bad}"
            )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    tokenizer.padding_side = "right"
    train_dataset = load_dataset(args.train_file, tokenizer, args.max_seq_length)

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

    dpo_args = DPOConfig(
        output_dir=args.output_dir,
        beta=args.dpo_beta,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=1,
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
        save_strategy="no" if args.save_epochs else "epoch",
        save_total_limit=None if args.save_epochs else 1,
        seed=args.seed,
        report_to=args.report_to,
        logging_dir=args.logging_dir or os.path.join(args.output_dir, "runs"),
        remove_unused_columns=False,
        max_length=args.max_seq_length,
        truncation_mode="keep_start",
        precompute_ref_log_probs=True,
    )

    snapshot_cb = None
    if args.save_epochs:
        snapshot_cb = EpochSnapshotCallback(args.save_epochs, args.output_dir, tokenizer)

    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=dpo_args,
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
