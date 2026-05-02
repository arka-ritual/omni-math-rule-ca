#!/bin/bash
# Orchestrate the four interventions across the model set defined in
# Section 6 of the paper, for the math task.
#
# Models (provider:api-id pairs — edit if the API names below diverge from
# what the host endpoints actually serve at run time):
#   - claude-haiku-4-5     → anthropic/claude-haiku-4-5
#   - gemini-3.1-flash-lite → google/gemini-3.1-flash-lite
#   - gpt-5.4-nano         → openai/gpt-5.4-nano
#   - qwen3.5-397b         → openrouter/qwen/qwen3.5-397b-instruct
#   - deepseek-v4-pro      → openrouter/deepseek/deepseek-v4-pro
#
# Prompt configurations: Quant-25, Quant-100, QP6, QP7
# Interventions: 1 (single-turn), 2 (multi-turn), 3 (multi-turn no-conf),
#                4 (post-hoc on int1 outputs, no API calls)
#
# Usage:
#   bash inference/run_interventions.sh                          # full sweep
#   bash inference/run_interventions.sh --model claude-haiku-4-5
#   bash inference/run_interventions.sh --config Quant-25 --intervention 1
#   bash inference/run_interventions.sh --model claude-haiku-4-5 --num-samples 1 --max-tokens 64000
#
# All knobs can be set via CLI flag OR via env var (CLI flag wins):
#   --num-samples / NUM_SAMPLES   default 200
#   --seed        / SEED          default 100
#   --temperature / TEMPERATURE   default 0.0
#   --max-tokens  / MAX_TOKENS    default 32768
#   --concurrency / CONCURRENCY   default 20
#   --results-dir / RESULTS_DIR   default inference/results/interventions
#   --eval-dir    / EVAL_DIR      default evaluation/output/interventions
# Filters (CLI only; absent = run everything):
#   --model       <slug>          one of the MODELS slugs below
#   --config      <name>          one of: Quant-25 Quant-100 QP6 QP7
#   --intervention <1|2|3|4>
#
# (NUM_SAMPLES and N_SAMPLES are both accepted; the previous version of
# this script only accepted N_SAMPLES, which was a footgun.)
#
# Required keys in env or in a .env file at repo root (the runner loads
# .env via python-dotenv):
#   ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY (or GOOGLE_API_KEY),
#   OPENROUTER_API_KEY.

set -euo pipefail

cd "$(dirname "$0")/.."

# ---- knobs (env-var defaults; --flag overrides below) ----------------
NUM_SAMPLES="${NUM_SAMPLES:-${N_SAMPLES:-100}}"
SEED="${SEED:-100}"
TEMPERATURE="${TEMPERATURE:-1.0}"
MAX_TOKENS="${MAX_TOKENS:-64000}"
CONCURRENCY="${CONCURRENCY:-20}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/interventions}"
EVAL_DIR="${EVAL_DIR:-evaluation/output/interventions}"

ONLY_MODEL=""
ONLY_CONFIG=""
ONLY_INTERVENTION=""

# ---- CLI flag parsing -------------------------------------------------
usage () {
    sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --model)         ONLY_MODEL="$2"; shift 2 ;;
        --config)        ONLY_CONFIG="$2"; shift 2 ;;
        --intervention)  ONLY_INTERVENTION="$2"; shift 2 ;;
        --num-samples)   NUM_SAMPLES="$2"; shift 2 ;;
        --seed)          SEED="$2"; shift 2 ;;
        --temperature)   TEMPERATURE="$2"; shift 2 ;;
        --max-tokens)    MAX_TOKENS="$2"; shift 2 ;;
        --concurrency)   CONCURRENCY="$2"; shift 2 ;;
        --results-dir)   RESULTS_DIR="$2"; shift 2 ;;
        --eval-dir)      EVAL_DIR="$2"; shift 2 ;;
        -h|--help)       usage ;;
        --)              shift; break ;;
        -*)
            echo "Unknown flag: $1" >&2
            echo "Run with --help for usage." >&2
            exit 2
            ;;
        *)
            # Backwards compat: tolerate the old positional form
            #   bash run_interventions.sh <model> [<config> [<intervention>]]
            if [ -z "$ONLY_MODEL" ]; then
                ONLY_MODEL="$1"
            elif [ -z "$ONLY_CONFIG" ]; then
                ONLY_CONFIG="$1"
            elif [ -z "$ONLY_INTERVENTION" ]; then
                ONLY_INTERVENTION="$1"
            else
                echo "Unexpected extra positional argument: $1" >&2
                exit 2
            fi
            shift
            ;;
    esac
done

mkdir -p "$RESULTS_DIR" "$EVAL_DIR"

# ---- model set --------------------------------------------------------
# Each line: <slug>|<provider>|<provider-model-id>[|<openrouter-subprovider>]
# The optional 4th field forces OpenRouter to route to a specific upstream
# (e.g. "DeepSeek") with allow_fallbacks=false. Only meaningful when the
# provider field is "openrouter".
MODELS=(
    "claude-haiku-4-5|anthropic|claude-haiku-4-5"
    "gemini-3.1-flash-lite-preview|openrouter|google/gemini-3.1-flash-lite-preview"
    "gpt-5.4-nano|openai|gpt-5.4-nano"
    "qwen3.5-397b|openrouter|qwen/qwen3.5-397b-a17b"
    "deepseek-v4-pro|openrouter|deepseek/deepseek-v4-pro|DeepSeek"
)

