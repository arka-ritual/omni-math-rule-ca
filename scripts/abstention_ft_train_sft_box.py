#!/usr/bin/env python3
import argparse
import json
import os
from dataclasses import dataclass

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments

from abstention_ft_train_sft import EpochSnapshotCallback, default_run_name

# `language_model.` is optional so this matches both multimodal models whose
# text decoder is nested (Gemma 4: model.language_model.layers.N.…) and
# text-only models (Qwen3.5: model.layers.N.…). Staying anchored to the
# decoder `layers` path keeps Gemma's vision_tower/embed_audio out of LoRA.
TARGET_MODULES = r"model\.(language_model\.)?layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))"


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


class SFTBoxDataset(Dataset):
    def __init__(self, path, tokenizer, max_len):
        self.rows = read_jsonl(path)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        row = self.rows[i]
        messages = row["messages"]
        supervised_suffix = row.get("supervised_suffix", "")

        full = render(self.tokenizer, messages, add_generation_prompt=False)
        enc = self.tokenizer(full, add_special_tokens=False, return_offsets_mapping=True)
        full_ids = enc["input_ids"]
        offsets = enc.get("offset_mapping")

        if len(full_ids) > self.max_len:
            raise ValueError(f"Overlength sft_box example idx={row.get('idx')}: {len(full_ids)} > {self.max_len}")

        # Align the supervised window via the tokenizer's offset_mapping.
        # Naive `len(tok(full[:char_idx]))` masking can be wrong by one token
        # because BPE/SentencePiece may fuse the suffix's leading character
        # with neighbouring chars in `full` (e.g. for "\boxed{...}" the leading
        # "\" gets merged into a "$$\\" token in context but tokenizes as a
        # standalone "\\" token in isolation — so neither character-length nor
        # token-subsequence matching works). offset_mapping is the only
        # correct way: find the first token whose span covers (or starts at)
        # the suffix's start char, and mask everything strictly before it.
        mask_len = None
        if supervised_suffix and offsets is not None:
            char_idx = full.rfind(supervised_suffix)
            if char_idx != -1:
                for t, (s, e) in enumerate(offsets):
                    # First token that overlaps the suffix region. If a token
                    # straddles the boundary (s < char_idx < e), supervise it
                    # so the suffix's leading character isn't silently dropped.
                    if e > char_idx:
                        mask_len = t
                        break
        if mask_len is None:
            # Fallback: standard prompt-only masking.
            prompt = render(self.tokenizer, messages[:2], add_generation_prompt=True)
            mask_len = len(self.tokenizer(prompt, add_special_tokens=False)["input_ids"])

        labels = list(full_ids)
        labels[:mask_len] = [-100] * mask_len
        return {
            "input_ids": torch.tensor(full_ids, dtype=torch.long),
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
    """Load the model in either qlora or full FT mode."""
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
    p.add_argument("--peft_mode", choices=["qlora", "full"], default="qlora")
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--max_grad_norm", type=float, default=1.0)
    p.add_argument("--gradient_checkpointing", action="store_true")
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
    p.add_argument(
        "--run_name",
        default=None,
        help="Run name for W&B/TB. Default: auto-generated from method, model, "
             "learning_rate, lora_r, and dataset balance.",
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

    run_name = args.run_name or default_run_name(
        method="sft_box",
        base_model=args.base_model,
        lr=lr,
        lora_r=args.lora_r if args.peft_mode == "qlora" else None,
        train_file=args.train_file,
    )
    os.environ.setdefault("WANDB_NAME", run_name)

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
        report_to=args.report_to,
        logging_dir=args.logging_dir or os.path.join(args.output_dir, "runs"),
        run_name=run_name,
        remove_unused_columns=False,
    )

    snapshot_cb = None
    if args.save_epochs:
        snapshot_cb = EpochSnapshotCallback(args.save_epochs, args.output_dir, tokenizer)

    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=SFTBoxDataset(args.train_file, tokenizer, args.max_seq_length),
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
