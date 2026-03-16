#!/usr/bin/env python3
"""Step-by-step agentic interface for the sequential environment.

Two modes of operation:

1. INTERACTIVE (stdin/stdout JSON-lines loop):
    python inference/sequential_agent.py --save_path results.jsonl

2. ONE-STEP CLI (for Claude Code / Codex / shell scripts):
    # Get the current question:
    python inference/sequential_agent.py --state state.json --action get_question

    # Submit a response:
    python inference/sequential_agent.py --state state.json --action submit \
        --response "Let me solve this...\\n\\boxed{42}"

    # Check status:
    python inference/sequential_agent.py --state state.json --action status
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inference.sequential.environment import SequentialEnvironment
from inference.sequential.state import ScoringRubric


def _make_env(args) -> tuple[SequentialEnvironment, str]:
    """Create or resume an environment. Returns (env, state_path)."""
    rubric = ScoringRubric(correct=args.correct, incorrect=args.incorrect, skip=args.skip)

    state_path = args.state
    if not state_path and args.save_path:
        state_path = args.save_path.replace(".jsonl", ".state.json")

    if state_path and os.path.exists(state_path):
        env = SequentialEnvironment.from_state(state_path, args.data_file)
    else:
        env = SequentialEnvironment(
            dataset_path=args.data_file,
            num_questions=args.num_questions,
            seed=args.seed,
            rubric=rubric,
            context_mode=args.context_mode,
            max_history_chars=args.max_history_chars,
        )

    return env, state_path


def _save(env, state_path, args):
    """Save state and optionally append to JSONL."""
    if state_path:
        env.save_state(state_path)


def action_get_question(args):
    """Print the current question as JSON and exit."""
    env, state_path = _make_env(args)

    if env.done:
        _print_done(env)
        return

    system_prompt, user_prompt = env.get_prompts()
    msg = {
        "type": "question",
        "step": env.current_step + 1,
        "total": env.total_steps,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "cumulative_score": env.cumulative_score,
    }
    print(json.dumps(msg))


def action_submit(args):
    """Submit a response for the current question, print result, save state."""
    env, state_path = _make_env(args)

    if env.done:
        _print_done(env)
        return

    response = args.response
    if response is None:
        # Try reading from stdin
        response = sys.stdin.read()

    record = env.step(response or "", outcome_override=getattr(args, "outcome_override", None))

    result_msg = {
        "type": "result",
        "step": record.step_number,
        "outcome": record.outcome,
        "score_delta": record.score_delta,
        "cumulative_score": record.cumulative_score,
        "parsed_answer": record.parsed_answer,
    }
    print(json.dumps(result_msg))

    _save(env, state_path, args)

    # Append to results JSONL
    if args.save_path:
        os.makedirs(os.path.dirname(args.save_path) or ".", exist_ok=True)
        with open(args.save_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def action_status(args):
    """Print current environment status."""
    env, state_path = _make_env(args)
    correct = sum(1 for r in env.history if r.outcome == "correct")
    incorrect = sum(1 for r in env.history if r.outcome == "incorrect")
    skipped = sum(1 for r in env.history if r.outcome == "skipped")
    msg = {
        "type": "status",
        "done": env.done,
        "current_step": env.current_step,
        "total_steps": env.total_steps,
        "cumulative_score": env.cumulative_score,
        "correct": correct,
        "incorrect": incorrect,
        "skipped": skipped,
    }
    print(json.dumps(msg))


def _print_done(env):
    correct = sum(1 for r in env.history if r.outcome == "correct")
    incorrect = sum(1 for r in env.history if r.outcome == "incorrect")
    skipped = sum(1 for r in env.history if r.outcome == "skipped")
    done_msg = {
        "type": "done",
        "final_score": env.cumulative_score,
        "summary": {
            "correct": correct,
            "incorrect": incorrect,
            "skipped": skipped,
            "total": env.total_steps,
        },
    }
    print(json.dumps(done_msg))


# --- Interactive stdin/stdout loop (original mode) ---

def run_agent_loop(args):
    env, state_path = _make_env(args)

    if args.save_path:
        os.makedirs(os.path.dirname(args.save_path) or ".", exist_ok=True)

    while not env.done:
        system_prompt, user_prompt = env.get_prompts()

        msg = {
            "type": "question",
            "step": env.current_step + 1,
            "total": env.total_steps,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "cumulative_score": env.cumulative_score,
        }
        print(json.dumps(msg), flush=True)

        line = sys.stdin.readline()
        if not line:
            _save(env, state_path, args)
            sys.exit(0)

        input_msg = json.loads(line.strip())
        model_response = input_msg["response"]

        record = env.step(model_response)

        result_msg = {
            "type": "result",
            "step": record.step_number,
            "outcome": record.outcome,
            "score_delta": record.score_delta,
            "cumulative_score": record.cumulative_score,
            "parsed_answer": record.parsed_answer,
        }
        print(json.dumps(result_msg), flush=True)

        _save(env, state_path, args)

        if args.save_path:
            with open(args.save_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    _print_done(env)


# --- CLI ---

def parse_args():
    parser = argparse.ArgumentParser(
        description="Agentic sequential environment (one-step CLI or interactive stdin/stdout)"
    )
    parser.add_argument("--data_file", type=str, default="omni_math_rule.jsonl")
    parser.add_argument("--save_path", type=str, default=None)
    parser.add_argument("--state", type=str, default=None,
                        help="Path to state file (default: derived from --save_path)")
    parser.add_argument("--num_questions", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--context_mode", type=str, default="summary",
                        choices=["full_trace", "summary"])
    parser.add_argument("--max_history_chars", type=int, default=0)
    parser.add_argument("--correct", type=int, default=1)
    parser.add_argument("--incorrect", type=int, default=-10)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--resume", action="store_true")

    # One-step CLI mode
    parser.add_argument("--action", type=str, default=None,
                        choices=["get_question", "submit", "status"],
                        help="One-step action (omit for interactive loop)")
    parser.add_argument("--response", type=str, default=None,
                        help="Model response text (for --action submit)")
    parser.add_argument("--outcome_override", type=str, default=None,
                        choices=["timed_out"],
                        help="Override outcome (for --action submit), e.g. timed_out")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.action == "get_question":
        action_get_question(args)
    elif args.action == "submit":
        action_submit(args)
    elif args.action == "status":
        action_status(args)
    else:
        run_agent_loop(args)
