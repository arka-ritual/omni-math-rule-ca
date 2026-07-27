#!/bin/bash
# The r_0 baseline on SWE-Bench Pro, for the NeurIPS 2026 rebuttal.
#
# r_0 := (s_c, s_a, s_i) = (+1, 0, 0) — the model is offered an abstain channel
# (`exit_abstain`), but submitting a wrong patch costs nothing. It is the
# quantitative no-consequence anchor Reviewers 27Kr and LswH asked for; the
# paper's SWE sweep starts at r_1.
#
# This is the SWE counterpart to inference/run_r0_math.sh, and it runs on Modal
# (`--runtime modal`) because a 5-model sweep of Docker-per-instance is not
# something a laptop can host.
#
# BREADTH-FIRST BY DESIGN
# -----------------------
# Modal bills sandbox wall-clock and the budget is finite, so instead of
# finishing one model at a time this walks all 5 models at N=20, then all 5 at
# N=40, and so on toward --target. Between rounds it prints spend so far.
#
# The point: if the budget runs out mid-sweep you are left with an equal-N row
# for every model — a usable table — rather than two complete models and three
# empty ones. Sampling is shuffle-then-slice on a fixed seed, so N=20 is a
# strict prefix of N=40 and each round only pays for the *new* instances.
# Nothing is redone.
#
# Note that `--workers` buys wall-clock, not budget: Modal charges per
# sandbox-second, so 8 concurrent sandboxes for an hour cost the same as 8
# sequential ones. Use it to finish sooner, not to spend less.
#
# Usage:
#   bash swebench_pro/run_r0.sh                        # rounds 20,40,60,80,100
#   bash swebench_pro/run_r0.sh --target 40            # stop after N=40
#   bash swebench_pro/run_r0.sh --rounds "10 25"       # custom ladder
#   bash swebench_pro/run_r0.sh --model openrouter/openai/gpt-5.4-nano
#   bash swebench_pro/run_r0.sh --no-eval              # inference only
#
# Env-var defaults (CLI wins):
#   WORKERS         parallel agents per cell   (default 8)
#   EVAL_WORKERS    parallel graders per cell  (default 8)
#   SEED            shuffle seed               (default 100)
#   TARGET          final N per model          (default 100)
#   ROUNDS          ladder of N values         (default "20 40 60 80 100")
#   REASONING_EFFORT                            (default medium — matches the
#                   paper's other SWE cells; do not change it casually, it
#                   changes both behaviour and cost)
#
# Every exit path — success, failure, Ctrl-C — runs modal_teardown.py, because
# a leaked sandbox bills until something kills it.

set -euo pipefail

cd "$(dirname "$0")/.."

WORKERS="${WORKERS:-8}"
EVAL_WORKERS="${EVAL_WORKERS:-8}"
SEED="${SEED:-100}"
TARGET="${TARGET:-100}"
ROUNDS="${ROUNDS:-}"
REASONING_EFFORT="${REASONING_EFFORT:-medium}"
RESULTS_ROOT="${RESULTS_ROOT:-swebench_pro/results}"
DO_EVAL=1
ONLY_MODEL=""

# r_0 rubric.
RC=1; RI=0; RA=0

usage () { sed -n '1,46p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --model)          ONLY_MODEL="$2"; shift 2 ;;
        --target)         TARGET="$2"; shift 2 ;;
        --rounds)         ROUNDS="$2"; shift 2 ;;
        --workers)        WORKERS="$2"; shift 2 ;;
        --eval-workers)   EVAL_WORKERS="$2"; shift 2 ;;
        --seed)           SEED="$2"; shift 2 ;;
        --reasoning-effort) REASONING_EFFORT="$2"; shift 2 ;;
        --no-eval)        DO_EVAL=0; shift ;;
        -h|--help)        usage ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

# Build the ladder if not given explicitly, capped at TARGET.
if [ -z "$ROUNDS" ]; then
    ROUNDS=""
    for n in 20 40 60 80 100; do
        [ "$n" -lt "$TARGET" ] && ROUNDS="$ROUNDS $n"
    done
    ROUNDS="$ROUNDS $TARGET"
fi

# litellm slugs. Everything goes through OpenRouter — it is the only key
# available (see inference/run_r0_math.sh for the same constraint on the math
# side, including why DeepSeek is not pinned to a specific upstream).
MODELS=(
    "openrouter/anthropic/claude-haiku-4.5"
    "openrouter/openai/gpt-5.4-nano"
    "openrouter/google/gemini-3.1-flash-lite-preview"
    "openrouter/deepseek/deepseek-v4-pro"
    "openrouter/qwen/qwen3.5-397b-a17b"
)

