#!/usr/bin/env bash
# Run the five-model QP6/QP7 no-CoT pilot through OpenRouter.
#
# The default sweep is 10 cells x 5 questions = 50 new completions. All ten
# cells run concurrently, with five requests per cell. Seed 100 makes the
# selected questions the strict five-question prefix of the existing
# consequence-position N=100 sample.
#
# Source ~/.bashrc through an interactive shell:
#   bash -ic 'cd /path/to/repo && bash inference/run_cot_ablation_pilot.sh'

set -euo pipefail

cd "$(dirname "$0")/.."

NUM_SAMPLES="${NUM_SAMPLES:-5}"
SEED="${SEED:-100}"
TEMPERATURE="${TEMPERATURE:-1.0}"
MAX_TOKENS="${MAX_TOKENS:-64000}"
CONCURRENCY="${CONCURRENCY:-5}"
MAX_CELL_ATTEMPTS="${MAX_CELL_ATTEMPTS:-4}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/cot_ablation_pilot}"
EVAL_DIR="${EVAL_DIR:-evaluation/output/cot_ablation_pilot}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

ONLY_MODEL=""
ONLY_QP=""
DRY_RUN=0

usage() {
    sed -n '1,28p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --model) ONLY_MODEL="$2"; shift 2 ;;
        --qp) ONLY_QP="$2"; shift 2 ;;
        --num-samples) NUM_SAMPLES="$2"; shift 2 ;;
        --seed) SEED="$2"; shift 2 ;;
        --temperature) TEMPERATURE="$2"; shift 2 ;;
        --max-tokens) MAX_TOKENS="$2"; shift 2 ;;
        --concurrency) CONCURRENCY="$2"; shift 2 ;;
        --results-dir) RESULTS_DIR="$2"; shift 2 ;;
        --eval-dir) EVAL_DIR="$2"; shift 2 ;;
        --python) PYTHON_BIN="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ "$NUM_SAMPLES" -ne 5 ]; then
    echo "ERROR: this preregistered pilot requires --num-samples 5." >&2
    exit 2
fi
if [ "$SEED" -ne 100 ]; then
    echo "ERROR: this preregistered pilot requires --seed 100." >&2
    exit 2
fi
if [ "$DRY_RUN" -eq 0 ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "ERROR: OPENROUTER_API_KEY is unset. Source ~/.bashrc first." >&2
    exit 2
fi

MODELS=(
    "claude-haiku-4-5|Claude Haiku 4.5|anthropic/claude-haiku-4.5|anthropic"
    "deepseek-v4-pro|DeepSeek V4 Pro|deepseek/deepseek-v4-pro|deepseek"
    "gemini-3.1-flash-lite|Gemini 3.1 Flash Lite|google/gemini-3.1-flash-lite|google-ai-studio"
    "gpt-5.4-nano|GPT-5.4 Nano|openai/gpt-5.4-nano|openai"
    "qwen3.5-397b-a17b|Qwen3.5 397B A17B|qwen/qwen3.5-397b-a17b|alibaba"
)
QPS=("QP6" "QP7")

validate_filter() {
    local flag="$1" value="$2"
    shift 2
    [ -z "$value" ] && return
    local candidate
    for candidate in "$@"; do
        [ "$candidate" = "$value" ] && return
    done
    echo "ERROR: --${flag} '${value}' is invalid; expected one of: $*" >&2
    exit 2
}

model_slugs=()
for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug _ <<< "$entry"
    model_slugs+=("$slug")
done
validate_filter model "$ONLY_MODEL" "${model_slugs[@]}"
validate_filter qp "$ONLY_QP" "${QPS[@]}"

mkdir -p "$RESULTS_DIR" "$EVAL_DIR"

echo "No-CoT pilot"
echo "  samples=$NUM_SAMPLES seed=$SEED temperature=$TEMPERATURE max_tokens=$MAX_TOKENS"
echo "  per-cell concurrency=$CONCURRENCY; selected cells run in parallel"
echo "  model=${ONLY_MODEL:-all} qp=${ONLY_QP:-all}"

run_cell() {
    local slug="$1" display="$2" model_id="$3" provider_tag="$4" qp="$5"
    local prompt="${qp}_no_cot"
    local stem="${slug}_${qp}_no_cot"
    local output="$RESULTS_DIR/${stem}.jsonl"
    local attempt=1
    local completed=0

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "DRY RUN: $display | $qp | $model_id via $provider_tag | n=$NUM_SAMPLES"
        return
    fi

    while [ "$attempt" -le "$MAX_CELL_ATTEMPTS" ]; do
        completed=0
        if [ -f "$output" ]; then
            completed="$(wc -l < "$output")"
        fi
        if [ "$completed" -ge "$NUM_SAMPLES" ]; then
            break
        fi
        echo "RUN: $display | $qp | attempt $attempt | completed $completed/$NUM_SAMPLES"
        "$PYTHON_BIN" inference/inference_api.py \
            --provider openrouter \
            --model "$model_id" \
            --openrouter-provider "$provider_tag" \
            --save_path "$output" \
            --prompt "$prompt" \
            --num_samples "$NUM_SAMPLES" \
            --seed "$SEED" \
            --temperature "$TEMPERATURE" \
            --max_tokens "$MAX_TOKENS" \
            --concurrency "$CONCURRENCY"
        attempt=$((attempt + 1))
    done

    completed=0
    if [ -f "$output" ]; then
        completed="$(wc -l < "$output")"
    fi
    if [ "$completed" -ne "$NUM_SAMPLES" ]; then
        echo "ERROR: $stem has $completed/$NUM_SAMPLES results after $MAX_CELL_ATTEMPTS attempts" >&2
        return 1
    fi

    "$PYTHON_BIN" evaluation/math_eval_cautious.py \
        --data_file "$output" \
        --output_dir "$EVAL_DIR/$stem"
}

pids=()
labels=()
for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug display model_id provider_tag <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    for qp in "${QPS[@]}"; do
        [ -n "$ONLY_QP" ] && [ "$ONLY_QP" != "$qp" ] && continue
        run_cell "$slug" "$display" "$model_id" "$provider_tag" "$qp" &
        pids+=("$!")
        labels+=("$slug/$qp")
    done
done

failed=0
for i in "${!pids[@]}"; do
    if ! wait "${pids[$i]}"; then
        echo "ERROR: worker ${labels[$i]} failed" >&2
        failed=1
    fi
done
if [ "$failed" -ne 0 ]; then
    exit 1
fi

echo "Done. Results: $RESULTS_DIR ; standard evaluation: $EVAL_DIR"
