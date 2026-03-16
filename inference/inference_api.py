#!/usr/bin/env python3
"""Unified API-based inference for Omni-MATH-Rule.

Usage:
    python inference/inference_api.py \
        --provider openai --model gpt-5.2 \
        --save_path inference/results/GPT-5.2_standard.jsonl \
        --prompt standard --num_samples 100
"""

import argparse
import asyncio
import json
import os
import sys
import random

# Ensure repo root is on path so imports work when running as a script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tqdm.asyncio import tqdm_asyncio

from inference.prompts import PROMPTS
from inference.providers import get_provider


def load_dataset(path: str) -> list[dict]:
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def load_existing_indices(path: str) -> set[int]:
    """Return set of idx values already written to *path* (for resume)."""
    indices: set[int] = set()
    if not os.path.exists(path):
        return indices
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    indices.add(obj["idx"])
                except (json.JSONDecodeError, KeyError):
                    pass
    return indices


async def run_inference(args):
    # --- Load dataset ---
    dataset = load_dataset(args.data_file)
    # Assign idx if not present
    for i, item in enumerate(dataset):
        if "idx" not in item:
            item["idx"] = i

    # --- Select subset ---
    if args.num_samples > 0:
        rng = random.Random(args.seed)
        indices = list(range(len(dataset)))
        if args.start > 0:
            indices = indices[args.start:]
        if args.num_samples < len(indices):
            indices = rng.sample(indices, args.num_samples)
            indices.sort()
        dataset = [dataset[i] for i in indices]
    elif args.start > 0:
        dataset = dataset[args.start:]

    # --- Resume: skip already-completed items ---
    os.makedirs(os.path.dirname(args.save_path) or ".", exist_ok=True)
    done = load_existing_indices(args.save_path)
    remaining = [item for item in dataset if item["idx"] not in done]
    print(f"Total selected: {len(dataset)}, already done: {len(done)}, remaining: {len(remaining)}")

    if not remaining:
        print("Nothing to do — all items already completed.")
        return

    # --- Resolve prompt ---
    if args.system_prompt:
        prompt_text = args.system_prompt
    else:
        if args.prompt not in PROMPTS:
            raise ValueError(f"Unknown prompt preset '{args.prompt}'. Available: {list(PROMPTS.keys())}")
        prompt_text = PROMPTS[args.prompt]

    if args.prompt_in_user:
        system_prompt = "You are a helpful and harmless assistant."
        user_prefix = prompt_text
    else:
        system_prompt = prompt_text
        user_prefix = None

    # --- Provider ---
    provider_kwargs = {}
    if args.api_key:
        provider_kwargs["api_key"] = args.api_key
    provider = get_provider(args.provider, **provider_kwargs)

    # --- Async inference with immediate writes ---
    sem = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    completed = 0

    async def process(item: dict):
        nonlocal completed
        problem = item.get("problem") or item.get("question", "")
        user_msg = f"{user_prefix}\n\nProblem:\n{problem}" if user_prefix else problem
        async with sem:
            response = await provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_msg,
                model=args.model,
                temperature=args.temperature,
                max_completion_tokens=args.max_tokens,
            )
        result = dict(item)
        result["model_generation"] = response or ""
        result["prompt_mode"] = args.prompt
        # Write immediately so progress is never lost
        async with write_lock:
            with open(args.save_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
            completed += 1
        return result

    tasks = [process(item) for item in remaining]
    await tqdm_asyncio.gather(*tasks, desc="Inference")

    print(f"Wrote {completed} results to {args.save_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="API-based inference for Omni-MATH-Rule")
    parser.add_argument("--provider", type=str, default="openai", help="Provider name (default: openai)")
    parser.add_argument("--model", type=str, required=True, help="Model name (e.g. gpt-5.2)")
    parser.add_argument("--data_file", type=str, default="omni_math_rule.jsonl", help="Path to dataset JSONL")
    parser.add_argument("--save_path", type=str, required=True, help="Output JSONL path")
    parser.add_argument("--prompt", type=str, default="standard", help="Prompt preset name (default: standard)")
    parser.add_argument("--system-prompt", type=str, default=None, dest="system_prompt", help="Custom system prompt (overrides --prompt)")
    parser.add_argument("--temperature", type=float, default=0, help="Sampling temperature (default: 0)")
    parser.add_argument("--max_tokens", type=int, default=32768, help="Max tokens (default: 32768)")
    parser.add_argument("--concurrency", type=int, default=50, help="Max concurrent API calls (default: 50)")
    parser.add_argument("--num_samples", type=int, default=100, help="Number of problems to sample (0=all, default: 100)")
    parser.add_argument("--start", type=int, default=0, help="Start index in dataset (default: 0)")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for sampling (default: 0)")
    parser.add_argument("--api_key", type=str, default=None, help="API key (overrides env variable)")
    parser.add_argument("--prompt-in-user", action="store_true", dest="prompt_in_user", help="Put prompt text in user message instead of system prompt")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_inference(args))
