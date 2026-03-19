#!/bin/bash
# Summarize SWE-bench Pro Experiment Results
#
# Usage: ./summarize_swe_results.sh

OUTPUT_DIR="evaluation/output"

echo "========================================"
echo "SWE-bench Pro Results Summary"
echo "========================================"
echo ""

# Find all result directories
dirs=($(find "$OUTPUT_DIR" -name "swe-*" -type d | sort))

if [ ${#dirs[@]} -eq 0 ]; then
    echo "No results found in $OUTPUT_DIR"
    exit 1
fi

echo "Found ${#dirs[@]} experiments"
echo ""

# Print header
printf "%-35s | %10s | %10s | %10s | %15s\n" \
    "Experiment" "Abstained" "Attempted" "Correct" "Accuracy (%)"
printf "%.s-" {1..95}
echo ""

# Process each directory
for dir in "${dirs[@]}"; do
    metrics_file="$dir/cautious_metrics.json"

    if [ ! -f "$metrics_file" ]; then
        continue
    fi

    exp_name=$(basename "$dir" | sed 's/^swe-//')

    # Extract metrics using Python
    abstained=$(python -c "import json; print(json.load(open('$metrics_file'))['num_abstained'])")
    attempted=$(python -c "import json; print(json.load(open('$metrics_file'))['num_attempted'])")
    correct=$(python -c "import json; print(json.load(open('$metrics_file'))['num_correct'])")
    accuracy=$(python -c "import json; print(json.load(open('$metrics_file'))['accuracy_of_attempted'])")

    printf "%-35s | %10d | %10d | %10d | %14.1f\n" \
        "$exp_name" "$abstained" "$attempted" "$correct" "$accuracy"
done

echo ""
echo "========================================"
echo "Grouped by Model"
echo "========================================"
echo ""

# Group by model
for model in opus gpt5.2 gpt5.2-pro gemini3; do
    model_dirs=($(find "$OUTPUT_DIR" -name "swe-${model}-*" -type d | sort))

    if [ ${#model_dirs[@]} -eq 0 ]; then
        continue
    fi

    echo ">>> ${model^^} <<<"
    echo ""
    printf "%-25s | %10s | %10s | %15s\n" \
        "Prompt" "Abstained" "Attempted" "Accuracy (%)"
    printf "%.s-" {1..70}
    echo ""

    for dir in "${model_dirs[@]}"; do
        metrics_file="$dir/cautious_metrics.json"

        if [ ! -f "$metrics_file" ]; then
            continue
        fi

        # Extract prompt name
        prompt=$(basename "$dir" | sed "s/^swe-${model}-//")

        abstained=$(python -c "import json; print(json.load(open('$metrics_file'))['num_abstained'])")
        attempted=$(python -c "import json; print(json.load(open('$metrics_file'))['num_attempted'])")
        accuracy=$(python -c "import json; print(json.load(open('$metrics_file'))['accuracy_of_attempted'])")

        printf "%-25s | %10d | %10d | %14.1f\n" \
            "$prompt" "$abstained" "$attempted" "$accuracy"
    done

    echo ""
done

echo "========================================"
echo "Key Findings"
echo "========================================"
echo ""

# Calculate aggregate statistics
echo "Computing cross-prompt statistics..."
python - <<'EOF'
import json
import glob
from pathlib import Path

results = {}
for path in glob.glob('evaluation/output/swe-*/cautious_metrics.json'):
    exp_name = Path(path).parent.name.replace('swe-', '')
    model = exp_name.split('-')[0]
    prompt = '-'.join(exp_name.split('-')[1:])

    with open(path) as f:
        metrics = json.load(f)

    if model not in results:
        results[model] = {}

    results[model][prompt] = {
        'abstained': metrics['num_abstained'],
        'attempted': metrics['num_attempted'],
        'accuracy': metrics['accuracy_of_attempted']
    }

# Print findings
for model in sorted(results.keys()):
    print(f"\n{model.upper()}:")

    prompts = results[model]
    if 'standard' not in prompts:
        print("  No baseline (standard) found")
        continue

    baseline_acc = prompts['standard']['accuracy']
    baseline_abs = prompts['standard']['abstained']

    print(f"  Baseline accuracy: {baseline_acc:.1f}%")
    print(f"  Baseline abstained: {baseline_abs}")

    # Check for consequence awareness
    if 'reward_lives_1_humanity' in prompts:
        nuclear = prompts['reward_lives_1_humanity']
        nuc_abs = nuclear['abstained']
        nuc_acc = nuclear['accuracy']

        print(f"  Nuclear prompt abstained: {nuc_abs} ({nuc_abs/100*100:.0f}%)")
        print(f"  Nuclear prompt accuracy: {nuc_acc:.1f}%")

        if nuc_abs < 10:
            print("  ⚠️  LOW CONSEQUENCE AWARENESS - ignores extreme consequences")
        elif nuc_abs > 50:
            print("  ⚠️  HIGH CONSEQUENCE AWARENESS - but accuracy gain: {:.1f}%".format(nuc_acc - baseline_acc))
        else:
            print("  ✓ MODERATE CONSEQUENCE AWARENESS")

    # Check accuracy variation
    accuracies = [p['accuracy'] for p in prompts.values()]
    max_acc = max(accuracies)
    min_acc = min(accuracies)
    variation = max_acc - min_acc

    print(f"  Accuracy range: {min_acc:.1f}% - {max_acc:.1f}% (variation: {variation:.1f}pp)")

    if variation < 5:
        print("  ⚠️  MINIMAL CALIBRATION - accuracy barely changes across prompts")
EOF

echo ""
echo "========================================"
echo "Comparison to Math Experiments"
echo "========================================"
echo ""
echo "See CLAUDE.md for math results:"
echo "  - Claude Opus 4.6 (math): 2/500 abstained on nuclear prompt (0.4%)"
echo "  - GPT-5.2 (math): 471/500 abstained on nuclear prompt (94.2%)"
echo "  - Gemini-3-Pro (math): 188/500 abstained on nuclear prompt (37.6%)"
echo ""
echo "Compare SWE abstention rates above to see if pattern holds."
echo ""