PROMPT_CONFIGS=("Quant-25" "Quant-100" "QP6" "QP7")
INTERVENTIONS=(1 2 3)   # 4 is handled separately as a post-hoc step

# ---- validate filters: bail loudly when the sweep would be empty -----
validate_filter () {
    local flag="$1" value="$2"; shift 2
    [ -z "$value" ] && return
    for v in "$@"; do
        [ "$v" = "$value" ] && return
    done
    echo "ERROR: --$flag '$value' did not match any known value." >&2
    echo "  valid: $*" >&2
    exit 2
}

if [ -n "$ONLY_MODEL" ]; then
    valid_slugs=()
    for entry in "${MODELS[@]}"; do
        IFS='|' read -r slug _provider _model <<< "$entry"
        valid_slugs+=("$slug")
    done
    validate_filter "model" "$ONLY_MODEL" "${valid_slugs[@]}"
fi
[ -n "$ONLY_CONFIG" ] && validate_filter "config" "$ONLY_CONFIG" "${PROMPT_CONFIGS[@]}"
[ -n "$ONLY_INTERVENTION" ] && validate_filter "intervention" "$ONLY_INTERVENTION" 1 2 3 4

echo "Sweep config:"
echo "  num_samples=$NUM_SAMPLES seed=$SEED temperature=$TEMPERATURE"
echo "  max_tokens=$MAX_TOKENS concurrency=$CONCURRENCY"
echo "  filters: model='${ONLY_MODEL:-(all)}' config='${ONLY_CONFIG:-(all)}' intervention='${ONLY_INTERVENTION:-(all)}'"
echo "  results_dir=$RESULTS_DIR  eval_dir=$EVAL_DIR"

run_one_inference () {
    local slug="$1" provider="$2" model="$3" cfg="$4" interv="$5" or_subprovider="${6:-}"
    local out="$RESULTS_DIR/${slug}_int${interv}_${cfg}.jsonl"
    local extra_args=()
    if [ -n "$or_subprovider" ]; then
        extra_args+=(--openrouter-provider "$or_subprovider")
    fi
    echo
    echo "=== ${slug} | int${interv} | ${cfg}${or_subprovider:+ | OR-provider=$or_subprovider} ==="
    python inference/run_interventions.py \
        --provider "$provider" --model "$model" \
        --intervention "$interv" --prompt_config "$cfg" \
        --save_path "$out" \
        --num_samples "$NUM_SAMPLES" --seed "$SEED" \
        --temperature "$TEMPERATURE" --max_tokens "$MAX_TOKENS" \
        --concurrency "$CONCURRENCY" \
        "${extra_args[@]}"
    python evaluation/math_eval_cautious.py \
        --data_file "$out" \
        --output_dir "$EVAL_DIR/${slug}_int${interv}_${cfg}"
}

run_intervention4 () {
    local slug="$1" cfg="$2"
    local int1="$RESULTS_DIR/${slug}_int1_${cfg}.jsonl"
    local out="$RESULTS_DIR/${slug}_int4_${cfg}.jsonl"
    if [ ! -f "$int1" ]; then
        echo "skip int4 ${slug}/${cfg}: missing intervention-1 file ${int1}"
        return
    fi
    echo
    echo "=== ${slug} | int4 (post-hoc) | ${cfg} ==="
    python inference/run_interventions.py \
        --provider openai --model unused \
        --intervention 4 --prompt_config "$cfg" \
        --save_path "$out" \
        --intervention1_input "$int1"
    python evaluation/math_eval_cautious.py \
        --data_file "$out" \
        --output_dir "$EVAL_DIR/${slug}_int4_${cfg}"
}

# Sanity: count how many cells we'll actually run.
cells=0
for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug _ _ <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    for cfg in "${PROMPT_CONFIGS[@]}"; do
        [ -n "$ONLY_CONFIG" ] && [ "$ONLY_CONFIG" != "$cfg" ] && continue
        for interv in "${INTERVENTIONS[@]}" 4; do
            [ -n "$ONLY_INTERVENTION" ] && [ "$ONLY_INTERVENTION" != "$interv" ] && continue
            cells=$((cells + 1))
        done
    done
done
if [ "$cells" -eq 0 ]; then
    echo "ERROR: filters matched 0 cells; nothing to run." >&2
    exit 2
fi
echo "Will run $cells cell(s)."

for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug provider model or_subprovider <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    for cfg in "${PROMPT_CONFIGS[@]}"; do
        [ -n "$ONLY_CONFIG" ] && [ "$ONLY_CONFIG" != "$cfg" ] && continue
        for interv in "${INTERVENTIONS[@]}"; do
            [ -n "$ONLY_INTERVENTION" ] && [ "$ONLY_INTERVENTION" != "$interv" ] && continue
            run_one_inference "$slug" "$provider" "$model" "$cfg" "$interv" "$or_subprovider"
        done
        if [ -z "$ONLY_INTERVENTION" ] || [ "$ONLY_INTERVENTION" = "4" ]; then
            run_intervention4 "$slug" "$cfg"
        fi
    done
done

echo
echo "Done. Results: $RESULTS_DIR ; metrics: $EVAL_DIR"
