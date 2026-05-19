#!/bin/bash
# Run the official SWE-bench Pro evaluation harness on a mini-swe-agent rundir.
#
# Pipeline:
#   1. Ensure swebench_pro/external/SWE-bench_Pro-os is cloned.
#   2. Convert <rundir>/preds.json -> <rundir>/eval/patches_for_eval.json
#      (adds the `instance_` prefix expected by the upstream harness).
#      With --gold, instead extract gold patches from the HF dataset.
#   3. Build <rundir>/eval/eval_data.jsonl from the upstream
#      `helper_code/sweap_eval_full_v2.jsonl` (filter + key rename).
#   4. cd into the upstream repo and invoke swe_bench_pro_eval.py with
#      --use_local_docker.
#
# Output:
#   <rundir>/eval/eval_results.json    -- {instance_id: bool} pass/fail
#   <rundir>/eval/instance_<id>/...    -- per-instance logs and outputs
#
# Usage:
#   bash swebench_pro/scripts/run_eval.sh <rundir> [--workers N] [--gold]
#       [--dockerhub-username jefzda] [--block-network]

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <rundir> [--workers N] [--gold] [--dockerhub-username U] [--block-network]" >&2
    exit 2
fi

RUNDIR_ARG="$1"; shift
WORKERS="${WORKERS:-1}"
GOLD=0
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-jefzda}"
BLOCK_NETWORK=""

while [ $# -gt 0 ]; do
    case "$1" in
        --workers)              WORKERS="$2"; shift 2 ;;
        --gold)                 GOLD=1; shift ;;
        --dockerhub-username)   DOCKERHUB_USERNAME="$2"; shift 2 ;;
        --block-network)        BLOCK_NETWORK="--block_network"; shift ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
SWEBENCH_PRO_DIR="$(cd "$HERE/.." && pwd)"
RUNDIR="$(cd "$RUNDIR_ARG" && pwd)"
UPSTREAM="$SWEBENCH_PRO_DIR/external/SWE-bench_Pro-os"

# 1. Setup upstream repo if missing.
bash "$HERE/setup_eval_repo.sh"

# 2. Build patches_for_eval.json.
mkdir -p "$RUNDIR/eval"
if [ "$GOLD" -eq 1 ]; then
    echo "[eval] Extracting gold patches from HuggingFace (ScaleAI/SWE-bench_Pro)"
    python "$UPSTREAM/helper_code/extract_gold_patches.py" \
        --output "$RUNDIR/eval/patches_for_eval.json"
else
    echo "[eval] Converting preds.json -> patches_for_eval.json"
    python "$HERE/preds_to_eval_input.py" "$RUNDIR"
fi

# Short-circuit: if no patches survived (e.g. every instance abstained,
# or every instance crashed before producing a patch), skip the upstream
# evaluator. It would otherwise divide by zero on
#   `sum(eval_results.values()) / len(eval_results)`
# and exit 1, breaking the orchestrator (run_interventions.sh) for what
# is actually a legitimate, well-behaved outcome.
NPATCHES="$(python -c "import json; print(len(json.load(open('$RUNDIR/eval/patches_for_eval.json'))))")"
if [ "$NPATCHES" -eq 0 ]; then
    echo "[eval] 0 patches to evaluate (every instance abstained or produced no patch)."
    echo "[eval] Skipping upstream swe_bench_pro_eval.py and writing empty eval_results.json."
    echo '{}' > "$RUNDIR/eval/eval_results.json"
    echo
    echo "[eval] Done."
    echo "  results: $RUNDIR/eval/eval_results.json   (empty — see preds.json + skipped_empty.txt)"
    exit 0
fi

# 3. Build per-rundir normalized eval data.
echo "[eval] Building eval_data.jsonl from upstream sweap_eval_full_v2.jsonl"
if [ "$GOLD" -eq 1 ]; then
    # Use the ids that ended up in patches_for_eval.json (upstream uses prefixed ids).
    python -c "
import json, sys
ids = [p['instance_id'] for p in json.load(open('$RUNDIR/eval/patches_for_eval.json'))]
sys.stdout.write('\n'.join(ids))
" > "$RUNDIR/eval/_ids.txt"
    python "$HERE/build_eval_data.py" --ids "$RUNDIR/eval/_ids.txt" \
        --upstream "$UPSTREAM" --output "$RUNDIR/eval/eval_data.jsonl"
else
    python "$HERE/build_eval_data.py" "$RUNDIR" --upstream "$UPSTREAM"
fi

# 4. Run the official eval (must be invoked from inside upstream repo
#    because it reads dockerfiles/ relative to cwd).
echo "[eval] Running swe_bench_pro_eval.py (workers=$WORKERS, dockerhub_username=$DOCKERHUB_USERNAME)"
(
    cd "$UPSTREAM"
    python swe_bench_pro_eval.py \
        --raw_sample_path "$RUNDIR/eval/eval_data.jsonl" \
        --patch_path "$RUNDIR/eval/patches_for_eval.json" \
        --output_dir "$RUNDIR/eval" \
        --scripts_dir run_scripts \
        --num_workers "$WORKERS" \
        --dockerhub_username "$DOCKERHUB_USERNAME" \
        --use_local_docker \
        $BLOCK_NETWORK
)

echo
echo "[eval] Done."
echo "  results: $RUNDIR/eval/eval_results.json"
echo "  per-instance: $RUNDIR/eval/instance_<id>/"
