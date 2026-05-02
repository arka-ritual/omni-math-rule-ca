#!/bin/bash
# Run mini-swe-agent on SWE-bench Pro instances and (optionally) grade
# the resulting patches with the official SWE-bench Pro Docker eval.
#
# Pipeline (default):
#   1. Inference: run_mini_on_pro.py over a shuffle-and-slice sample of
#      `data/swebench_pro_full.jsonl`, writing <output>/preds.json.
#      Fully resumable: re-running the same command (or with a larger
#      --n) skips instances already in preds.json.
#   2. Evaluation (official): scripts/run_eval.sh -> <output>/eval/eval_results.json
#
# Prereqs:
#   - pip install -r requirements.txt
#   - Docker installed and running (`docker --version` works)
#   - Relevant API key in env or in `.env` at the repo root, e.g.
#       ANTHROPIC_API_KEY=...   OPENAI_API_KEY=...   OPENROUTER_API_KEY=...
#       GEMINI_API_KEY=...
#
# Usage:
#   bash swebench_pro/run.sh --model openai/gpt-5-nano --n 1
#   bash swebench_pro/run.sh --model anthropic/claude-haiku-4-5-20251001 \
#                            --n 100 --workers 4 --eval-workers 8 \
#                            --output swebench_pro/results/haiku_n100
#   bash swebench_pro/run.sh --model openai/gpt-5-nano --n 50  # resume / extend a prior run
#
#   bash swebench_pro/run.sh --no-eval                          # inference only
#   bash swebench_pro/run.sh --eval-only --rundir <path>        # eval an existing rundir
#   bash swebench_pro/run.sh --gold-eval                        # grade gold patches (sanity check)
#
# Notes on resumability:
#   - Sampling is "shuffle-then-slice" with a fixed seed (default 100).
#     With the same seed, --n=20 is a strict prefix of --n=100, so an
#     interrupted run resumes exactly. To force fresh sampling, pass
#     --seed <n> with a different value (and a different --output).
#   - Resume is keyed on the instance ids already in <output>/preds.json.
#
# Consequence-asymmetry interventions (mirrors inference/run_interventions.sh):
#   --intervention {0,1,2,3}        0 = vanilla (no CA framing). Default 0.
#   --prompt-config {none,quant,qp6,qp7}
#                                   none + intervention 0 = vanilla
#                                   quant requires --rc/--ri/--ra
#                                   qp6/qp7 use the qualitative paragraphs
#                                   from the paper (no rubric needed).
#   --rc / --ri / --ra              quantitative rubric values (correct,
#                                   incorrect, abstain).
#
# Env-var defaults (CLI flag wins): MODEL, CONFIG, INSTANCES, N, SEED,
# WORKERS, EVAL_WORKERS, OUTPUT, DOCKERHUB_USERNAME, INTERVENTION,
# PROMPT_CONFIG, RC, RI, RA

set -euo pipefail

cd "$(dirname "$0")/.."

MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"
INSTANCES="${INSTANCES:-swebench_pro/data/swebench_pro_full.jsonl}"
WORKERS="${WORKERS:-1}"
N="${N:-0}"                                  # 0 means "all"
SEED="${SEED:-100}"
EVAL_WORKERS="${EVAL_WORKERS:-1}"
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-jefzda}"
OUTPUT="${OUTPUT:-}"                         # default derived from model + N below
CONFIG="${CONFIG:-swebench_pro/configs/swebench_pro_vanilla.yaml}"
INTERVENTION="${INTERVENTION:-0}"
PROMPT_CONFIG="${PROMPT_CONFIG:-none}"
RC="${RC:-}"
RI="${RI:-}"
RA="${RA:-}"
API_TIMEOUT="${API_TIMEOUT:-600}"
REASONING_EFFORT="${REASONING_EFFORT:-medium}"

DO_INFER=1
DO_EVAL=1
GOLD_EVAL=0
RUNDIR_OVERRIDE=""

usage () {
    sed -n '1,55p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --model)              MODEL="$2"; shift 2 ;;
        --config)             CONFIG="$2"; shift 2 ;;
        --instances)          INSTANCES="$2"; shift 2 ;;
        --n|--num-samples)    N="$2"; shift 2 ;;
        --seed)               SEED="$2"; shift 2 ;;
        --workers)            WORKERS="$2"; shift 2 ;;
        --eval-workers)       EVAL_WORKERS="$2"; shift 2 ;;
        --output)             OUTPUT="$2"; shift 2 ;;
        --rundir)             RUNDIR_OVERRIDE="$2"; shift 2 ;;
        --dockerhub-username) DOCKERHUB_USERNAME="$2"; shift 2 ;;
        --intervention)       INTERVENTION="$2"; shift 2 ;;
        --prompt-config)      PROMPT_CONFIG="$2"; shift 2 ;;
        --rc|--rubric-correct)   RC="$2"; shift 2 ;;
        --ri|--rubric-incorrect) RI="$2"; shift 2 ;;
        --ra|--rubric-abstain)   RA="$2"; shift 2 ;;
        --api-timeout)           API_TIMEOUT="$2"; shift 2 ;;
        --reasoning-effort)      REASONING_EFFORT="$2"; shift 2 ;;
        --no-eval)            DO_EVAL=0; shift ;;
        --eval-only)          DO_INFER=0; shift ;;
        --gold-eval)          DO_INFER=0; GOLD_EVAL=1; shift ;;
        -h|--help)            usage ;;
        --)                   shift; break ;;
        -*) echo "Unknown flag: $1" >&2; echo "Run with --help." >&2; exit 2 ;;
        *)  echo "Unexpected positional: $1" >&2; exit 2 ;;
    esac
