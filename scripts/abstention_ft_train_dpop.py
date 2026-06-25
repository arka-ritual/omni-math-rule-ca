#!/usr/bin/env python3
"""DPO-Positive (DPOP) abstention fine-tuning — Smaug loss (Pal et al., 2402.13228).

Why DPOP instead of DPO here: our abstention preference pairs have a *low edit
distance* — chosen/rejected share the reasoning prefix and the `\\boxed{...}`
scaffold, differing only in the boxed payload (UNSURE vs. the real answer, or an
attempt vs. an abstention). That is exactly the regime where standard DPO drives
the log-prob of the *preferred* completion below the reference (the "wrong-way"
downstream-token gradient in Section 3 of the paper), producing the format
collapse we observed (models stop emitting `\\boxed{}` at all, especially at the
p≈50 balance point).

DPOP adds an inside-the-sigmoid penalty that is zero while the model keeps the
preferred completion at least as likely as the reference, and grows once it
slips below:

    L_DPOP = -E[ log σ( β ( (logπθ(y_w) - logπref(y_w))
                            - (logπθ(y_l) - logπref(y_l))
                            - λ · max(0, logπref(y_w) - logπθ(y_w)) ) ) ]

i.e. score_DPOP = Δ_DPO - λ · relu(-chosen_logratio), where
chosen_logratio = logπθ(y_w|x) - logπref(y_w|x).

TRL 1.5.0 does NOT implement DPOP (its loss_type list is sigmoid/hinge/ipo/
exo_pair/nca_pair/robust/bco_pair/sppo_hard/aot/aot_unpaired/apo_zero/apo_down/
discopop/sft/sigmoid_norm), so we subclass DPOTrainer and override the loss.
Reference log-probs are precomputed by TRL (precompute_ref_log_probs=True), so
the override never has to replicate the PEFT adapter-disable reference path.

Paper defaults: β=0.3, λ=50 (λ is robust across {5,50,500}). We keep β=0.1 by
default for apples-to-apples comparison with our existing DPO runs; pass
--dpo_beta 0.3 to match the paper exactly.

Supports google/gemma-4-E2B-it and Qwen/Qwen3.5-9B (qlora or full), and reuses
the same memory patches, data loader, snapshot callback, and run-naming as the
DPO trainer.

Example:
  python scripts/abstention_ft_train_dpop.py \\
    --base_model google/gemma-4-E2B-it \\
    --train_file data/abstention_ft/gemma4_e2b/dpo_n500_quant_m25_k512_p50.jsonl \\
    --output_dir checkpoints/abstention_ft/dpop/gemma4_e2b_quant_m25_p50 \\
    --peft_mode qlora --dpo_beta 0.3 --dpop_lambda 50 \\
    --num_train_epochs 3 --save_epochs 1 2 3 --report_to tensorboard wandb
"""
import argparse
import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
import torch.nn.functional as F
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import DPOConfig, DPOTrainer
import trl.trainer.dpo_trainer as _dpot

# Importing the DPO trainer module applies the memory patches (chunked
# selective_log_softmax + accelerate fp32 no-op) at import time, and gives us the
# shared data loader / target modules. abstention_ft_train_sft supplies the
# snapshot callback + run-name helper.
from abstention_ft_train_dpo import TARGET_MODULES, load_dataset
from abstention_ft_train_sft import EpochSnapshotCallback, default_run_name


