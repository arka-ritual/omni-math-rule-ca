#!/bin/bash
# Vanilla SWE-bench Pro baseline sweep across the 6 models of interest.
#
# This is the "no-intervention" counterpart to swebench_pro/run_interventions.sh.
# It loops the 6 models through `swebench_pro/run.sh --intervention 0` (vanilla),
# so each cell writes to `swebench_pro/results/<model_slug>_n<N>/` with a
# normal `preds.json` + `eval/eval_results.json`.
#
# Models (litellm slugs):
#   - gemini/gemini-3.1-flash-lite-preview
#   - openai/gpt-5.4-nano
#   - openrouter/deepseek/deepseek-v4-pro
#   - openrouter/qwen/qwen3.5-397b-a17b
#   - openrouter/qwen/qwen3.5-9b                  (NEW)
#   - openrouter/google/gemma-4-31b-it            (NEW)
#
# Usage:
#   bash swebench_pro/run_baselines.sh                       # all 6 models, defaults
#   bash swebench_pro/run_baselines.sh --model openai/gpt-5.4-nano
#   bash swebench_pro/run_baselines.sh --no-eval             # inference only
#
#   N=100 WORKERS=4 EVAL_WORKERS=8 \
#       bash swebench_pro/run_baselines.sh
#
# CLI filter (repeat for multiple):
#   --model <slug>            # restrict to this model (default: all in MODELS)
#
# Env-var defaults (CLI wins; same names as run_interventions.sh):
#   N, NUM_SAMPLES   -> per-cell sample count (0 = all 731 instances)
#   SEED             -> shuffle seed (default 100)
#   WORKERS          -> parallel agents per cell
#   EVAL_WORKERS     -> parallel docker eval workers
#   REASONING_EFFORT -> none|low|medium|high|xhigh (default medium, matches
#                       run_interventions.sh for an apples-to-apples baseline.
#                       Pass `none` for a true plain-vanilla baseline.)
#   DO_EVAL=0        -> skip the per-cell official-grader step
#   GOLD_EVAL=1      -> after the loop, also grade gold patches
#                       (sanity check, model-agnostic)

set -euo pipefail

cd "$(dirname "$0")/.."

# ---- defaults ----------------------------------------------------------
N="${N:-${NUM_SAMPLES:-100}}"
SEED="${SEED:-100}"
WORKERS="${WORKERS:-1}"
EVAL_WORKERS="${EVAL_WORKERS:-1}"
DO_EVAL="${DO_EVAL:-1}"
GOLD_EVAL="${GOLD_EVAL:-0}"
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-jefzda}"
API_TIMEOUT="${API_TIMEOUT:-600}"
REASONING_EFFORT="${REASONING_EFFORT:-medium}"
INSTANCES="${INSTANCES:-swebench_pro/data/swebench_pro_full.jsonl}"
CONFIG="${CONFIG:-swebench_pro/configs/swebench_pro_vanilla.yaml}"
RESULTS_ROOT="${RESULTS_ROOT:-swebench_pro/results}"

# ---- model set ---------------------------------------------------------
ALL_MODELS=(
    "gemini/gemini-3-flash-preview"
    "gemini/gemini-3.1-flash-lite-preview"
    "gemini/gemini-3.1-pro-preview"
    "openai/gpt-5.4-nano"
    "anthropic/claude-haiku-4-5"
    "openrouter/deepseek/deepseek-v4-pro"
    "openrouter/qwen/qwen3.5-397b-a17b"
    "openrouter/qwen/qwen3.5-122b-a10b"
    "openrouter/qwen/qwen3.5-9b"
    "openrouter/google/gemma-4-31b-it"
)

# ---- CLI filter parsing ------------------------------------------------
FILTER_MODELS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --model)        FILTER_MODELS+=("$2"); shift 2 ;;
        --n|--num-samples) N="$2"; shift 2 ;;
        --seed)         SEED="$2"; shift 2 ;;
        --workers)      WORKERS="$2"; shift 2 ;;
        --eval-workers) EVAL_WORKERS="$2"; shift 2 ;;
        --api-timeout)  API_TIMEOUT="$2"; shift 2 ;;
        --reasoning-effort) REASONING_EFFORT="$2"; shift 2 ;;
        --no-eval)      DO_EVAL=0; shift ;;
        --gold-eval)    GOLD_EVAL=1; shift ;;
        --instances)    INSTANCES="$2"; shift 2 ;;
        --config)       CONFIG="$2"; shift 2 ;;
        --dockerhub-username) DOCKERHUB_USERNAME="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

