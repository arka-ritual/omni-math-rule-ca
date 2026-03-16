#!/usr/bin/env python3
"""Run a full sequential adaptive evaluation.

Usage:
    python inference/sequential_run.py \
        --provider anthropic --model claude-opus-4-6 \
        --save_path inference/results/seq_opus-4.6_summary.jsonl \
        --num_questions 100 --seed 42 \
        --context_mode summary \
        --correct 1 --incorrect -10 --skip 0
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inference.providers import get_provider
from inference.sequential.environment import SequentialEnvironment
from inference.sequential.state import ScoringRubric


async def run_sequential(args):
    rubric = ScoringRubric(
        correct=args.correct,
        incorrect=args.incorrect,
        skip=args.skip,
    )

    state_path = args.save_path.replace(".jsonl", ".state.json")

    if args.resume and os.path.exists(state_path):
        env = SequentialEnvironment.from_state(state_path, args.data_file)
        print(f"Resumed from step {env.current_step}/{env.total_steps}, score={env.cumulative_score}")
    else:
        env = SequentialEnvironment(
            dataset_path=args.data_file,
            num_questions=args.num_questions,
            seed=args.seed,
            rubric=rubric,
            context_mode=args.context_mode,
            max_history_chars=args.max_history_chars,
        )
        print(
            f"Starting sequential run: {env.total_steps} questions, "
            f"mode={args.context_mode}, "
            f"rubric=({rubric.correct:+d}/{rubric.incorrect:+d}/{rubric.skip:+d})"
        )

    provider_kwargs = {}
    if args.api_key:
        provider_kwargs["api_key"] = args.api_key
    provider = get_provider(args.provider, **provider_kwargs)

    os.makedirs(os.path.dirname(args.save_path) or ".", exist_ok=True)

    while not env.done:
        system_prompt, user_prompt = env.get_prompts()

        response = await provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=args.model,
            temperature=args.temperature,
            max_completion_tokens=args.max_tokens,
        )

        record = env.step(response or "")

        print(
            f"Step {record.step_number}/{env.total_steps}: "
            f"{record.outcome} ({record.score_delta:+d}) "
            f"| cumulative={record.cumulative_score} "
            f"| difficulty={record.difficulty}"
        )

        # Write result line immediately (crash-safe)
        result_line = record.to_dict()
        result_line["model"] = args.model
        result_line["provider"] = args.provider
        result_line["context_mode"] = args.context_mode
        result_line["rubric"] = {"correct": rubric.correct, "incorrect": rubric.incorrect, "skip": rubric.skip}
        with open(args.save_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result_line, ensure_ascii=False) + "\n")

        # Save state for resume
        env.save_state(state_path)

    # Final summary
    correct = sum(1 for r in env.history if r.outcome == "correct")
    incorrect = sum(1 for r in env.history if r.outcome == "incorrect")
    skipped = sum(1 for r in env.history if r.outcome == "skipped")
    print(f"\n=== FINAL SCORE: {env.cumulative_score} ===")
    print(f"Correct: {correct}, Incorrect: {incorrect}, Skipped: {skipped}")
    if correct + incorrect > 0:
        print(f"Accuracy when attempted: {100 * correct / (correct + incorrect):.1f}%")


def parse_args():
    parser = argparse.ArgumentParser(description="Sequential adaptive environment runner")
    parser.add_argument("--provider", type=str, default="openai")
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--api_key", type=str, default=None)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--max_tokens", type=int, default=32768)
    parser.add_argument("--data_file", type=str, default="omni_math_rule.jsonl")
    parser.add_argument("--save_path", type=str, required=True)
    parser.add_argument("--num_questions", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--context_mode", type=str, default="summary", choices=["full_trace", "summary"])
    parser.add_argument("--max_history_chars", type=int, default=0, help="Max chars for history (0=unlimited)")
    parser.add_argument("--correct", type=int, default=1)
    parser.add_argument("--incorrect", type=int, default=-10)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_sequential(args))
