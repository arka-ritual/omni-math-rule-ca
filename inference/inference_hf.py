#!/usr/bin/env python3
"""Transformers/PEFT-based inference, drop-in replacement for inference_vllm.py.

Use this when vLLM silently mis-loads a LoRA adapter (e.g. key/path mismatches
on Gemma4ForConditionalGeneration) or when you want to verify generations
against the same code path used at training time.

CLI is kept compatible with inference_vllm.py where possible. vLLM-only flags
(tensor_parallel_size, max_model_len, gpu_memory_utilization,
max_num_batched_tokens, enable_prefix_caching, max_lora_rank) are accepted but
ignored so the same shell scripts keep working.
"""
import argparse
import json
import os
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import PROMPTS


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def batches(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def problem(row):
    return row.get("problem", row.get("question"))


def render_prompt(tokenizer, system, user_problem, enable_thinking):
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_problem},
    ]
    if tokenizer.chat_template is not None:
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )
        except TypeError:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
    return f"{system}\n\nProblem:\n{user_problem}\n\nAnswer:\n"


def finish_reason_from_eos(seq_ids, eos_ids, max_new):
    # mimic vLLM's finish_reason: "stop" if EOS hit, "length" otherwise
    last = seq_ids[-1].item() if len(seq_ids) else None
    if last is not None and last in eos_ids:
        return "stop"
    if len(seq_ids) >= max_new:
        return "length"
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--data_file", required=True)
    p.add_argument("--save_path", required=True)
    p.add_argument("--prompt", default="standard")
    p.add_argument("--system-prompt", dest="system_prompt", default=None)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=None)
    p.add_argument("--batch_size", type=int, default=8)

    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--top_p", type=float, default=0.8)
    p.add_argument("--top_k", type=int, default=20)
    p.add_argument("--repetition_penalty", type=float, default=1.0)
    p.add_argument("--max_tokens", type=int, default=4096)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--enable_thinking", action="store_true")
    p.add_argument("--dtype", default="bfloat16",
                   choices=["bfloat16", "float16", "float32"])

    p.add_argument("--lora_adapter", default=None)

    # vLLM-only flags, accepted and silently ignored for CLI compatibility.
    for ignored in [
        "--tensor_parallel_size", "--max_model_len", "--gpu_memory_utilization",
        "--max_num_batched_tokens", "--max_lora_rank", "--presence_penalty",
    ]:
        p.add_argument(ignored, default=None)
    p.add_argument("--enable_prefix_caching", action="store_true")

    args = p.parse_args()

    torch.manual_seed(args.seed)

    system = args.system_prompt if args.system_prompt is not None else PROMPTS[args.prompt]
    rows = read_jsonl(args.data_file)[args.start:args.end]

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16,
             "float32": torch.float32}[args.dtype]

    # Try flash_attention_2, fall back to sdpa, fall back to eager.
    attn_impl = None
    for impl in ("flash_attention_2", "sdpa"):
        try:
            model = AutoModelForCausalLM.from_pretrained(
                args.model, dtype=dtype, trust_remote_code=True,
                attn_implementation=impl,
            )
            attn_impl = impl
            break
        except (ImportError, ValueError) as e:
            print(f"[inference_hf] {impl} unavailable: {e}", flush=True)
    if attn_impl is None:
        model = AutoModelForCausalLM.from_pretrained(
            args.model, dtype=dtype, trust_remote_code=True,
        )
        attn_impl = "eager"
    print(f"[inference_hf] attn_implementation={attn_impl}", flush=True)
    if args.lora_adapter is not None:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.lora_adapter)
        # sanity print so silent mismatches are loud
        lora_keys = [n for n, _ in model.named_parameters()
                     if "lora_A" in n or "lora_B" in n]
        print(f"[inference_hf] loaded {len(lora_keys)} LoRA parameter tensors "
              f"from {args.lora_adapter}", flush=True)
        assert lora_keys, "PEFT loaded zero LoRA tensors — adapter is not active."

    model.to("cuda").eval()

    prompts_text = [
        render_prompt(tokenizer, system, problem(row), args.enable_thinking)
        for row in rows
    ]

    do_sample = args.temperature > 0
    gen_kwargs = dict(
        max_new_tokens=args.max_tokens,
        do_sample=do_sample,
        repetition_penalty=args.repetition_penalty,
        pad_token_id=tokenizer.pad_token_id,
    )
    if do_sample:
        gen_kwargs.update(
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k if args.top_k and args.top_k > 0 else 0,
        )

    eos_ids = set()
    if tokenizer.eos_token_id is not None:
        eos_ids.add(tokenizer.eos_token_id)
    # Gemma uses <end_of_turn> as a stop sentinel in the chat template
    for tok_str in ["<end_of_turn>", "<|im_end|>", "<eos>"]:
        tid = tokenizer.convert_tokens_to_ids(tok_str)
        if isinstance(tid, int) and tid != tokenizer.unk_token_id:
            eos_ids.add(tid)
    if eos_ids:
        gen_kwargs["eos_token_id"] = list(eos_ids)

    generated = []
    for batch_prompts in tqdm(list(batches(prompts_text, args.batch_size)),
                              desc="batches"):
        enc = tokenizer(batch_prompts, return_tensors="pt",
                        padding=True, truncation=False).to("cuda")
        with torch.inference_mode():
            out = model.generate(**enc, **gen_kwargs)
        input_len = enc["input_ids"].shape[1]
        new_tokens = out[:, input_len:]
        for i, seq in enumerate(new_tokens):
            text = tokenizer.decode(seq, skip_special_tokens=True)
            fr = finish_reason_from_eos(seq, eos_ids, args.max_tokens)
            generated.append({"text": text, "finish_reason": fr,
                              "stop_reason": None})

    os.makedirs(os.path.dirname(args.save_path), exist_ok=True)
    with open(args.save_path, "w", encoding="utf-8") as f:
        for row, gen in zip(rows, generated):
            out = dict(row)
            out["model_generation"] = gen["text"]
            out["generation_finish_reason"] = gen["finish_reason"]
            out["generation_stop_reason"] = gen["stop_reason"]
            out["prompt_mode"] = (args.prompt if args.system_prompt is None
                                  else "system_prompt_override")
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
