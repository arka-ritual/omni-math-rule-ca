#!/usr/bin/env python3
"""Intervention runner for Omni-MATH-Rule.

Implements the four prompting-based interventions of Section 6 of the
Consequence Asymmetry paper:

  1. Single-turn multi-step guidance (Wu et al.)  — 1 API call / problem
  2. Multi-turn (Wu et al.)                       — 3 API calls / problem
  3. Multi-turn no-confidence (ablation)          — 2 API calls / problem
  4. Confidence-based scaffolding (Wang et al.)   — post-hoc on #1's outputs

Each (model × prompt-config × intervention) cell writes one JSONL file
into `inference/results/interventions/`. Each line has at minimum
`idx`, `model_generation`, `finish_reason`, `prompt_tokens`,
`completion_tokens`, plus per-turn details for multi-turn runs. The
final-answer JSONL conforms to the format expected by
`evaluation/math_eval_cautious.py` (the evaluator just reads
`model_generation` + `finish_reason`).

Resume is supported: if the output file already contains items with a
given `idx`, they are skipped.

Usage:
    # Intervention 1 (or 4 — the runner skips inference for 4)
    python inference/run_interventions.py \
        --provider anthropic --model claude-haiku-4-5 \
        --intervention 1 --prompt_config Quant-25 \
        --num_samples 200

    # Intervention 4: post-hoc only (reads intervention-1 file, no API calls)
    python inference/run_interventions.py \
        --provider anthropic --model claude-haiku-4-5 \
        --intervention 4 --prompt_config Quant-25 \
        --intervention1_input inference/results/interventions/claude-haiku-4-5_int1_Quant-25.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tqdm.asyncio import tqdm_asyncio

# Best-effort .env loading so the providers pick up API keys without
# requiring the user to source a script.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from inference.providers import get_provider
from inference.intervention_prompts import (
    CONFIGS,
    apply_intervention4,
    build_intervention1,
    build_intervention2_confidence_turn,
    build_intervention2_decision_turn,
    build_intervention3_decision_turn,
    build_solve_turn,
    extract_last_boxed,
    parse_confidence_line,
)


# ----------------------- dataset / IO helpers ---------------------------

def load_dataset(path: str) -> list[dict]:
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def load_existing_indices(path: str) -> set[int]:
    indices: set[int] = set()
    if not os.path.exists(path):
        return indices
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                indices.add(obj["idx"])
            except (json.JSONDecodeError, KeyError):
                pass
    return indices


def select_subset(dataset: list[dict], num_samples: int, seed: int, start: int) -> list[dict]:
    """Shuffle-and-slice subset selection (mirrors inference_api.py)."""
    for i, item in enumerate(dataset):
        item.setdefault("idx", i)
    if num_samples <= 0:
        return dataset[start:] if start > 0 else dataset
    rng = random.Random(seed)
    indices = list(range(len(dataset)))
    if start > 0:
        indices = indices[start:]
    rng.shuffle(indices)
    if num_samples < len(indices):
        indices = indices[:num_samples]
    indices.sort()
    return [dataset[i] for i in indices]


# ----------------------- per-intervention runners -----------------------

async def run_intervention1(provider, model, item, cfg, *, max_tokens, temperature, reasoning_effort=None):
    problem = item.get("problem") or item.get("question", "")
    system, user = build_intervention1(cfg, problem)
    meta = await provider.generate_with_meta(
        system_prompt=system, user_prompt=user,
        model=model, temperature=temperature, max_completion_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
    return {
        "model_generation": meta["text"],
        "finish_reason": meta.get("finish_reason"),
        "prompt_tokens": meta.get("prompt_tokens"),
        "completion_tokens": meta.get("completion_tokens"),
    }


async def run_intervention2(provider, model, item, cfg, *, max_tokens, temperature, reasoning_effort=None):
    """Three sequential calls: solve → confidence → decision."""
    problem = item.get("problem") or item.get("question", "")

    sys1, usr1 = build_solve_turn(problem)
    t1 = await provider.generate_with_meta(
        system_prompt=sys1, user_prompt=usr1,
        model=model, temperature=temperature, max_completion_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
    predicted = extract_last_boxed(t1["text"]) or "[NO ANSWER PARSED]"

    sys2, usr2 = build_intervention2_confidence_turn(problem, predicted)
    t2 = await provider.generate_with_meta(
        system_prompt=sys2, user_prompt=usr2,
        model=model, temperature=temperature, max_completion_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
    confidence = parse_confidence_line(t2["text"]) or "[unparsed]"

    sys3, usr3 = build_intervention2_decision_turn(cfg, problem, predicted, confidence)
    t3 = await provider.generate_with_meta(
        system_prompt=sys3, user_prompt=usr3,
        model=model, temperature=temperature, max_completion_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )

    return _aggregate_turns(
        final=t3,
        turns=[
            ("solve", sys1, usr1, t1),
            ("confidence", sys2, usr2, t2),
            ("decision", sys3, usr3, t3),
        ],
        extras={"predicted_answer_turn1": predicted, "stated_confidence": confidence},
    )


async def run_intervention3(provider, model, item, cfg, *, max_tokens, temperature, reasoning_effort=None):
    """Two sequential calls: solve → decision (no confidence step)."""
    problem = item.get("problem") or item.get("question", "")

    sys1, usr1 = build_solve_turn(problem)
    t1 = await provider.generate_with_meta(
        system_prompt=sys1, user_prompt=usr1,
        model=model, temperature=temperature, max_completion_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
    predicted = extract_last_boxed(t1["text"]) or "[NO ANSWER PARSED]"

    sys2, usr2 = build_intervention3_decision_turn(cfg, problem, predicted)
    t2 = await provider.generate_with_meta(
        system_prompt=sys2, user_prompt=usr2,
        model=model, temperature=temperature, max_completion_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )

    return _aggregate_turns(
        final=t2,
        turns=[
            ("solve", sys1, usr1, t1),
            ("decision", sys2, usr2, t2),
        ],
        extras={"predicted_answer_turn1": predicted},
    )


def _aggregate_turns(*, final, turns, extras: dict) -> dict:
    """Combine multi-turn results: `model_generation` is the FINAL turn's
    text (so the evaluator scores the right thing), `finish_reason` is
    the FINAL turn's reason, but token counts are summed across turns
    and per-turn details preserved under `turns`.
    """
    pt = sum((t[3].get("prompt_tokens") or 0) for t in turns)
    ct = sum((t[3].get("completion_tokens") or 0) for t in turns)
    out = {
        "model_generation": final["text"],
        "finish_reason": final.get("finish_reason"),
        "prompt_tokens": pt or None,
        "completion_tokens": ct or None,
        "turns": [
            {
                "name": name,
                "system_prompt": sysp,
                "user_prompt": usrp,
                "text": t["text"],
                "finish_reason": t.get("finish_reason"),
                "prompt_tokens": t.get("prompt_tokens"),
                "completion_tokens": t.get("completion_tokens"),
            }
            for (name, sysp, usrp, t) in turns
        ],
    }
    out.update(extras)
    return out


# ------------------------- intervention 4: post-hoc ---------------------

def run_intervention4_posthoc(input_path: str, save_path: str, cfg) -> None:
    """Read an intervention-1 jsonl, apply Wang's τ(λ) decision rule,
    write a new jsonl in the format the evaluator consumes."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Intervention 1 input not found: {input_path}")
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    n = 0
    with open(input_path, "r", encoding="utf-8") as fin, \
         open(save_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            result = apply_intervention4(item.get("model_generation", ""), cfg)
            new_item = dict(item)
            # Replace the things the evaluator cares about.
            new_item["model_generation"] = result["model_generation"]
            # If int-1 was truncated, the synthesized text is still a
            # complete deliberate decision, so override finish_reason.
            new_item["finish_reason"] = "stop"
            new_item["intervention"] = 4
            new_item["int4_answer"] = result["intervention1_answer"]
            new_item["int4_confidence"] = result["intervention1_confidence"]
            new_item["int4_threshold"] = result["threshold"]
            new_item["int4_decision"] = result["decision"]
            fout.write(json.dumps(new_item, ensure_ascii=False) + "\n")
            n += 1
    print(f"intervention 4 post-hoc: wrote {n} items to {save_path}")


# -------------------------------- main ----------------------------------

INTERVENTION_FN = {
    1: run_intervention1,
    2: run_intervention2,
    3: run_intervention3,
}


async def run(args):
    cfg = CONFIGS[args.prompt_config]

    # Intervention 4 is purely post-hoc — no API calls.
    if args.intervention == 4:
        if not args.intervention1_input:
            raise ValueError("--intervention1_input is required for --intervention 4")
        run_intervention4_posthoc(args.intervention1_input, args.save_path, cfg)
        return

    fn = INTERVENTION_FN[args.intervention]

    dataset = select_subset(
        load_dataset(args.data_file), args.num_samples, args.seed, args.start
    )
    os.makedirs(os.path.dirname(args.save_path) or ".", exist_ok=True)
    done = load_existing_indices(args.save_path)
    remaining = [item for item in dataset if item["idx"] not in done]
    print(
        f"intervention={args.intervention} cfg={args.prompt_config} "
        f"model={args.model}: total={len(dataset)} done={len(done)} "
        f"remaining={len(remaining)}"
    )
    if not remaining:
        print("Nothing to do.")
        return

    provider_kwargs = {}
    if args.api_key:
        provider_kwargs["api_key"] = args.api_key
    if args.openrouter_provider:
        provider_kwargs["openrouter_provider"] = args.openrouter_provider
    provider = get_provider(args.provider, **provider_kwargs)

    sem = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    completed = 0
    failed = 0

    async def process(item: dict):
        nonlocal completed, failed
        try:
            async with sem:
                result = await fn(
                    provider, args.model, item, cfg,
                    max_tokens=args.max_tokens, temperature=args.temperature,
                    reasoning_effort=args.reasoning_effort,
                )
        except Exception as e:
            failed += 1
            print(f"[FAIL idx={item.get('idx')}] {type(e).__name__}: {e}")
            return
        out = dict(item)
        out["intervention"] = args.intervention
        out["prompt_config"] = args.prompt_config
        out.update(result)
        async with write_lock:
            with open(args.save_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
            completed += 1

    tasks = [process(item) for item in remaining]
    await tqdm_asyncio.gather(*tasks, desc=f"int{args.intervention}/{args.prompt_config}")
    print(
        f"Wrote {completed} results to {args.save_path}"
        + (f"  ({failed} failed — rerun to retry)" if failed else "")
    )


def parse_args():
    p = argparse.ArgumentParser(description="Intervention runner for Omni-MATH-Rule")
    p.add_argument("--provider", required=True,
                   choices=["openai", "anthropic", "google", "openrouter", "vllm"])
    p.add_argument("--model", required=True, help="Provider-specific model id")
    p.add_argument("--intervention", type=int, required=True, choices=[1, 2, 3, 4])
    p.add_argument("--prompt_config", required=True, choices=list(CONFIGS.keys()))
    p.add_argument("--save_path", required=True)
    p.add_argument("--data_file", default="omni_math_rule.jsonl")
    p.add_argument("--num_samples", type=int, default=200)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--seed", type=int, default=100)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max_tokens", type=int, default=32768)
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--reasoning_effort", "--reasoning-effort",
                   dest="reasoning_effort", default=None,
                   choices=[None, "minimal", "low", "medium", "high"],
                   help="Explicit reasoning_effort to send to OpenAI. "
                        "Default None = omit the field, which makes the API "
                        "fall back to the model default (medium for the "
                        "GPT-5 family). To pin a value (e.g. for "
                        "reproducibility) pass it explicitly. 'minimal' is "
                        "GPT-5-only. Currently honored by the OpenAI "
                        "provider; ignored by other providers.")
    p.add_argument("--api_key", default=None)
    p.add_argument("--openrouter-provider", "--openrouter_provider",
                   dest="openrouter_provider", default=None,
                   help="When --provider=openrouter, force OpenRouter to "
                        "route to a specific upstream provider (e.g. "
                        "'DeepSeek'). Disables fallbacks.")
    p.add_argument("--intervention1_input", default=None,
                   help="Required for --intervention 4: path to the "
                        "intervention-1 results JSONL to re-score.")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
