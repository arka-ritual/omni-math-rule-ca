#!/bin/bash
# Grade every SWE-Bench Pro r_0 cell with the official evaluator on Modal.
#
# Inference is already done and lives in swebench_pro/results/*_int5_quant1_0_0/.
# This runs only the grading half, which is the cheap half: measured at
# ~$0.013 per instance (vs ~$0.05 for inference), because the grader just
# applies the patch and runs the repo's test suites.
#
# Grading is idempotent per cell — it rebuilds patches_for_eval.json from
# preds.json each time — so re-running after a partial pass simply re-grades.
# There is no incremental mode upstream.
#
# Usage:
#   bash swebench_pro/run_grade_all.sh                    # all r_0 cells
#   bash swebench_pro/run_grade_all.sh --workers 16
#   bash swebench_pro/run_grade_all.sh --cell openrouter_openai_gpt-5.4-nano_int5_quant1_0_0
#   bash swebench_pro/run_grade_all.sh --local            # local Docker instead of Modal
#
# Env: WORKERS (default 8), GLOB (default '*_int5_quant1_0_0')
#
# Modal workspace: whichever profile is active (`modal profile list`). Grading
# sandboxes land in the upstream-hardcoded `swe-bench-pro-eval` app, which
# `scripts/modal_teardown.py` also sweeps.

set -uo pipefail

cd "$(dirname "$0")/.."

WORKERS="${WORKERS:-8}"
GLOB="${GLOB:-*_int5_quant1_0_0}"
BACKEND="--modal"
ONLY_CELL=""

while [ $# -gt 0 ]; do
    case "$1" in
        --workers) WORKERS="$2"; shift 2 ;;
        --cell)    ONLY_CELL="$2"; shift 2 ;;
        --glob)    GLOB="$2"; shift 2 ;;
        --local)   BACKEND=""; shift ;;
        -h|--help) sed -n '1,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

# Teardown kills every sandbox in BOTH project apps — Modal offers no way to
# attribute a sandbox to a caller. Set NO_TEARDOWN=1 when an inference run is
# in flight at the same time, or grading will terminate its containers.
NO_TEARDOWN="${NO_TEARDOWN:-0}"
teardown () {
    if [ "$NO_TEARDOWN" = "1" ]; then
        echo
        echo "[grade] NO_TEARDOWN=1 — leaving sandboxes running."
        echo "        Clean up later with: python swebench_pro/scripts/modal_teardown.py"
        return
    fi
    echo
    echo "[grade] tearing down Modal sandboxes..."
    python swebench_pro/scripts/modal_teardown.py || true
}
trap teardown EXIT INT TERM

echo "[grade] active Modal profile:"
python -m modal profile list 2>/dev/null | sed 's/^/    /' || true
echo "[grade] workers=$WORKERS backend=${BACKEND:-local-docker}"

failed=()
graded=()
for d in swebench_pro/results/$GLOB; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"
    [ -n "$ONLY_CELL" ] && [ "$ONLY_CELL" != "$name" ] && continue
    [ -f "$d/preds.json" ] || { echo "[grade] skip (no preds.json): $name"; continue; }

    echo
    echo "=========================================================="
    echo "[grade] $name  ($(date +%H:%M:%S))"
    echo "=========================================================="
    if bash swebench_pro/scripts/run_eval.sh "$d" --workers "$WORKERS" $BACKEND; then
        graded+=("$name")
    else
        echo "[grade] FAILED: $name"
        failed+=("$name")
    fi
done

echo
echo "[grade] done. graded=${#graded[@]} failed=${#failed[@]}"
for f in "${failed[@]:-}"; do [ -n "$f" ] && echo "    FAILED: $f"; done
echo
echo "Summarize with:"
echo "    python scripts/swe_summarize_cells.py --glob '*quant1_0_0*'"