contains () {
    local needle="$1"; shift
    for v in "$@"; do [ "$v" = "$needle" ] && return 0; done
    return 1
}

is_active () {
    local listname="$1" val="$2"
    eval "local n=\${#${listname}[@]}"
    if [ "$n" -eq 0 ]; then return 0; fi
    eval "contains \"\$val\" \"\${${listname}[@]}\""
}

declare -a SWEEP=()
for model in "${ALL_MODELS[@]}"; do
    is_active FILTER_MODELS "$model" || continue
    SWEEP+=("$model")
done

if [ "${#SWEEP[@]}" -eq 0 ]; then
    echo "Empty sweep. Filters too restrictive?" >&2
    echo "  --model: ${FILTER_MODELS[*]:-(no filter)}" >&2
    echo "  Available: ${ALL_MODELS[*]}" >&2
    exit 2
fi

echo "Vanilla baseline sweep:"
echo "  models       = ${#SWEEP[@]}"
for m in "${SWEEP[@]}"; do echo "                 $m"; done
echo "  N (samples)  = ${N:-all}"
echo "  seed         = $SEED"
echo "  workers      = $WORKERS"
echo "  eval_workers = $EVAL_WORKERS"
echo "  do_eval      = $DO_EVAL"
echo "  gold_eval    = $GOLD_EVAL"
echo "  api_timeout  = ${API_TIMEOUT}s"
echo "  reasoning    = $REASONING_EFFORT"

slug () {
    local s="$1"; s="${s//\//_}"; s="${s//:/_}"; echo "$s"
}

# ---- run each model (vanilla = intervention 0, prompt_config none) ----
for model in "${SWEEP[@]}"; do
    out_slug="$(slug "$model")"
    if [ "$N" -gt 0 ]; then out_slug="${out_slug}_n${N}"; else out_slug="${out_slug}_all"; fi
    if [ "$SEED" != "100" ]; then out_slug="${out_slug}_seed${SEED}"; fi
    out_dir="${RESULTS_ROOT}/${out_slug}"

    echo
    echo "============================================================"
    echo "[$(date +%H:%M:%S)] cell: model=$model (vanilla)  -> $out_dir"
    echo "============================================================"

    args=(
        --model "$model"
        --output "$out_dir"
        --instances "$INSTANCES"
        --config "$CONFIG"
        --n "$N"
        --seed "$SEED"
        --workers "$WORKERS"
        --eval-workers "$EVAL_WORKERS"
        --api-timeout "$API_TIMEOUT"
        --reasoning-effort "$REASONING_EFFORT"
        --intervention 0
        --prompt-config none
        --dockerhub-username "$DOCKERHUB_USERNAME"
    )
    if [ "$DO_EVAL" -eq 0 ]; then
        args+=(--no-eval)
    fi

    bash swebench_pro/run.sh "${args[@]}"
done

if [ "$GOLD_EVAL" -eq 1 ]; then
    echo
    echo "============================================================"
    echo "[$(date +%H:%M:%S)] gold eval (sanity check)"
    echo "============================================================"
    bash swebench_pro/run.sh --gold-eval --eval-workers "$EVAL_WORKERS"
fi

echo
echo "Baseline sweep complete. Results: ${RESULTS_ROOT}/"
echo "Per-model rundirs:"
for model in "${SWEEP[@]}"; do
    out_slug="$(slug "$model")"
    if [ "$N" -gt 0 ]; then out_slug="${out_slug}_n${N}"; else out_slug="${out_slug}_all"; fi
    if [ "$SEED" != "100" ]; then out_slug="${out_slug}_seed${SEED}"; fi
    echo "  ${RESULTS_ROOT}/${out_slug}/"
done