class DPOPTrainer(DPOTrainer):
    """DPOTrainer with the Smaug DPO-Positive loss.

    Requires precompute_ref_log_probs=True so inputs carry ref_chosen_logps /
    ref_rejected_logps; the reference-model forward path is therefore not
    re-implemented here. Assumes the default reverse-KL parameterisation
    (f_divergence_type='reverse_kl') and ld_alpha=None, which is what our runs
    use; both are validated in __init__.
    """

    def __init__(self, *args, dpop_lambda: float = 50.0, **kwargs):
        self.dpop_lambda = dpop_lambda
        super().__init__(*args, **kwargs)
        if not getattr(self, "precompute_ref_logps", False):
            raise RuntimeError(
                "DPOPTrainer requires precompute_ref_log_probs=True so reference "
                "log-probs are available in the batch."
            )
        if getattr(self, "ld_alpha", None) is not None:
            raise RuntimeError("DPOPTrainer does not support ld_alpha; leave it unset.")
        if getattr(self, "f_divergence_type", "reverse_kl") != "reverse_kl":
            raise RuntimeError("DPOPTrainer only supports f_divergence_type='reverse_kl'.")

    def _compute_loss(self, model, inputs, return_outputs=False):
        mode = "train" if self.model.training else "eval"

        _non_model_keys = {"completion_mask", "ref_chosen_logps", "ref_rejected_logps"}
        model_kwargs = {k: v for k, v in inputs.items() if k not in _non_model_keys}
        model_kwargs["use_cache"] = False
        outputs = model(**model_kwargs)

        input_ids = inputs["input_ids"]
        completion_mask = inputs["completion_mask"]
        shift_logits = outputs.logits[..., :-1, :].contiguous()
        shift_labels = input_ids[..., 1:].contiguous()
        shift_completion_mask = completion_mask[..., 1:].contiguous()

        # Use the (memory-patched) selective_log_softmax bound on the dpo module.
        per_token_logps = _dpot.selective_log_softmax(shift_logits, shift_labels)
        per_token_logps[shift_completion_mask == 0] = 0.0
        logps = per_token_logps.sum(dim=1)
        chosen_logps, rejected_logps = logps.chunk(2, dim=0)  # batch is [chosen, rejected]

        ref_chosen_logps = inputs["ref_chosen_logps"]
        ref_rejected_logps = inputs["ref_rejected_logps"]

        chosen_logratios = chosen_logps - ref_chosen_logps
        rejected_logratios = rejected_logps - ref_rejected_logps

        # DPOP: standard DPO margin minus λ·max(0, logπref(y_w) - logπθ(y_w)).
        # The penalty is 0 while the preferred completion stays at least as likely
        # as under the reference, and pushes it back up once it slips below.
        dpop_penalty = torch.relu(-chosen_logratios)  # = max(0, log πref/πθ on y_w)
        dpop_score = (chosen_logratios - rejected_logratios) - self.dpop_lambda * dpop_penalty
        per_sequence_loss = -F.logsigmoid(self.beta * dpop_score)
        loss = per_sequence_loss.mean()

        # ---- metrics (subset of TRL's, plus DPOP-specific diagnostics) ----
        chosen_rewards = self.beta * chosen_logratios.detach()
        rejected_rewards = self.beta * rejected_logratios.detach()
        m = self._metrics[mode]
        m["rewards/chosen"].append(self.accelerator.gather(chosen_rewards).mean().item())
        m["rewards/rejected"].append(self.accelerator.gather(rejected_rewards).mean().item())
        m["rewards/accuracies"].append(
            self.accelerator.gather((chosen_rewards > rejected_rewards).float()).mean().item())
        m["rewards/margins"].append(
            self.accelerator.gather(chosen_rewards - rejected_rewards).mean().item())
        m["logps/chosen"].append(self.accelerator.gather(chosen_logps.detach()).mean().item())
        m["logps/rejected"].append(self.accelerator.gather(rejected_logps.detach()).mean().item())
        # Fraction of the batch where the penalty is active (preferred below ref) and
        # its mean magnitude — the key signal that the DPO failure mode is being caught.
        m["dpop/penalty_active"].append(
            self.accelerator.gather((dpop_penalty.detach() > 0).float()).mean().item())
        m["dpop/penalty_mean"].append(
            self.accelerator.gather(dpop_penalty.detach()).mean().item())
        m["dpop/chosen_logratio"].append(
            self.accelerator.gather(chosen_logratios.detach()).mean().item())

        return (loss, outputs) if return_outputs else loss


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model", required=True)
    p.add_argument("--train_file", required=True)
    p.add_argument("--output_dir", required=True)
    p.add_argument("--max_seq_length", type=int, default=65536)
    p.add_argument("--learning_rate", type=float, default=5e-6)
    p.add_argument("--dpo_beta", type=float, default=0.1,
                   help="KL/regularisation strength β. Paper uses 0.3; default 0.1 "
                        "matches our DPO runs for a like-for-like comparison.")
    p.add_argument("--dpop_lambda", type=float, default=50.0,
                   help="DPOP penalty weight λ (paper default 50; robust across "
                        "{5,50,500}). Higher = stronger pull keeping logπθ(y_w) ≥ logπref(y_w).")
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
    p.add_argument("--save_epochs", type=float, nargs="+", default=None,
                   help="If set, save snapshots at each (fractional) epoch milestone "
                        "into {output_dir}/epoch-{tag}/, disabling default saves. "
                        "All values must be <= --num_train_epochs.")
    p.add_argument("--report_to", nargs="+", default=["tensorboard"],
                   help="HF Trainer report_to integrations (tensorboard, wandb, none, ...).")
    p.add_argument("--logging_dir", default=None,
                   help="Directory for TB event files. Default: {output_dir}/runs.")
    p.add_argument("--run_name", default=None,
                   help="Run name for W&B/TB. Default: auto-generated from method, "
                        "model, learning_rate, lora_r, and dataset balance.")
    args = p.parse_args()

    if args.save_epochs:
        bad = [ep for ep in args.save_epochs if ep > args.num_train_epochs + 1e-9]
        if bad:
            raise ValueError(
                f"--save_epochs values exceed --num_train_epochs={args.num_train_epochs}: {bad}")

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

    run_name = args.run_name or default_run_name(
        method="dpop",
        base_model=args.base_model,
        lr=lr,
        lora_r=args.lora_r if args.peft_mode == "qlora" else None,
        train_file=args.train_file,
    )
    os.environ.setdefault("WANDB_NAME", run_name)

    dpo_args = DPOConfig(
        output_dir=args.output_dir,
        beta=args.dpo_beta,
        loss_type="sigmoid",  # ignored by DPOPTrainer's override; keeps config valid
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
        run_name=run_name,
        remove_unused_columns=False,
        max_length=args.max_seq_length,
        truncation_mode="keep_start",
        precompute_ref_log_probs=True,
    )

    snapshot_cb = None
    if args.save_epochs:
        snapshot_cb = EpochSnapshotCallback(args.save_epochs, args.output_dir, tokenizer)

    trainer = DPOPTrainer(
        model=model,
        ref_model=None,
        args=dpo_args,
        train_dataset=train_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
        callbacks=[snapshot_cb] if snapshot_cb else None,
        dpop_lambda=args.dpop_lambda,
    )
    if snapshot_cb is not None:
        snapshot_cb.attach(trainer)

    trainer.train()

    if not args.save_epochs:
        trainer.save_model(args.output_dir)
        tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
