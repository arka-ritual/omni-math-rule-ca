#!/usr/bin/env python3
"""Build SFT/DPO/SFT-box training files for abstention fine-tuning.

Axes:
  --sizes               total #examples per file (e.g. 250 500 1000)
  --abstention_fractions fraction of rows whose target is the abstention string
                        (i.e. fraction sourced from "incorrect" labels). Default 0.5.
  --rubrics             one or more rubric prompt names from inference/prompts.py
                        (e.g. quant_m25 quant_m100), OR a registered mix-rubric
                        from MIX_RUBRICS (e.g. mix_m25_m100) which samples each
                        row's system prompt across multiple rubrics.
  --prefix_ks           how many tokens of the model's own pre-answer reasoning to
                        keep before the abstention string (e.g. 512 1024).

Output filename:
  {method}_n{N}_{rubric}_k{K}_p{PP}.jsonl
where PP = round(abstention_fraction * 100). For backward compat, p50 file content
is identical (modulo determinism/seed) to the previous fixed 50/50 build.
"""
import argparse
import json
import re
import os
import random
import sys

from transformers import AutoTokenizer

FIXED_ABSTENTION = """I am not sufficiently confident that I can answer this correctly under the stated scoring rubric. Since an incorrect answer is heavily penalized and abstaining receives 0, I will abstain.

\\boxed{UNSURE}"""


# Registered mixtures: rubric_name -> list of base rubric names sampled uniformly.
# Add more here when needed; aggregator parsing matches "mix_*" by prefix.
MIX_RUBRICS = {
    "mix_m25_m100": ["quant_m25", "quant_m100"],
}


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def problem(row):
    return row.get("problem", row.get("question"))


def _collect_boxed_spans(text):
    spans = []
    for m in re.finditer(r"\\boxed\s*\{|(?<![A-Za-z])boxed\s*\{", text):
        open_i = text.find("{", m.start())
        if open_i < 0:
            continue
        depth = 1
        value = ""
        for i, c in enumerate(text[open_i + 1:], start=open_i + 1):
            if c == "{":
                depth += 1
                value += c
            elif c == "}":
                depth -= 1
                if depth == 0:
                    value = value.strip()
                    if value.upper() != "UNSURE":
                        spans.append((m.start(), i + 1, value))
                    break
                value += c
            else:
                value += c
    return spans


_THINK_END_TOKENS = ["</think>", "<channel|>"]


def final_answer_span(text):
    """Last non-UNSURE \\boxed{} in the visible response (after thinking block).
    Falls back to last non-UNSURE \\boxed{} in the full text."""
    all_spans = _collect_boxed_spans(text)
    if not all_spans:
        return None
    think_end = -1
    for tok in _THINK_END_TOKENS:
        pos = text.rfind(tok)
        if pos != -1:
            think_end = max(think_end, pos + len(tok))
    if think_end != -1:
        visible = [s for s in all_spans if s[0] > think_end]
        if visible:
            return visible[-1]
    return all_spans[-1]


def answer_span(row):
    gen = row.get("model_generation", "") or ""
    return final_answer_span(gen)


def attempted_completion(row):
    gen = row.get("model_generation", "") or ""
    span = final_answer_span(gen)
    if span is not None:
        _, end, _ = span
        return gen[:end].rstrip()
    ans = row.get("extracted_answer")
    if not ans:
        return gen.rstrip()
    return gen.rstrip() + f"\n\n\\boxed{{{ans}}}"


def reasoning_before_answer(row):
    gen = row.get("model_generation", "") or ""
    span = answer_span(row)
    if span is None:
        return gen.rstrip()
    start, _, _ = span
    return gen[:start].rstrip()


def prefix_tokens(tokenizer, text, k):
    if k <= 0 or not text.strip():
        return ""
    ids = tokenizer(text, add_special_tokens=False)["input_ids"][:k]
    return tokenizer.decode(ids, skip_special_tokens=True).strip()


def abstention_completion(row, tokenizer, k):
    prefix = prefix_tokens(tokenizer, reasoning_before_answer(row), k)
    if prefix:
        return prefix.rstrip() + "\n\n" + FIXED_ABSTENTION
    return FIXED_ABSTENTION


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


def n_tokens(tokenizer, text):
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def target(row, tokenizer, k):
    if row["classification"] == "correct":
        return attempted_completion(row)
    return abstention_completion(row, tokenizer, k)


