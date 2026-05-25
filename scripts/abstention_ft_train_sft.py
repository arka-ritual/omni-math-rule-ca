#!/usr/bin/env python3
import argparse
import json
import os
from dataclasses import dataclass

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)


def epoch_tag(ep: float) -> str:
    """Filesystem-friendly tag for an epoch milestone (1.0 -> '1', 0.5 -> '0p5')."""
    s = ("%g" % float(ep))
    return s.replace(".", "p")


class EpochSnapshotCallback(TrainerCallback):
    """Save full model+tokenizer snapshots when training crosses each target epoch.

    Lets one training run produce N intermediate checkpoints along its LR schedule
    (e.g. train for 8 epochs once, save snapshots at {0.5, 1, 2, 3, 5, 8}) instead
    of running N independent fine-tunes from scratch.
    """

    def __init__(self, save_epochs, output_dir, tokenizer):
        self.targets = sorted({float(e) for e in save_epochs})
        self.fired = set()
        self.output_dir = output_dir
        self.tokenizer = tokenizer
        self.trainer = None

    def attach(self, trainer):
        self.trainer = trainer

    def _maybe_snapshot(self, state):
        if self.trainer is None:
            return
        cur_epoch = float(state.epoch or 0.0)
        for ep in self.targets:
            if ep in self.fired:
                continue
            # Fire as soon as the running epoch counter reaches the milestone
            # (HF Trainer's state.epoch is fractional, updated after each step).
            if cur_epoch + 1e-9 >= ep:
                save_dir = os.path.join(self.output_dir, f"epoch-{epoch_tag(ep)}")
                os.makedirs(save_dir, exist_ok=True)
                self.trainer.save_model(save_dir)
                self.tokenizer.save_pretrained(save_dir)
                self.fired.add(ep)
                print(f"[snapshot] epoch={cur_epoch:.4f} -> {save_dir}")

    def on_step_end(self, args, state, control, **kwargs):
        self._maybe_snapshot(state)

    def on_train_end(self, args, state, control, **kwargs):
        self._maybe_snapshot(state)

TARGET_MODULES = r"model\.language_model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))"


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def render(tokenizer, messages, add_generation_prompt=False):
    if tokenizer.chat_template is not None:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
            enable_thinking=True,
        )
    system, user = messages[0]["content"], messages[1]["content"]
    text = f"{system}\n\nProblem:\n{user}\n\nAnswer:\n"
    return text + messages[2]["content"] if len(messages) == 3 else text


class SFTDataset(Dataset):
    def __init__(self, path, tokenizer, max_len):
        self.rows = read_jsonl(path)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        row = self.rows[i]
        messages = row["messages"]
        prompt = render(self.tokenizer, messages[:2], add_generation_prompt=True)
        full = render(self.tokenizer, messages, add_generation_prompt=False)
        prompt_ids = self.tokenizer(prompt, add_special_tokens=False)["input_ids"]
        enc = self.tokenizer(full, add_special_tokens=False)

        if len(enc["input_ids"]) > self.max_len:
            raise ValueError(f"Overlength SFT example idx={row.get('idx')}: {len(enc['input_ids'])} > {self.max_len}")

        labels = list(enc["input_ids"])
        labels[:len(prompt_ids)] = [-100] * len(prompt_ids)
        return {
            "input_ids": torch.tensor(enc["input_ids"], dtype=torch.long),
            "attention_mask": torch.tensor(enc["attention_mask"], dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


@dataclass
class Collator:
    tokenizer: object

    def __call__(self, features):
        pad_id = self.tokenizer.pad_token_id
        max_len = max(len(x["input_ids"]) for x in features)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for x in features:
            n = max_len - len(x["input_ids"])
            batch["input_ids"].append(torch.cat([x["input_ids"], torch.full((n,), pad_id)]))
            batch["attention_mask"].append(torch.cat([x["attention_mask"], torch.zeros(n, dtype=torch.long)]))
            batch["labels"].append(torch.cat([x["labels"], torch.full((n,), -100)]))
        return {k: torch.stack(v) for k, v in batch.items()}


def build_model(args):
    """Load the model in either qlora (4-bit + LoRA) or full (bf16, all params trainable) mode."""
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
        model = get_peft_model(
            model,
            LoraConfig(
                r=args.lora_r,
                lora_alpha=args.lora_alpha,
                lora_dropout=0.05,
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=TARGET_MODULES,
            ),
        )
        model.print_trainable_parameters()
        return model

    if args.peft_mode == "full":
        model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        model.config.use_cache = False
        # Required for gradient checkpointing to work with bf16 full FT.
        if hasattr(model, "gradient_checkpointing_enable"):
            model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
            if hasattr(model, "enable_input_require_grads"):
                model.enable_input_require_grads()
        return model

    raise ValueError(f"Unknown --peft_mode: {args.peft_mode}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model", required=True)
    p.add_argument("--train_file", required=True)
    p.add_argument("--output_dir", required=True)
    p.add_argument("--max_seq_length", type=int, default=65536)
    p.add_argument("--learning_rate", type=float, default=2e-5)
    p.add_argument("--num_train_epochs", type=float, default=3)
    p.add_argument("--per_device_train_batch_size", type=int, default=1)
    p.add_argument("--gradient_accumulation_steps", type=int, default=16)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--logging_steps", type=int, default=1)
    p.add_argument(
        "--peft_mode",
        choices=["qlora", "full"],
        default="qlora",
        help="qlora = 4-bit NF4 + LoRA r=lora_r; full = full bf16 fine-tuning.",
    )
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument(
        "--max_grad_norm",
        type=float,
        default=1.0,
        help="Gradient norm clip threshold. Trainer logs raw grad_norm per step "
             "even when clipping doesn't fire — set high (e.g. 1e9) to disable "
             "clipping while still recording the natural distribution.",
    )
    p.add_argument(
        "--gradient_checkpointing",
        action="store_true",
        help="Force-enable gradient checkpointing (auto-on for full FT).",
    )
    p.add_argument("--learning_rate_full", type=float, default=None,
                   help="Optional override LR when --peft_mode full (else --learning_rate is used).")
    p.add_argument(
        "--save_epochs",
        type=float,
        nargs="+",
        default=None,
        help="If set, save a checkpoint snapshot at each of these (fractional) epoch "
             "milestones into {output_dir}/epoch-{tag}/. Disables the default "
             "save_strategy='epoch' so no extra end-of-epoch checkpoints are written. "
             "All milestones must be <= --num_train_epochs.",
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

    model = build_model(args)

    lr = args.learning_rate
    if args.peft_mode == "full" and args.learning_rate_full is not None:
        lr = args.learning_rate_full

    train_args = TrainingArguments(
        output_dir=args.output_dir,
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
        gradient_checkpointing=args.gradient_checkpointing or args.peft_mode == "full",
        logging_steps=args.logging_steps,
        save_strategy="no" if args.save_epochs else "epoch",
        save_total_limit=None if args.save_epochs else 1,
        seed=args.seed,
        report_to="none",
        remove_unused_columns=False,
    )

    snapshot_cb = None
    if args.save_epochs:
        snapshot_cb = EpochSnapshotCallback(args.save_epochs, args.output_dir, tokenizer)

    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=SFTDataset(args.train_file, tokenizer, args.max_seq_length),
        data_collator=Collator(tokenizer),
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
