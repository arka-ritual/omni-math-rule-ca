#!/bin/bash
# SWE-bench Pro Consequence Asymmetry Experiments Runner
#
# Usage:
#   ./run_swe_experiments.sh [model] [prompt]
#
# Examples:
#   ./run_swe_experiments.sh opus standard          # Run one experiment
#   ./run_swe_experiments.sh opus all               # Run all prompts for Claude
#   ./run_swe_experiments.sh all all                # Run everything (21 runs)

set -e  # Exit on error

# Configuration
DATA_FILE="swe_bench_pro_100.jsonl"
NUM_SAMPLES=100
SEED=42
RESULTS_DIR="inference/results"
OUTPUT_DIR="evaluation/output"

# Ensure keys are loaded
source setup_keys.sh

# Model configurations
declare -A MODELS
MODELS[opus]="anthropic claude-opus-4-6"
MODELS[gpt5.2]="openai gpt-5.2"
MODELS[gpt5.2-pro]="openai gpt-5.2-pro"
MODELS[gemini3]="google gemini-3-pro-preview"

# Prompt variants
PROMPTS=(
    "standard"
    "cautious"
    "ultra_cautious"
    "reward_lives_1_10"
    "reward_lives_1_humanity"
    "natural_grading"
    "natural_grading_2"
)

# Parse arguments
MODEL_ARG="${1:-all}"
PROMPT_ARG="${2:-all}"

# Function to run single experiment
run_experiment() {
    local model_key=$1
    local prompt=$2

    # Parse model configuration
    IFS=' ' read -r provider model_id <<< "${MODELS[$model_key]}"

    local save_path="${RESULTS_DIR}/swe_${model_key}_${prompt}.jsonl"
    local output_path="${OUTPUT_DIR}/swe-${model_key}-${prompt}"

    echo ""
    echo "========================================"
    echo "Running: $model_key / $prompt"
    echo "========================================"

    # Run inference
    echo ">>> Inference (this may take a while)..."
    python inference/inference_api_swe.py \
        --provider "$provider" \
        --model "$model_id" \
        --data_file "$DATA_FILE" \
        --save_path "$save_path" \
        --prompt "$prompt" \
        --num_samples "$NUM_SAMPLES" \
        --seed "$SEED"

    # Run evaluation
    echo ">>> Evaluation..."
    python evaluation/swe_eval_cautious.py \
        --data_file "$save_path" \
        --output_dir "$output_path" \
        --execution_mode simulated

    # Show results
    echo ">>> Results:"
    cat "$output_path/cautious_metrics.json" | python -m json.tool

    echo "✓ Completed: $model_key / $prompt"
}

# Main execution
main() {
    # Check if dataset exists
    if [ ! -f "$DATA_FILE" ]; then
        echo "Error: Dataset not found: $DATA_FILE"
        echo "Please run:"
        echo "  python inference/swe_dataset_loader.py $DATA_FILE 100"
        exit 1
    fi

    # Determine which models to run
    if [ "$MODEL_ARG" = "all" ]; then
        MODELS_TO_RUN=("opus" "gpt5.2" "gemini3")
    else
        MODELS_TO_RUN=("$MODEL_ARG")
    fi

    # Determine which prompts to run
    if [ "$PROMPT_ARG" = "all" ]; then
        PROMPTS_TO_RUN=("${PROMPTS[@]}")
    else
        PROMPTS_TO_RUN=("$PROMPT_ARG")
    fi

    # Run experiments
    total=$((${#MODELS_TO_RUN[@]} * ${#PROMPTS_TO_RUN[@]}))
    current=0

    echo "========================================"
    echo "SWE-bench Pro Experiments"
    echo "========================================"
    echo "Models: ${MODELS_TO_RUN[*]}"
    echo "Prompts: ${PROMPTS_TO_RUN[*]}"
    echo "Total runs: $total"
    echo "========================================"

    for model_key in "${MODELS_TO_RUN[@]}"; do
        # Check if model exists
        if [ -z "${MODELS[$model_key]}" ]; then
            echo "Error: Unknown model: $model_key"
            echo "Available: ${!MODELS[@]}"
            exit 1
        fi

        for prompt in "${PROMPTS_TO_RUN[@]}"; do
            current=$((current + 1))
            echo ""
            echo "[$current/$total] Running $model_key / $prompt"
            run_experiment "$model_key" "$prompt"
        done
    done

    echo ""
    echo "========================================"
    echo "All experiments completed!"
    echo "========================================"
    echo "Results saved to: $OUTPUT_DIR/swe-*"
    echo ""
    echo "To view summary:"
    echo "  ./summarize_swe_results.sh"
}

# Run main
main