done

# Build a sensible default output dir if the user didn't pass --output.
# Format: results/<model_slug>[_int<I>_<config>][_n<N>][_seed<S>]
if [ -z "$OUTPUT" ]; then
    if [ "$DO_INFER" -eq 0 ] && [ -n "$RUNDIR_OVERRIDE" ]; then
        OUTPUT="$RUNDIR_OVERRIDE"
    else
        slug="${MODEL//\//_}"; slug="${slug//:/_}"
        suffix=""
        if [ "$INTERVENTION" != "0" ]; then
            cfg_slug="$PROMPT_CONFIG"
            if [ "$PROMPT_CONFIG" = "quant" ]; then
                cfg_slug="quant${RC}_${RI}_${RA}"
            fi
            suffix="_int${INTERVENTION}_${cfg_slug}"
        elif [ "$PROMPT_CONFIG" != "none" ]; then
            cfg_slug="$PROMPT_CONFIG"
            if [ "$PROMPT_CONFIG" = "quant" ]; then
                cfg_slug="quant${RC}_${RI}_${RA}"
            fi
            suffix="_consequence_${cfg_slug}"
        fi
        if [ "$N" -gt 0 ]; then
            OUTPUT="swebench_pro/results/${slug}${suffix}_n${N}"
        else
            OUTPUT="swebench_pro/results/${slug}${suffix}_all"
        fi
        if [ "$SEED" != "100" ]; then
            OUTPUT="${OUTPUT}_seed${SEED}"
        fi
    fi
elif [ "$DO_INFER" -eq 0 ] && [ -n "$RUNDIR_OVERRIDE" ]; then
    OUTPUT="$RUNDIR_OVERRIDE"
fi

echo "Run config:"
echo "  model         = $MODEL"
echo "  config        = $CONFIG"
echo "  instances     = $INSTANCES"
echo "  N (samples)   = ${N:-all}"
echo "  seed          = $SEED"
echo "  workers       = $WORKERS"
echo "  intervention  = $INTERVENTION"
echo "  prompt_config = $PROMPT_CONFIG"
if [ "$PROMPT_CONFIG" = "quant" ]; then
    echo "  rubric        = ($RC, $RI, $RA)  (correct, incorrect, abstain)"
fi
echo "  output        = $OUTPUT"
echo "  api_timeout   = ${API_TIMEOUT}s"
echo "  reasoning     = $REASONING_EFFORT"
echo "  do_infer      = $DO_INFER"
echo "  do_eval       = $DO_EVAL"
echo "  gold_eval     = $GOLD_EVAL"
echo "  eval_workers  = $EVAL_WORKERS"
echo "  dockerhub_user= $DOCKERHUB_USERNAME"

mkdir -p "$OUTPUT"

# 1. Inference (resumable).
if [ "$DO_INFER" -eq 1 ]; then
    EXTRA=()
    if [ "$N" -gt 0 ]; then
        EXTRA+=(--limit "$N")
    fi
    EXTRA+=(--intervention "$INTERVENTION" --prompt-config "$PROMPT_CONFIG")
    if [ "$PROMPT_CONFIG" = "quant" ]; then
        if [ -z "$RC" ] || [ -z "$RI" ] || [ -z "$RA" ]; then
            echo "Error: --prompt-config quant requires --rc / --ri / --ra." >&2
            exit 2
        fi
        EXTRA+=(--rubric-correct "$RC" --rubric-incorrect "$RI" --rubric-abstain "$RA")
    fi
    python swebench_pro/run_mini_on_pro.py \
        --model "$MODEL" \
        --config "$CONFIG" \
        --instances "$INSTANCES" \
        --output "$OUTPUT" \
        --workers "$WORKERS" \
        --seed "$SEED" \
        --api-timeout "$API_TIMEOUT" \
        --reasoning-effort "$REASONING_EFFORT" \
        "${EXTRA[@]}"
else
    echo "[run] skipping inference (--eval-only / --gold-eval)"
fi

# 2. Evaluation.
if [ "$DO_EVAL" -eq 1 ] || [ "$GOLD_EVAL" -eq 1 ]; then
    EVAL_FLAGS=(--workers "$EVAL_WORKERS" --dockerhub-username "$DOCKERHUB_USERNAME")
    if [ "$GOLD_EVAL" -eq 1 ]; then
        EVAL_FLAGS+=(--gold)
    fi
    bash swebench_pro/scripts/run_eval.sh "$OUTPUT" "${EVAL_FLAGS[@]}"
else
    echo "[run] skipping evaluation (--no-eval)"
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
    echo "  eval/instance_<bare_id>/mini_entryscript.sh      -- script run inside test container"
    echo
    echo "Note: <bare_id> is the instance id WITHOUT the leading 'instance_' prefix"
    echo "      (the eval dir uses the prefixed id; the trajectory dir uses the bare id)."
    if [ -f "$OUTPUT/eval/eval_results.json" ]; then
        n_total="$(python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(len(d))' "$OUTPUT/eval/eval_results.json" 2>/dev/null || echo "?")"
        n_resolved="$(python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(sum(d.values()))' "$OUTPUT/eval/eval_results.json" 2>/dev/null || echo "?")"
        echo "      This run: $n_resolved / $n_total resolved."
    fi
fi
