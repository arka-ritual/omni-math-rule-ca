#!/bin/bash
# Smoke test for the vanilla mini-swe-agent SWE-bench Pro setup.
# Runs Pro instances through your chosen model with the stock config,
# then evaluates the produced patches with the official SWE-bench Pro
# Docker eval harness.
#
# Pipeline:
#   1. Inference: run_mini_on_pro.py -> <output>/preds.json
#   2. Evaluation (official): scripts/run_eval.sh -> <output>/eval/eval_results.json
#
# Prereqs:
#   - pip install -r requirements.txt
#   - Docker installed and running (`docker --version` works)
#   - Relevant API key in env or in `.env` at the repo root, e.g.
#       ANTHROPIC_API_KEY=...   OPENAI_API_KEY=...   OPENROUTER_API_KEY=...
#       GEMINI_API_KEY=...
#     The driver loads `.env` from the repo root before importing litellm.
#
# Usage:
#   bash swebench_pro/run_smoke.sh                                       # defaults
#   bash swebench_pro/run_smoke.sh --model openai/gpt-5-nano
#   bash swebench_pro/run_smoke.sh --model openai/gpt-5-nano \
#                                  --instances swebench_pro/data/smoke.jsonl \
#                                  --n-instances 5 --workers 2 --eval-workers 4
#   bash swebench_pro/run_smoke.sh --no-eval                             # skip eval
#   bash swebench_pro/run_smoke.sh --eval-only --rundir swebench_pro/results/smoke_<ts>
#   bash swebench_pro/run_smoke.sh --gold-eval                           # eval gold patches (sanity)
#
# Env-var defaults (CLI flag wins): MODEL, CONFIG, INSTANCES, N_INSTANCES,
# WORKERS, EVAL_WORKERS, OUTPUT, DOCKERHUB_USERNAME

set -euo pipefail

cd "$(dirname "$0")/.."

MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"
INSTANCES="${INSTANCES:-swebench_pro/data/smoke_1.jsonl}"
WORKERS="${WORKERS:-1}"
N_INSTANCES="${N_INSTANCES:-0}"
EVAL_WORKERS="${EVAL_WORKERS:-1}"
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-jefzda}"
TS="$(date +%Y%m%d_%H%M%S)"
OUTPUT="${OUTPUT:-swebench_pro/results/smoke_${TS}}"
CONFIG="${CONFIG:-swebench_pro/configs/swebench_pro_vanilla.yaml}"

DO_INFER=1
DO_EVAL=1
GOLD_EVAL=0
RUNDIR_OVERRIDE=""

usage () {
    sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --model)              MODEL="$2"; shift 2 ;;
        --config)             CONFIG="$2"; shift 2 ;;
        --instances)          INSTANCES="$2"; shift 2 ;;
        --n-instances)        N_INSTANCES="$2"; shift 2 ;;
        --workers)            WORKERS="$2"; shift 2 ;;
        --eval-workers)       EVAL_WORKERS="$2"; shift 2 ;;
        --output)             OUTPUT="$2"; shift 2 ;;
        --rundir)             RUNDIR_OVERRIDE="$2"; shift 2 ;;
        --dockerhub-username) DOCKERHUB_USERNAME="$2"; shift 2 ;;
        --no-eval)            DO_EVAL=0; shift ;;
        --eval-only)          DO_INFER=0; shift ;;
        --gold-eval)          DO_INFER=0; GOLD_EVAL=1; shift ;;
        -h|--help)            usage ;;
        --)                   shift; break ;;
        -*) echo "Unknown flag: $1" >&2; echo "Run with --help." >&2; exit 2 ;;
        *)  echo "Unexpected positional: $1" >&2; exit 2 ;;
    esac
done

if [ "$DO_INFER" -eq 0 ] && [ -n "$RUNDIR_OVERRIDE" ]; then
    OUTPUT="$RUNDIR_OVERRIDE"
fi

echo "Smoke run config:"
echo "  model         = $MODEL"
echo "  config        = $CONFIG"
echo "  instances     = $INSTANCES (limit=$N_INSTANCES)"
echo "  workers       = $WORKERS"
echo "  output        = $OUTPUT"
echo "  do_infer      = $DO_INFER"
echo "  do_eval       = $DO_EVAL"
echo "  gold_eval     = $GOLD_EVAL"
echo "  eval_workers  = $EVAL_WORKERS"
echo "  dockerhub_user= $DOCKERHUB_USERNAME"

mkdir -p "$OUTPUT"

# 1. Inference.
if [ "$DO_INFER" -eq 1 ]; then
    EXTRA=()
    if [ "$N_INSTANCES" -gt 0 ]; then
        EXTRA+=(--limit "$N_INSTANCES")
    fi
    python swebench_pro/run_mini_on_pro.py \
        --model "$MODEL" \
        --config "$CONFIG" \
        --instances "$INSTANCES" \
        --output "$OUTPUT" \
        --workers "$WORKERS" \
        "${EXTRA[@]}"
else
    echo "[run_smoke] skipping inference (--eval-only / --gold-eval)"
fi

# 2. Evaluation.
if [ "$DO_EVAL" -eq 1 ] || [ "$GOLD_EVAL" -eq 1 ]; then
    EVAL_FLAGS=(--workers "$EVAL_WORKERS" --dockerhub-username "$DOCKERHUB_USERNAME")
    if [ "$GOLD_EVAL" -eq 1 ]; then
        EVAL_FLAGS+=(--gold)
    fi
    bash swebench_pro/scripts/run_eval.sh "$OUTPUT" "${EVAL_FLAGS[@]}"
else
    echo "[run_smoke] skipping evaluation (--no-eval)"
fi

echo
echo "Done. Outputs in: $OUTPUT"
echo "  preds.json                                       -- instance_id -> submitted patch"
echo "  exit_statuses.yaml                               -- per-instance agent exit_status"
echo "  minisweagent.log                                 -- driver log"
echo "  <bare_id>/<bare_id>.traj.json                    -- full agent trajectory"
if [ "$DO_EVAL" -eq 1 ] || [ "$GOLD_EVAL" -eq 1 ]; then
    echo "  eval/eval_results.json                           -- {instance_id: bool} resolved"
    echo "  eval/instance_<bare_id>/mini_stdout.log          -- test-run stdout"
    echo "  eval/instance_<bare_id>/mini_stderr.log          -- test-run stderr"
    echo "  eval/instance_<bare_id>/mini_output.json         -- per-test PASSED/FAILED"
    echo "  eval/instance_<bare_id>/mini_patch.diff          -- patch handed to git apply"
    echo "  eval/instance_<bare_id>/mini_entryscript.sh      -- script run inside the test container"
    echo
    echo "Note: <bare_id> is the instance id WITHOUT the leading 'instance_' prefix"
    echo "      (the eval dir uses the full prefixed id; the trajectory dir uses the bare id)."
    echo "      Concrete example for this run:"
    if [ -f "$OUTPUT/eval/eval_results.json" ]; then
        first_iid="$(python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(next(iter(d)))' "$OUTPUT/eval/eval_results.json" 2>/dev/null || true)"
        first_resolved="$(python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(next(iter(d.values())))' "$OUTPUT/eval/eval_results.json" 2>/dev/null || true)"
        if [ -n "${first_iid:-}" ]; then
            echo "        $OUTPUT/eval/$first_iid/"
            echo "        resolved = $first_resolved"
        fi
    fi
fi
