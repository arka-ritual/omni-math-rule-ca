#!/bin/bash
# Vanilla baseline sweep for Omni-MATH-Rule using the `standard` prompt.
#
# This is the math-side counterpart to `swebench_pro/run_baselines.sh`.
# It runs `inference/inference_api.py --prompt standard` for each of the
# baseline models, then grades each output JSONL with `evaluation/math_eval.py`.
#
# Models (slug | provider | model-id [| openrouter-subprovider]):
#   - claude-haiku-4-5              | anthropic  | claude-haiku-4-5
#   - gemini-3.1-flash-lite-preview | openrouter | google/gemini-3.1-flash-lite-preview
#   - gemini-3-flash-preview        | openrouter | google/gemini-3.0-flash-preview      
#   - gemini-3.1-pro-preview        | openrouter | google/gemini-3.1-pro-preview
#   - gpt-5.4-nano                  | openai     | gpt-5.4-nano
#   - deepseek-v4-pro               | openrouter | deepseek/deepseek-v4-pro | DeepSeek
#   - qwen3.5-397b                  | openrouter | qwen/qwen3.5-397b-a17b
#   - qwen3.5-122b                  | openrouter | qwen/qwen3.5-122b
#   - qwen3.5-9b                    | openrouter | qwen/qwen3.5-9b
#   - gemma-4-31b                   | openrouter | google/gemma-4-31b-it
#
# Mirrors `inference/run_interventions.sh` for everything that overlaps
# (model definitions, env-var defaults, CLI flag style, results-dir layout).
#
# Usage:
#   bash inference/run_baselines.sh                          # all 10 models
#   bash inference/run_baselines.sh --model gpt-5.4-nano     # one model only
#   bash inference/run_baselines.sh --no-eval                # inference only
#
#   NUM_SAMPLES=500 CONCURRENCY=20 \
#       bash inference/run_baselines.sh
#
# Knobs (CLI flag wins over env var):
#   --num-samples / NUM_SAMPLES   default 100  (0 = full 2,821-problem dataset)
#   --seed        / SEED          default 100
#   --temperature / TEMPERATURE   default 0.0
#   --max-tokens  / MAX_TOKENS    default 32768
#   --concurrency / CONCURRENCY   default 20
#   --results-dir / RESULTS_DIR   default inference/results/baselines
#   --eval-dir    / EVAL_DIR      default evaluation/output/baselines
#   --prompt      / PROMPT        default "standard"
#   --no-eval                     skip the per-cell evaluation step
#   --model <slug>                restrict to this model (default: all)
#
# Required keys in env or in `.env` at the repo root:
#   OPENAI_API_KEY        (gpt-5.4-nano)
#   ANTHROPIC_API_KEY     (claude-haiku-4-5)
#   OPENROUTER_API_KEY    (all gemini variants, deepseek, qwen 397B/122B/9B, gemma)

set -euo pipefail

cd "$(dirname "$0")/.."

# ---- knobs ------------------------------------------------------------
NUM_SAMPLES="${NUM_SAMPLES:-${N_SAMPLES:-100}}"
SEED="${SEED:-100}"
TEMPERATURE="${TEMPERATURE:-0.0}"
MAX_TOKENS="${MAX_TOKENS:-32768}"
CONCURRENCY="${CONCURRENCY:-20}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/baselines}"
EVAL_DIR="${EVAL_DIR:-evaluation/output/baselines}"
PROMPT="${PROMPT:-standard}"
DATA_FILE="${DATA_FILE:-omni_math_rule.jsonl}"

DO_EVAL=1
ONLY_MODEL=""

usage () { sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --model)        ONLY_MODEL="$2"; shift 2 ;;
        --num-samples)  NUM_SAMPLES="$2"; shift 2 ;;
        --seed)         SEED="$2"; shift 2 ;;
        --temperature)  TEMPERATURE="$2"; shift 2 ;;
        --max-tokens)   MAX_TOKENS="$2"; shift 2 ;;
        --concurrency)  CONCURRENCY="$2"; shift 2 ;;
        --results-dir)  RESULTS_DIR="$2"; shift 2 ;;
        --eval-dir)     EVAL_DIR="$2"; shift 2 ;;
        --prompt)       PROMPT="$2"; shift 2 ;;
        --data-file)    DATA_FILE="$2"; shift 2 ;;
        --no-eval)      DO_EVAL=0; shift ;;
        -h|--help)      usage ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$RESULTS_DIR" "$EVAL_DIR"

