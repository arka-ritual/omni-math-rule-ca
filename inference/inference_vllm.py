#!/usr/bin/env python3
import argparse
import json
import os
import sys

from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import PROMPTS

from vllm.lora.request import LoRARequest


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--data_file", required=True)
    p.add_argument("--save_path", required=True)
    p.add_argument("--prompt", default="standard")
    p.add_argument("--system-prompt", default=None)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=None)
    p.add_argument("--batch_size", type=int, default=128)
    p.add_argument("--tensor_parallel_size", type=int, default=1)

    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--top_p", type=float, default=0.8)
    p.add_argument("--top_k", type=int, default=20)
    p.add_argument("--presence_penalty", type=float, default=0.0)
    p.add_argument("--repetition_penalty", type=float, default=1.0)
    p.add_argument("--max_tokens", type=int, default=4096)
    p.add_argument("--max_model_len", type=int, default=32768)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--enable_thinking", action="store_true")
    p.add_argument("--gpu_memory_utilization", type=float, default=None)
    p.add_argument("--max_num_batched_tokens", type=int, default=None)
    p.add_argument("--enable_prefix_caching", action="store_true")

    p.add_argument("--lora_adapter", default=None)
    p.add_argument("--max_lora_rank", type=int, default=16)
    p.add_argument(
        "--lora_merge_mode",
        choices=["native", "merge"],
        default="merge",
        help=(
            "How to apply the LoRA. 'native' uses vLLM's enable_lora pathway. "
            "'merge' (default) pre-bakes the adapter into a cached merged "
            "checkpoint and loads that as the base model — works around "
            "vLLM's silent LoRA-load bug on multimodal Gemma4 and is also ~10x "
            "faster than vLLM's LoRA fastpath."
        ),
    )
    p.add_argument(
        "--merged_cache_dir",
        default="checkpoints/_merged_cache",
        help="Where to cache adapter-merged base models (used with --lora_merge_mode=merge).",
    )
    args = p.parse_args()

    system = args.system_prompt if args.system_prompt is not None else PROMPTS[args.prompt]
    rows = read_jsonl(args.data_file)[args.start:args.end]

    # If --lora_merge_mode=merge, materialise a merged checkpoint and load it
    # as the base model (no vLLM LoRA pathway). Required for multimodal Gemma4,
    # where vLLM's enable_lora silently fails to apply the adapter.
    base_model_path = args.model
    if args.lora_adapter is not None and args.lora_merge_mode == "merge":
        import subprocess
        adapter_tag = os.path.basename(os.path.abspath(args.lora_adapter.rstrip("/")))
        adapter_parent = os.path.basename(os.path.dirname(os.path.abspath(args.lora_adapter.rstrip("/"))))
        base_slug = args.model.replace("/", "__")
        merged_dir = os.path.join(
            args.merged_cache_dir, base_slug, adapter_parent, adapter_tag,
        )
        if not (os.path.exists(os.path.join(merged_dir, "config.json"))
                and os.path.exists(os.path.join(merged_dir, "model.safetensors"))):
            print(f"[inference_vllm] merging adapter into {merged_dir} ...", flush=True)
            subprocess.run(
                [
                    "python3",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "scripts", "merge_lora.py"),
                    "--base_model", args.model,
                    "--adapter_dir", args.lora_adapter,
                    "--out_dir", merged_dir,
                ],
                check=True,
            )
        else:
            print(f"[inference_vllm] reusing cached merged model at {merged_dir}", flush=True)
        base_model_path = merged_dir
        # Tell the downstream LLM init to NOT enable the LoRA pathway.
        args.lora_adapter = None

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    prompts = [
        render_prompt(tokenizer, system, problem(row), args.enable_thinking)
        for row in rows
    ]

    llm_kwargs = dict(
        model=base_model_path,
        tensor_parallel_size=args.tensor_parallel_size,
        max_model_len=args.max_model_len,
        trust_remote_code=True,
    )
    if args.lora_adapter is not None:
        llm_kwargs["enable_lora"] = True
        llm_kwargs["max_lora_rank"] = args.max_lora_rank
    if args.gpu_memory_utilization is not None:
        llm_kwargs["gpu_memory_utilization"] = args.gpu_memory_utilization
    if args.max_num_batched_tokens is not None:
        llm_kwargs["max_num_batched_tokens"] = args.max_num_batched_tokens
    if args.enable_prefix_caching:
        llm_kwargs["enable_prefix_caching"] = True

    llm = LLM(**llm_kwargs)
    sampling = SamplingParams(
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        max_tokens=args.max_tokens,
        seed=args.seed,
        presence_penalty=args.presence_penalty,
        repetition_penalty=args.repetition_penalty,
    )

    lora_request = None
    if args.lora_adapter is not None:
        lora_request = LoRARequest("adapter", 1, args.lora_adapter)

    generated = []
    for batch in batches(prompts, args.batch_size):
        for out in llm.generate(batch, sampling, lora_request=lora_request):
            o = out.outputs[0]
            generated.append({
                "text": o.text,
                "finish_reason": getattr(o, "finish_reason", None),
                "stop_reason": getattr(o, "stop_reason", None),
            })

    os.makedirs(os.path.dirname(args.save_path), exist_ok=True)
    with open(args.save_path, "w", encoding="utf-8") as f:
        for row, gen in zip(rows, generated):
            out = dict(row)
            out["model_generation"] = gen["text"]
            out["generation_finish_reason"] = gen["finish_reason"]
            out["generation_stop_reason"] = gen["stop_reason"]
            out["prompt_mode"] = args.prompt if args.system_prompt is None else "system_prompt_override"
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()