def _system_for_row(rubric, mix_components, row_idx, mix_seed):
    """For a fixed-rubric set, returns that rubric's prompt text. For a mix
    rubric, deterministically samples one of mix_components based on (row_idx, seed)."""
    if mix_components is None:
        return PROMPTS[rubric], rubric
    rng = random.Random(hash((mix_seed, row_idx)) & 0xFFFFFFFF)
    chosen = rng.choice(mix_components)
    return PROMPTS[chosen], chosen


def sft_row(row, system, rubric, tokenizer, k, row_rubric):
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": problem(row)},
            {"role": "assistant", "content": target(row, tokenizer, k)},
        ],
        "idx": row["idx"],
        "source_standard_correct": row["classification"] == "correct",
        "rubric": rubric,
        "row_rubric": row_rubric,
        "train_rubric": rubric,
        "prefix_k": k,
    }


def dpo_row(row, system, rubric, tokenizer, k, row_rubric):
    correct = row["classification"] == "correct"
    attempt = attempted_completion(row)
    abstain_k = abstention_completion(row, tokenizer, k)
    abstain_0 = abstention_completion(row, tokenizer, 0)

    if correct:
        chosen, rejected = attempt, abstain_0
    else:
        chosen, rejected = abstain_k, attempt

    return {
        "prompt": [
            {"role": "system", "content": system},
            {"role": "user", "content": problem(row)},
        ],
        "chosen": chosen,
        "rejected": rejected,
        "idx": row["idx"],
        "source_standard_correct": correct,
        "rubric": rubric,
        "row_rubric": row_rubric,
        "train_rubric": rubric,
        "prefix_k": k,
    }


def sft_box_row(row, system, rubric, tokenizer, k, row_rubric):
    correct = row["classification"] == "correct"
    full_assistant = target(row, tokenizer, k)
    if correct:
        gen = row.get("model_generation", "") or ""
        span = final_answer_span(gen)
        if span is not None:
            start, end, _ = span
            supervised_suffix = gen[start:end]
        else:
            ans = row.get("extracted_answer", "")
            supervised_suffix = f"\\boxed{{{ans}}}" if ans else full_assistant
    else:
        supervised_suffix = FIXED_ABSTENTION
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": problem(row)},
            {"role": "assistant", "content": full_assistant},
        ],
        "supervised_suffix": supervised_suffix,
        "idx": row["idx"],
        "source_standard_correct": correct,
        "rubric": rubric,
        "row_rubric": row_rubric,
        "train_rubric": rubric,
        "prefix_k": k,
    }


def fits_sft(tokenizer, row, system, k, max_len):
    full = render(
        tokenizer,
        sft_row(row, system, "tmp", tokenizer, k, "tmp")["messages"],
        add_generation_prompt=False,
    )
    return n_tokens(tokenizer, full) <= max_len - 256


def fits_dpo(tokenizer, row, system, k, max_len):
    ex = dpo_row(row, system, "tmp", tokenizer, k, "tmp")
    prompt_text = render(tokenizer, ex["prompt"], add_generation_prompt=True)
    return (
        n_tokens(tokenizer, prompt_text + ex["chosen"]) <= max_len - 256
        and n_tokens(tokenizer, prompt_text + ex["rejected"]) <= max_len - 256
    )


def select(rows, classification, seed):
    out = [r for r in rows if r["classification"] == classification]
    random.Random(seed).shuffle(out)
    return out


def _resolve_rubric(rubric_name):
    """Returns (canonical_name, mix_components_or_None, representative_system)."""
    if rubric_name in MIX_RUBRICS:
        components = MIX_RUBRICS[rubric_name]
        # Use the first component's prompt for length filtering as a representative
        # (mixes only differ in numeric penalty; lengths are nearly identical).
        return rubric_name, components, PROMPTS[components[0]]
    if rubric_name in PROMPTS:
        return rubric_name, None, PROMPTS[rubric_name]
    raise ValueError(
        f"Unknown rubric '{rubric_name}'. Add it to inference/prompts.py PROMPTS "
        f"or to MIX_RUBRICS in this file."
    )


