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

# Best-effort .env loading so the providers pick up API keys without
# requiring the user to source a script. Mirrors run_interventions.py.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from inference.prompts import PROMPTS, build_quantitative_grading
from inference.providers import get_provider
from inference import fewshot


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


def select_dataset(
    dataset: list[dict],
    *,
    num_samples: int,
    start: int,
    seed: int,
) -> list[dict]:
    """Select a deterministic shuffle-and-slice subset.

    For a fixed seed/start, the N-item selection is always a prefix (as an
    unordered set) of a larger selection. Sorting the chosen indices keeps
    output order stable and makes a pilot file safely resumable to N=100.
    """
    if num_samples > 0:
        rng = random.Random(seed)
        indices = list(range(len(dataset)))
        if start > 0:
            indices = indices[start:]
        rng.shuffle(indices)
        if num_samples < len(indices):
            indices = indices[:num_samples]
        indices.sort()
        return [dataset[i] for i in indices]
    if start > 0:
        return dataset[start:]
    return dataset


async def run_inference(args):
    # --- Load dataset ---
    dataset = load_dataset(args.data_file)
    # Assign idx if not present
    for i, item in enumerate(dataset):
        if "idx" not in item:
            item["idx"] = i

    # --- Select subset ---
    # Use shuffle-and-slice (NOT rng.sample) so that for a fixed seed, a
    # smaller --num_samples is ALWAYS a strict prefix of a larger one. This
    # makes resume work correctly when re-running with a smaller num_samples
    # than the original run. `random.sample(seq, k)` does not have this
    # property — its output for k=N₁ and k=N₂ can have non-trivial differences.
    dataset = select_dataset(
        dataset,
        num_samples=args.num_samples,
        start=args.start,
        seed=args.seed,
    )

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
    elif args.prompt == "quantitative_grading":
        # Render with the requested rubric (defaults to 1 / -10 / 0).
        prompt_text = build_quantitative_grading(
            args.rubric_correct, args.rubric_incorrect, args.rubric_abstain,
        )
        print(f"Using quantitative_grading rubric: correct={args.rubric_correct}, "
              f"incorrect={args.rubric_incorrect}, abstain={args.rubric_abstain}")
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

    # --- Few-shot preamble (base models) ---
    fewshot_preamble: str | None = None
    stop_sequences: list[str] | None = None
    if args.fewshot_variant:
        if args.fewshot_variant not in fewshot.VARIANTS:
            raise ValueError(
                f"Unknown fewshot variant '{args.fewshot_variant}'. Available: {fewshot.VARIANTS}"
            )
        fewshot_preamble = fewshot.build_preamble(args.fewshot_variant, prompt_text)
        stop_sequences = fewshot.STOP_SEQUENCES
        # In few-shot mode the consequence framing is already embedded inline
        # before each Q (when applicable); the system prompt becomes empty so
        # the autocomplete starts cleanly with the preamble.
        system_prompt = ""
        user_prefix = None

    # --- Provider ---
    provider_kwargs = {}
    if args.api_key:
        provider_kwargs["api_key"] = args.api_key
    if args.base_model:
        provider_kwargs["base_model"] = True
    if args.provider == "vllm" and args.base_model_timeout is not None:
        provider_kwargs["base_model_timeout"] = args.base_model_timeout
    if args.openrouter_provider:
        provider_kwargs["openrouter_provider"] = args.openrouter_provider
    provider = get_provider(args.provider, **provider_kwargs)

    # --- Async inference with immediate writes ---
    sem = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    completed = 0
    failed = 0

    async def process(item: dict):
        nonlocal completed, failed
        problem = item.get("problem") or item.get("question", "")
        if fewshot_preamble is not None:
            user_msg = (
                fewshot_preamble
                + "\n\n"
                + fewshot.format_query(problem, args.fewshot_variant, prompt_text)
            )
        elif user_prefix:
            user_msg = f"{user_prefix}\n\nProblem:\n{problem}"
        else:
            user_msg = problem
        try:
            async with sem:
                meta = await provider.generate_with_meta(
                    system_prompt=system_prompt,
                    user_prompt=user_msg,
                    model=args.model,
                    temperature=None if args.omit_temperature else args.temperature,
                    max_completion_tokens=args.max_tokens,
                    stop=stop_sequences,
                    reasoning_effort=args.reasoning_effort,
                )
        except Exception as e:
            # Per-item failure isolation: log and skip so one bad request
            # (timeout, connection drop, etc.) doesn't crash the whole run.
            # The item is left out of the save file, so a subsequent rerun
            # with --resume picks it up automatically.
            failed += 1
            print(f"[FAIL idx={item.get('idx')}] {type(e).__name__}: {e}")
            return None
        result = dict(item)
        result["model_generation"] = meta.pop("text", "") or ""
        result.update(meta)
        result["prompt_mode"] = args.prompt
        result["request_provider"] = args.provider
        result["request_model"] = args.model
        result["request_openrouter_provider"] = args.openrouter_provider
        result["reasoning_effort"] = args.reasoning_effort
        result["temperature"] = None if args.omit_temperature else args.temperature
        result["max_completion_tokens"] = args.max_tokens
        result["dataset_seed"] = args.seed
        if args.prompt == "quantitative_grading":
            result["rubric_correct"] = args.rubric_correct
            result["rubric_incorrect"] = args.rubric_incorrect
            result["rubric_abstain"] = args.rubric_abstain
        async with write_lock:
            with open(args.save_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
            completed += 1
        return result

    tasks = [process(item) for item in remaining]
    await tqdm_asyncio.gather(*tasks, desc="Inference")

    print(f"Wrote {completed} results to {args.save_path}" + (f"  ({failed} failed — rerun to retry)" if failed else ""))


def parse_args():
    parser = argparse.ArgumentParser(description="API-based inference for Omni-MATH-Rule")
    parser.add_argument("--provider", type=str, default="openai", help="Provider name (default: openai)")
    parser.add_argument("--model", type=str, required=True, help="Model name (e.g. gpt-5.2)")
    parser.add_argument("--data_file", type=str, default="omni_math_rule.jsonl", help="Path to dataset JSONL")
    parser.add_argument("--save_path", type=str, required=True, help="Output JSONL path")
    parser.add_argument("--prompt", type=str, default="standard", help="Prompt preset name (default: standard)")
    parser.add_argument("--system-prompt", type=str, default=None, dest="system_prompt", help="Custom system prompt (overrides --prompt)")
    parser.add_argument("--temperature", type=float, default=0, help="Sampling temperature (default: 0)")
    parser.add_argument("--omit-temperature", action="store_true",
                        help="Omit temperature from the API request and use the model/provider default.")
    parser.add_argument("--max_tokens", type=int, default=32768, help="Max tokens (default: 32768)")
    parser.add_argument("--concurrency", type=int, default=50, help="Max concurrent API calls (default: 50)")
    parser.add_argument("--num_samples", type=int, default=100, help="Number of problems to sample (0=all, default: 100)")
    parser.add_argument("--start", type=int, default=0, help="Start index in dataset (default: 0)")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for sampling (default: 0)")
    parser.add_argument("--api_key", type=str, default=None, help="API key (overrides env variable)")
    parser.add_argument("--openrouter-provider", "--openrouter_provider",
                        dest="openrouter_provider", default=None,
                        help="OpenRouter sub-provider to pin via provider routing "
                             "(e.g. 'openai'). Sets allow_fallbacks=false and "
                             "require_parameters=true, so the request fails loudly "
                             "if that upstream cannot honor the request.")
    parser.add_argument("--prompt-in-user", action="store_true", dest="prompt_in_user", help="Put prompt text in user message instead of system prompt")
    parser.add_argument("--reasoning-effort", "--reasoning_effort",
                        dest="reasoning_effort", default=None,
                        choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
                        help="Explicit reasoning effort to send to the provider. "
                             "Default None = omit the field, which makes the "
                             "API fall back to the model default (medium for "
                             "GPT-5.6 Sol). To pin a value for reproducibility, "
                             "pass it explicitly.")
    parser.add_argument("--base_model", action="store_true", help="Tell the vllm provider this is a base (non-instruction-tuned) model — uses /v1/completions instead of /v1/chat/completions")
    parser.add_argument("--base_model_timeout", type=float, default=60.0,
                        help="Per-request timeout (seconds) for base-model autocomplete calls (default: 60). Has no effect on chat-completions calls.")
    parser.add_argument("--fewshot_variant", type=str, default=None, choices=fewshot.VARIANTS,
                        help=f"Enable few-shot scaffolding for base models. One of: {', '.join(fewshot.VARIANTS)}")
    # Rubric values for --prompt quantitative_grading (ignored otherwise).
    parser.add_argument("--rubric_correct", type=float, default=1, help="Score for a correct answer (quantitative_grading only, default: 1)")
    parser.add_argument("--rubric_incorrect", type=float, default=-10, help="Score for an incorrect answer (quantitative_grading only, default: -10)")
    parser.add_argument("--rubric_abstain", type=float, default=0, help="Score for abstaining (quantitative_grading only, default: 0)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_inference(args))
