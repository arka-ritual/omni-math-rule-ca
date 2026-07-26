#!/usr/bin/env python3
"""Zero-shot raw-completion arm: base vs matched instruct, no scaffolding.

Answers Reviewer pmhX:

    "Could you test variants less tied to instruction tuning (i.e. simpler
     prompting) to ensure robustness of the base versus instruction models?"

§6 of the paper compares base and instruct models using a 4-shot preamble with
an explicit `Q: / Thoughts: / Answer/Abstain decision: / Final Answer:`
structure. That scaffolding is itself instruction-like, so the reviewer's worry
is that the base-vs-instruct gap is an artifact of imposing it on a base model.

This strips the scaffolding to nothing. Every model — base *and* instruct — is
prompted through `/v1/completions` as raw autocomplete:

    <consequence text>\\n\\n<problem>

No chat template, no few-shot examples, no decision line. The matched instruct
arm is what makes it decisive: if the instruct models still refuse to abstain
under a prompt with zero instruction-tuned structure, the gap cannot be blamed
on the template.

Grid: 4 models × 9 framings, matching the paper's base-model grid so the
results drop into Fig 4 — 3 qualitative (ultra_cautious, QP4, QP7; note the
paper's table labels `ultra_cautious` as "QP1") and 6 quantitative rubrics.

Expect low boxing rates here — that is the point, and it is why every cell is
scored with both the standard evaluator and `scripts/analyze_boxing_rate.py`,
which separates "chose to abstain" from "never emitted a parseable answer".

COST: this stands up Modal GPUs. Weights are prefetched on CPU first so the
~62 GB Gemma download is not billed at GPU rates, and every server is torn down
in a `finally`. Run one model at a time (`--model`) if the budget is tight.

Usage:
    python inference/run_zeroshot_raw.py --prefetch-only
    python inference/run_zeroshot_raw.py --model Qwen/Qwen3.5-9B-Base
    python inference/run_zeroshot_raw.py --num-samples 20 --dry-cell   # smoke
    python inference/run_zeroshot_raw.py                               # full grid
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from modal_apps.vllm_sandbox import prefetch, serve  # noqa: E402

RESULTS_DIR = os.path.join("inference", "results", "zeroshot_raw")
EVAL_DIR = os.path.join("evaluation", "output", "zeroshot_raw")

# (hf_id, output slug, tuning). Slugs mirror the few-shot runs' naming so the
# two arms are easy to line up, but they live in their own directory so they
# can't collide.
MODELS = [
    ("Qwen/Qwen3.5-9B-Base", "Qwen3.5-9B-base", "base"),
    ("Qwen/Qwen3.5-9B", "Qwen3.5-9B", "instruct"),
    ("google/gemma-4-31b", "gemma-4-31b", "base"),
    ("google/gemma-4-31b-it", "gemma-4-31b-it", "instruct"),
]

# The paper's base-model grid. Quantitative cells are (r_correct, r_incorrect,
# r_abstain) and use the `_r{rc}_{ri}_{ra}` filename convention of
# inference/run_qwen35_9b.sh, so labels line up with the existing base runs.
QUALITATIVE = ["ultra_cautious", "QP4", "QP7"]
QUANTITATIVE = [
    (1, 0, 0),      # r_0      — no penalty at all
    (10, -1, 0),    # r_0.1
    (10, -5, 0),    # r_0.5
    (1, -1, 0),     # r_1
    (1, -10, 0),    # r_10
    (-1, -10, 10),  # r_abstain — abstaining is strictly dominant
]

# Raw autocomplete has no turn structure to stop on, so a base model will happily
# keep generating a new problem after answering. These cut that off; `max_tokens`
# is the real backstop.
STOP_SEQUENCES = ["\n\nProblem:", "\n\nQ:", "\nProblem:"]


def cell_name(prompt: str, rubric: tuple | None) -> str:
    if rubric is None:
        return prompt
    return "quantitative_grading_r{}_{}_{}".format(*rubric)


def run_cell(slug: str, base_url: str, model_id: str, prompt: str,
             rubric: tuple | None, args) -> bool:
    cell = cell_name(prompt, rubric)
    stem = f"{slug}-{cell}" + ("_SMOKE" if args.dry_cell else "")
    save_path = os.path.join(RESULTS_DIR, f"{stem}.jsonl")
    out_dir = os.path.join(EVAL_DIR, stem)

    cmd = [
        sys.executable, os.path.join("inference", "inference_api.py"),
        "--provider", "vllm",
        "--model", model_id,
        "--base_model",                 # force /v1/completions: raw, no chat template
        "--base_url", base_url,
        "--prompt", prompt,
        "--save_path", save_path,
        "--num_samples", str(args.num_samples),
        "--seed", str(args.seed),
        "--temperature", str(args.temperature),
        "--max_tokens", str(args.max_tokens),
        "--concurrency", str(args.concurrency),
    ]
    for s in STOP_SEQUENCES:
        cmd += ["--stop", s]
    if rubric is not None:
        rc, ri, ra = rubric
        cmd += ["--rubric_correct", str(rc),
                "--rubric_incorrect", str(ri),
                "--rubric_abstain", str(ra)]

    print(f"\n=== {slug} | {cell} ===", flush=True)
    if subprocess.run(cmd, cwd=REPO_ROOT).returncode != 0:
        print(f"!! inference failed for {stem}", flush=True)
        return False

    if not args.no_eval:
        subprocess.run(
            [sys.executable, os.path.join("evaluation", "math_eval_cautious.py"),
             "--data_file", save_path, "--output_dir", out_dir],
            cwd=REPO_ROOT, check=False,
        )
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", default=None,
                    help="HF id to restrict to; repeat for several.")
    ap.add_argument("--num-samples", type=int, default=100, dest="num_samples")
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--max-tokens", type=int, default=2048, dest="max_tokens",
                    help="Bounded because raw completions ramble and GPU time is "
                         "billed per second (default 2048).")
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--max-model-len", type=int, default=8192, dest="max_model_len")
    ap.add_argument("--gpu", default=None, help="Override the per-model GPU choice.")
    ap.add_argument("--prefetch-only", action="store_true",
                    help="Download weights into the cache Volume (CPU-only) and exit.")
    ap.add_argument("--no-eval", action="store_true")
    ap.add_argument("--dry-cell", action="store_true",
                    help="Suffix outputs with _SMOKE so a test run can't pollute results.")
    args = ap.parse_args()

    selected = [m for m in MODELS if not args.model or m[0] in args.model]
    if not selected:
        print(f"No model matched {args.model}. Known: {[m[0] for m in MODELS]}", file=sys.stderr)
        return 2

    os.makedirs(os.path.join(REPO_ROOT, RESULTS_DIR), exist_ok=True)
    os.makedirs(os.path.join(REPO_ROOT, EVAL_DIR), exist_ok=True)

    # Always prefetch first: downloading inside the GPU sandbox bills tens of GB
    # of transfer at GPU rates.
    for hf_id, _, _ in selected:
        prefetch(hf_id)
    if args.prefetch_only:
        return 0

    cells = [(p, None) for p in QUALITATIVE] + [("quantitative_grading", r) for r in QUANTITATIVE]
    failures = []
    for hf_id, slug, tuning in selected:
        print(f"\n{'=' * 70}\n{hf_id}  ({tuning})  — {len(cells)} cells\n{'=' * 70}", flush=True)
        # serve() tears the GPU down on every exit path, including exceptions.
        with serve(hf_id, gpu=args.gpu, max_model_len=args.max_model_len) as base_url:
            for prompt, rubric in cells:
                if not run_cell(slug, base_url, hf_id, prompt, rubric, args):
                    failures.append(f"{slug}/{cell_name(prompt, rubric)}")

    print("\nDone.")
    if failures:
        print(f"{len(failures)} cell(s) failed: {', '.join(failures)}")
    print("\nScore the boxing/abstention decomposition with:")
    print(f"    python scripts/analyze_boxing_rate.py --results_dir {RESULTS_DIR} "
          f"--eval_root {EVAL_DIR} --out_dir {EVAL_DIR}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
