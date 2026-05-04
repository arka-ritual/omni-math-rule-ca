#!/bin/bash
# Re-run evaluation/math_eval_cautious.py over every intervention rundir
# in parallel batches, after fixes to the cautious classifier:
#
#   1. Multi-turn (int2/int3): grade only the LAST \boxed{...} value, so
#      that the decision turn quoting an earlier turn's answer in prose
#      (e.g. "your previous answer was \\boxed{6}, but I'll abstain
#       \\boxed{UNSURE}") no longer falsely registers as
#      `incorrect_mixed`.
#   2. is_unsure() now accepts LaTeX-wrapped variants (\\text{UNSURE},
#      \\textbf{UNSURE}, \\mathrm{UNSURE}, ...) — previously
#      `\\boxed{\\text{UNSURE}}` extracted to `\\text{UNSURE}` and got
#      graded as `incorrect_standard` instead of `abstained`. This
#      affects all interventions (1/2/3/4), not just multi-turn.
#
# Usage:
#   bash evaluation/sh/reeval_interventions_cautious.sh
#   PARALLEL=8 bash evaluation/sh/reeval_interventions_cautious.sh
#   bash evaluation/sh/reeval_interventions_cautious.sh --only-multi-turn

set -euo pipefail

cd "$(dirname "$0")/../.."

PARALLEL="${PARALLEL:-6}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/interventions}"
EVAL_DIR="${EVAL_DIR:-evaluation/output/interventions}"
ONLY_MULTI_TURN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --only-multi-turn) ONLY_MULTI_TURN=1; shift ;;
        --parallel)        PARALLEL="$2"; shift 2 ;;
        --results-dir)     RESULTS_DIR="$2"; shift 2 ;;
        --eval-dir)        EVAL_DIR="$2"; shift 2 ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

mapfile -t files < <(ls "$RESULTS_DIR"/*.jsonl 2>/dev/null | sort)
[ "${#files[@]}" -eq 0 ] && { echo "No JSONL files in $RESULTS_DIR"; exit 1; }

if [ "$ONLY_MULTI_TURN" -eq 1 ]; then
    filtered=()
    for f in "${files[@]}"; do
        case "$f" in
            *_int2_*|*_int3_*) filtered+=("$f") ;;
        esac
    done
    files=("${filtered[@]}")
fi

echo "Re-evaluating ${#files[@]} cell(s) with parallelism=$PARALLEL"
echo

run_one () {
    local data="$1"
    local stem
    stem=$(basename "$data" .jsonl)
    local out="$EVAL_DIR/${stem}"
    python evaluation/math_eval_cautious.py \
        --data_file "$data" \
        --output_dir "$out" \
        > "$out/_reeval.log" 2>&1
    if [ "$?" -eq 0 ]; then
        echo "OK   $stem"
    else
        echo "FAIL $stem  (see $out/_reeval.log)"
    fi
}

export -f run_one
export EVAL_DIR

# Make sure all output dirs exist so > redirection in run_one doesn't fail
for f in "${files[@]}"; do
    stem=$(basename "$f" .jsonl)
    mkdir -p "$EVAL_DIR/$stem"
done

printf '%s\n' "${files[@]}" | xargs -n 1 -P "$PARALLEL" -I {} bash -c 'run_one "$@"' _ {}

echo
echo "Done. Per-cell logs at $EVAL_DIR/*/  _reeval.log"
