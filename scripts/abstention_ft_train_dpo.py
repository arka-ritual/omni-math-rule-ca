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

TARGET_MODULES = r"model\.language_model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))"


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
    args = p.parse_args()

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
        save_strategy="epoch",
        save_total_limit=1,
        seed=args.seed,
        report_to="none",
        remove_unused_columns=False,
        max_length=args.max_seq_length,
        truncation_mode="keep_start",
        precompute_ref_log_probs=True,
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=dpo_args,
        train_dataset=train_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
