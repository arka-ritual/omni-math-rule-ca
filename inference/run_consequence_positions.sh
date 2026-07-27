#!/usr/bin/env bash
# Run the QP6/QP7 consequence-position ablation through OpenRouter.
#
# Defaults reproduce the prior qualitative Omni-MATH sampling configuration:
# 100 examples, seed 100, temperature 1.0, 64k maximum completion tokens.
# The same sampled indices are used in every cell.
#
# Source ~/.bashrc before invoking this script so OPENROUTER_API_KEY is set:
#   bash -ic 'cd /path/to/repo && bash inference/run_consequence_positions.sh'
#
# Five model workers run in parallel. Within each worker, its six conditions
# run sequentially with CONCURRENCY concurrent requests, bounding the default
# sweep at 5 * 20 = 100 simultaneous OpenRouter requests.

set -euo pipefail

cd "$(dirname "$0")/.."

NUM_SAMPLES="${NUM_SAMPLES:-100}"
SEED="${SEED:-100}"
TEMPERATURE="${TEMPERATURE:-1.0}"
MAX_TOKENS="${MAX_TOKENS:-64000}"
CONCURRENCY="${CONCURRENCY:-20}"
MAX_CELL_ATTEMPTS="${MAX_CELL_ATTEMPTS:-4}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/consequence_position}"
EVAL_DIR="${EVAL_DIR:-evaluation/output/consequence_position}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

ONLY_MODEL=""
ONLY_QP=""
ONLY_POSITION=""
DRY_RUN=0

usage() {
    sed -n '1,36p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --model) ONLY_MODEL="$2"; shift 2 ;;
        --qp) ONLY_QP="$2"; shift 2 ;;
        --position) ONLY_POSITION="$2"; shift 2 ;;
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
POSITIONS=("original" "beginning" "end")

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
validate_filter position "$ONLY_POSITION" "${POSITIONS[@]}"

mkdir -p "$RESULTS_DIR" "$EVAL_DIR"

echo "Consequence-position sweep"
echo "  samples=$NUM_SAMPLES seed=$SEED temperature=$TEMPERATURE max_tokens=$MAX_TOKENS"
echo "  per-model concurrency=$CONCURRENCY (model workers run in parallel)"
echo "  model=${ONLY_MODEL:-all} qp=${ONLY_QP:-all} position=${ONLY_POSITION:-all}"

run_cell() {
    local slug="$1" display="$2" model_id="$3" provider_tag="$4" qp="$5" position="$6"
    local prompt="${qp}_position_${position}"
    local stem="${slug}_${qp}_${position}"
    local output="$RESULTS_DIR/${stem}.jsonl"
    local attempt=1
    local completed=0

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "DRY RUN: $display | $qp | $position | $model_id via $provider_tag"
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
        echo "RUN: $display | $qp | $position | attempt $attempt | completed $completed/$NUM_SAMPLES"
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

run_model() {
    local entry="$1"
    local slug display model_id provider_tag qp position
    IFS='|' read -r slug display model_id provider_tag <<< "$entry"
    for qp in "${QPS[@]}"; do
        [ -n "$ONLY_QP" ] && [ "$ONLY_QP" != "$qp" ] && continue
        for position in "${POSITIONS[@]}"; do
            [ -n "$ONLY_POSITION" ] && [ "$ONLY_POSITION" != "$position" ] && continue
            run_cell "$slug" "$display" "$model_id" "$provider_tag" "$qp" "$position"
        done
    done
}

pids=()
worker_labels=()
for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug _ <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    run_model "$entry" &
    pids+=("$!")
    worker_labels+=("$slug")
done

failed=0
for i in "${!pids[@]}"; do
    if ! wait "${pids[$i]}"; then
        echo "ERROR: worker ${worker_labels[$i]} failed" >&2
        failed=1
    fi
done
if [ "$failed" -ne 0 ]; then
    exit 1
fi

if [ "$DRY_RUN" -eq 0 ]; then
    summary_args=(
        --eval-dir "$EVAL_DIR"
        --output-markdown "$EVAL_DIR/summary.md"
        --output-csv "$EVAL_DIR/summary.csv"
    )
    [ -n "$ONLY_MODEL" ] && summary_args+=(--model "$ONLY_MODEL")
    [ -n "$ONLY_QP" ] && summary_args+=(--qp "$ONLY_QP")
    [ -n "$ONLY_POSITION" ] && summary_args+=(--position "$ONLY_POSITION")
    "$PYTHON_BIN" scripts/summarize_consequence_positions.py "${summary_args[@]}"
fi

echo "Done. Results: $RESULTS_DIR ; evaluation: $EVAL_DIR"