def _build_split(rows, p_abst, n, seed):
    """Return (correct_subset, incorrect_subset) for one (n, p_abst) cell."""
    n_abst = int(round(n * p_abst))
    n_attempt = n - n_abst
    correct = select(rows, "correct", seed)
    incorrect = select(rows, "incorrect", seed)
    if len(correct) < n_attempt:
        raise AssertionError(
            f"Not enough correct examples: need {n_attempt}, have {len(correct)} "
            f"(n={n}, p_abst={p_abst})"
        )
    if len(incorrect) < n_abst:
        raise AssertionError(
            f"Not enough incorrect examples: need {n_abst}, have {len(incorrect)} "
            f"(n={n}, p_abst={p_abst})"
        )
    return correct[:n_attempt], incorrect[:n_abst], n_attempt, n_abst


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--labeled", required=True)
    p.add_argument("--model_slug", required=True)
    p.add_argument("--base_model", required=True)
    p.add_argument("--out_root", default="data/abstention_ft")
    p.add_argument("--max_seq_length", type=int, default=65536)
    p.add_argument("--sizes", type=int, nargs="+", default=[100])
    p.add_argument(
        "--abstention_fractions",
        type=float,
        nargs="+",
        default=[0.5],
        help="Fractions of rows whose target is the abstention string. "
             "E.g. 0.25 0.5 0.75. Each value produces its own output file.",
    )
    p.add_argument(
        "--rubrics",
        nargs="+",
        default=["quant_m25"],
        help="Rubric names from PROMPTS, or registered mix-rubric names "
             f"({sorted(MIX_RUBRICS)}).",
    )
    p.add_argument("--prefix_ks", type=int, nargs="+", default=[512, 1024])
    p.add_argument("--methods", nargs="+", default=["sft", "dpo", "sft_box"])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--mix_seed",
        type=int,
        default=1234,
        help="Seed for per-row rubric sampling within a mix rubric.",
    )
    p.add_argument(
        "--allow_partial",
        action="store_true",
        help="Skip (don't fail) cells whose label budget can't satisfy the requested "
             "(n, p_abst) split. Useful for grids that exceed the budget at extremes.",
    )
    args = p.parse_args()

    sys.path.insert(0, os.path.join(os.getcwd(), "inference"))
    from prompts import PROMPTS as _PROMPTS  # noqa: F401

    # Make PROMPTS visible to the helpers in this module.
    global PROMPTS
    PROMPTS = _PROMPTS

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    rows = [
        r for r in read_jsonl(args.labeled)
        if r.get("classification") in {"correct", "incorrect"}
    ]
    out_dir = os.path.join(args.out_root, args.model_slug)
    summary = {}

    method_specs = {
        "sft": (fits_sft, sft_row),
        "dpo": (fits_dpo, dpo_row),
        "sft_box": (fits_sft, sft_box_row),
    }
    for m in args.methods:
        if m not in method_specs:
            raise ValueError(f"Unknown method '{m}'. Known: {list(method_specs)}")

    for rubric_name in args.rubrics:
        canonical, mix_components, repr_system = _resolve_rubric(rubric_name)
        for k in args.prefix_ks:
            for method in args.methods:
                fits, make = method_specs[method]
                eligible = [
                    r for r in rows
                    if fits(tokenizer, r, repr_system, k, args.max_seq_length)
                ]
                key = f"{method}_{canonical}_k{k}"
                summary[key] = {
                    "eligible_correct": sum(
                        1 for r in eligible if r["classification"] == "correct"
                    ),
                    "eligible_incorrect": sum(
                        1 for r in eligible if r["classification"] == "incorrect"
                    ),
                    "cells": {},
                }

                for n in args.sizes:
                    for p_abst in args.abstention_fractions:
                        try:
                            attempt_subset, abstain_subset, n_attempt, n_abst = _build_split(
                                eligible, p_abst, n, args.seed
                            )
                        except AssertionError as e:
                            cell_name = f"n{n}_p{int(round(p_abst * 100)):02d}"
                            if args.allow_partial:
                                summary[key]["cells"][cell_name] = {"skipped": str(e)}
                                print(f"[skip] {key} {cell_name}: {e}", file=sys.stderr)
                                continue
                            print(json.dumps(summary, indent=2), file=sys.stderr)
                            raise

                        selected = attempt_subset + abstain_subset

                        out_rows = []
                        for r in selected:
                            sys_text, row_rubric = _system_for_row(
                                canonical, mix_components, r["idx"], args.mix_seed
                            )
                            out_rows.append(
                                make(r, sys_text, canonical, tokenizer, k, row_rubric)
                            )

                        random.Random(
                            hash((args.seed, n, int(p_abst * 100))) & 0xFFFFFFFF
                        ).shuffle(out_rows)

                        p_pct = int(round(p_abst * 100))
                        out_path = os.path.join(
                            out_dir,
                            f"{method}_n{n}_{canonical}_k{k}_p{p_pct:02d}.jsonl",
                        )
                        write_jsonl(out_rows, out_path)
                        summary[key]["cells"][f"n{n}_p{p_pct:02d}"] = {
                            "rows": len(out_rows),
                            "attempt_rows": n_attempt,
                            "abstain_rows": n_abst,
                            "path": out_path,
                        }

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "train_data_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