slug () { local s="$1"; s="${s//\//_}"; s="${s//:/_}"; echo "$s"; }

# Output dirs deliberately omit the usual `_n<N>` suffix: N grows between
# rounds, and a changing directory name would defeat resume (which keys on the
# instance ids already in <output>/preds.json).
out_dir_for () { echo "${RESULTS_ROOT}/$(slug "$1")_int5_quant${RC}_${RI}_${RA}"; }

# DANGER: this teardown kills EVERY sandbox in the project's Modal apps, not
# just the ones this process started — Modal gives no way to attribute a
# sandbox to a caller. That is what you want for a single sequential sweep (it
# is the backstop against leaks), but it means **you must not run two copies of
# this script at once**: whichever finishes first will tear down the other's
# in-flight instances.
#
# To run models concurrently, call swebench_pro/run.sh per model instead (it
# installs no trap) and run modal_teardown.py by hand at the end, or set
# NO_TEARDOWN=1 here and accept responsibility for cleanup.
NO_TEARDOWN="${NO_TEARDOWN:-0}"
teardown () {
    if [ "$NO_TEARDOWN" = "1" ]; then
        echo
        echo "[run_r0] NO_TEARDOWN=1 — leaving sandboxes running."
        echo "         Clean up with: python swebench_pro/scripts/modal_teardown.py"
        return
    fi
    echo
    echo "[run_r0] tearing down Modal sandboxes..."
    python swebench_pro/scripts/modal_teardown.py || true
}
trap teardown EXIT INT TERM

spend () {
    python -m modal billing summary 2>/dev/null \
        | grep -iE "metered|credits" || echo "  (billing summary unavailable)"
}

echo "=========================================================="
echo " SWE-Bench Pro r_0 sweep  (rubric: +${RC} correct / ${RA} abstain / ${RI} incorrect)"
echo "=========================================================="
echo "  models       : ${ONLY_MODEL:-all ${#MODELS[@]}}"
echo "  rounds (N)   :$ROUNDS   (target $TARGET)"
echo "  workers      : $WORKERS   eval_workers: $EVAL_WORKERS"
echo "  seed         : $SEED   reasoning: $REASONING_EFFORT"
echo "  runtime      : modal"
echo
echo "Spend before start:"
spend

for N in $ROUNDS; do
    echo
    echo "=========================================================="
    echo "[run_r0] ROUND N=$N  ($(date +%H:%M:%S))"
    echo "=========================================================="
    for model in "${MODELS[@]}"; do
        [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$model" ] && continue
        out="$(out_dir_for "$model")"
        echo
        echo "---- $model  ->  $out  (N=$N) ----"
        # --no-eval during the ladder: grading every round would re-grade
        # instances that already passed. Graded once at the end instead.
        bash swebench_pro/run.sh \
            --runtime modal \
            --model "$model" \
            --output "$out" \
            --n "$N" \
            --seed "$SEED" \
            --workers "$WORKERS" \
            --eval-workers "$EVAL_WORKERS" \
            --reasoning-effort "$REASONING_EFFORT" \
            --intervention 5 \
            --prompt-config quant \
            --rc "$RC" --ri "$RI" --ra "$RA" \
            --no-eval
    done

    echo
    echo "[run_r0] spend after round N=$N:"
    spend
    echo "[run_r0] If credit is running low, stop here — every model has N=$N,"
    echo "         which is a complete equal-N table. Re-run later to extend."
done

if [ "$DO_EVAL" -eq 1 ]; then
    echo
    echo "=========================================================="
    echo "[run_r0] grading all cells with the official evaluator"
    echo "=========================================================="
    for model in "${MODELS[@]}"; do
        [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$model" ] && continue
        out="$(out_dir_for "$model")"
        [ -f "$out/preds.json" ] || { echo "skip (no preds): $out"; continue; }
        echo
        echo "---- grading $out ----"
        bash swebench_pro/scripts/run_eval.sh "$out" \
            --workers "$EVAL_WORKERS" --modal
    done
fi

echo
echo "[run_r0] done. Summarize with:"
echo "    python scripts/swe_summarize_cells.py --glob '*_int5_quant1_0_0*'"
echo
echo "Final spend:"
spend