# ---- model set --------------------------------------------------------
# Each line: <slug>|<provider>|<provider-model-id>[|<openrouter-subprovider>]
# slug feeds the output filename + eval exp_name. The optional 4th field
# pins OpenRouter to a specific upstream (allow_fallbacks=false). Mirrors
# the 5-model row-set in inference/run_interventions.sh, plus qwen3.5-9b,
# gemma-4-31b, gemini-3.0-flash, gemini-3.1-pro, and qwen3.5-122b for the
# baseline-only model set.
MODELS=(
    "claude-haiku-4-5|anthropic|claude-haiku-4-5"
    "gemini-3.1-flash-lite-preview|openrouter|google/gemini-3.1-flash-lite-preview"
    "gemini-3-flash-preview|openrouter|google/gemini-3-flash-preview"
    "gemini-3.1-pro-preview|openrouter|google/gemini-3.1-pro-preview"
    "gpt-5.4-nano|openai|gpt-5.4-nano"
    "deepseek-v4-pro|openrouter|deepseek/deepseek-v4-pro|DeepSeek"
    "qwen3.5-397b|openrouter|qwen/qwen3.5-397b-a17b"
    "qwen3.5-122b|openrouter|qwen/qwen3.5-122b-a10b"
    "qwen3.5-9b|openrouter|qwen/qwen3.5-9b"
    "gemma-4-31b|openrouter|google/gemma-4-31b-it"
)

# ---- validate filter --------------------------------------------------
if [ -n "$ONLY_MODEL" ]; then
    valid=0
    for entry in "${MODELS[@]}"; do
        IFS='|' read -r slug _ _ <<< "$entry"
        [ "$slug" = "$ONLY_MODEL" ] && valid=1 && break
    done
    if [ "$valid" -ne 1 ]; then
        echo "ERROR: --model '$ONLY_MODEL' did not match any known slug." >&2
        echo "  valid: $(for e in "${MODELS[@]}"; do echo -n "${e%%|*} "; done)" >&2
        exit 2
    fi
fi

echo "Baseline sweep config:"
echo "  prompt        = $PROMPT"
echo "  num_samples   = $NUM_SAMPLES   seed=$SEED"
echo "  temperature   = $TEMPERATURE   max_tokens=$MAX_TOKENS"
echo "  concurrency   = $CONCURRENCY"
echo "  data_file     = $DATA_FILE"
echo "  filter model  = ${ONLY_MODEL:-(all ${#MODELS[@]})}"
echo "  do_eval       = $DO_EVAL"
echo "  results_dir   = $RESULTS_DIR"
echo "  eval_dir      = $EVAL_DIR"

run_one_inference () {
    local slug="$1" provider="$2" model="$3" or_subprovider="${4:-}"
    local out="$RESULTS_DIR/${slug}_${PROMPT}.jsonl"
    local extra_args=()
    if [ -n "$or_subprovider" ]; then
        extra_args+=(--openrouter-provider "$or_subprovider")
    fi
    echo
    echo "=== ${slug} | ${PROMPT}${or_subprovider:+ | OR-provider=$or_subprovider} ==="
    python inference/inference_api.py \
        --provider "$provider" --model "$model" \
        --prompt "$PROMPT" \
        --data_file "$DATA_FILE" \
        --save_path "$out" \
        --num_samples "$NUM_SAMPLES" --seed "$SEED" \
        --temperature "$TEMPERATURE" --max_tokens "$MAX_TOKENS" \
        --concurrency "$CONCURRENCY" \
        "${extra_args[@]}"
    if [ "$DO_EVAL" -eq 1 ]; then
        # math_eval.py imports `evaluate`, `utils`, etc. from cwd, so it must
        # be run from inside evaluation/. Use absolute paths for input/output
        # so the cd doesn't break things.
        local abs_in abs_out
        abs_in="$(cd "$(dirname "$out")" && pwd)/$(basename "$out")"
        abs_out="$(cd "$(dirname "$EVAL_DIR")" && pwd)/$(basename "$EVAL_DIR")"
        ( cd evaluation && python math_eval.py \
            --data_name omni-math \
            --exp_name "$slug" \
            --input_path "$abs_in" \
            --output_dir "$abs_out" )
    fi
}

# Sanity: cell count
cells=0
for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug _ _ <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    cells=$((cells + 1))
done
[ "$cells" -eq 0 ] && { echo "ERROR: filter matched 0 cells." >&2; exit 2; }
echo "Will run $cells cell(s)."

for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug provider model or_subprovider <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    run_one_inference "$slug" "$provider" "$model" "$or_subprovider"
done

echo
echo "Done."
echo "Per-model rundirs:"
for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug _ _ <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    echo "  inference: $RESULTS_DIR/${slug}_${PROMPT}.jsonl"
    if [ "$DO_EVAL" -eq 1 ]; then
        echo "  eval:      $EVAL_DIR/${slug}/omni-math/math_eval_cot_metrics.json"
    fi
done
