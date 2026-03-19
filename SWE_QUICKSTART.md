# SWE-bench Pro Experiments - Quick Start Guide

## Prerequisites

1. **API Keys** - Set up in `setup_keys.sh` or environment:
   ```bash
   export OPENAI_API_KEY="sk-..."
   export ANTHROPIC_API_KEY="sk-ant-..."
   export GOOGLE_API_KEY="..."
   ```

2. **Python Dependencies** - Already installed:
   - `openai`, `anthropic`, `google-genai` (API clients)
   - `datasets` (HuggingFace dataset loading)
   - `tqdm` (progress bars)

3. **Network** - Ensure stable internet connection without proxy issues

## Step 1: Download Dataset

```bash
# Download full SWE-bench Pro dataset (731 problems)
python -c "
from datasets import load_dataset
import json

print('Downloading SWE-bench Pro...')
ds = load_dataset('ScaleAI/SWE-bench_Pro', split='test')
data = list(ds)

with open('swe_bench_pro_full.jsonl', 'w') as f:
    for item in data:
        f.write(json.dumps(item) + '\n')

print(f'Saved {len(data)} problems to swe_bench_pro_full.jsonl')
"
```

## Step 2: Create 100-Problem Subset

```bash
# Create subset with seed 42 (deterministic)
python -c "
import random
import json

with open('swe_bench_pro_full.jsonl') as f:
    data = [json.loads(line) for line in f if line.strip()]

rng = random.Random(42)
indices = sorted(rng.sample(range(len(data)), 100))
subset = [data[i] for i in indices]

# Add idx field
for i, item in enumerate(subset):
    item['idx'] = i

with open('swe_bench_pro_100.jsonl', 'w') as f:
    for item in subset:
        f.write(json.dumps(item) + '\n')

print(f'Created subset: {len(subset)} problems')
"
```

## Step 3: Run Baseline Experiments

### Claude Opus 4.6 - Standard Prompt
```bash
source setup_keys.sh

python inference/inference_api_swe.py \
  --provider anthropic \
  --model claude-opus-4-6 \
  --data_file swe_bench_pro_100.jsonl \
  --save_path inference/results/swe_opus_standard.jsonl \
  --prompt standard \
  --num_samples 100 \
  --seed 42
```

### GPT-5.2 - Standard Prompt
```bash
python inference/inference_api_swe.py \
  --provider openai \
  --model gpt-5.2 \
  --data_file swe_bench_pro_100.jsonl \
  --save_path inference/results/swe_gpt5.2_standard.jsonl \
  --prompt standard \
  --num_samples 100 \
  --seed 42
```

### Gemini-3-Pro - Standard Prompt
```bash
python inference/inference_api_swe.py \
  --provider google \
  --model gemini-3-pro-preview \
  --data_file swe_bench_pro_100.jsonl \
  --save_path inference/results/swe_gemini3_standard.jsonl \
  --prompt standard \
  --num_samples 100 \
  --seed 42
```

## Step 4: Evaluate Baselines

```bash
# Claude Opus
python evaluation/swe_eval_cautious.py \
  --data_file inference/results/swe_opus_standard.jsonl \
  --output_dir evaluation/output/swe-opus-standard/ \
  --execution_mode simulated

# GPT-5.2
python evaluation/swe_eval_cautious.py \
  --data_file inference/results/swe_gpt5.2_standard.jsonl \
  --output_dir evaluation/output/swe-gpt5.2-standard/ \
  --execution_mode simulated

# Gemini-3-Pro
python evaluation/swe_eval_cautious.py \
  --data_file inference/results/swe_gemini3_standard.jsonl \
  --output_dir evaluation/output/swe-gemini3-standard/ \
  --execution_mode simulated
```

## Step 5: Run Consequence Asymmetry Experiments

Run all prompt variants for each model:

```bash
# Prompts to test
PROMPTS=(
  "cautious"
  "ultra_cautious"
  "reward_lives_1_10"
  "reward_lives_1_humanity"
  "natural_grading"
  "natural_grading_2"
)

# Example: Claude Opus 4.6
for prompt in "${PROMPTS[@]}"; do
  echo "Running $prompt..."
  python inference/inference_api_swe.py \
    --provider anthropic \
    --model claude-opus-4-6 \
    --data_file swe_bench_pro_100.jsonl \
    --save_path inference/results/swe_opus_${prompt}.jsonl \
    --prompt $prompt \
    --num_samples 100 \
    --seed 42

  python evaluation/swe_eval_cautious.py \
    --data_file inference/results/swe_opus_${prompt}.jsonl \
    --output_dir evaluation/output/swe-opus-${prompt}/ \
    --execution_mode simulated
done
```

Repeat for GPT-5.2 and Gemini-3-Pro.

## Step 6: Analyze Results

```bash
# View metrics for all runs
for dir in evaluation/output/swe-*; do
  echo "=== $(basename $dir) ==="
  cat $dir/cautious_metrics.json | python -m json.tool
  echo ""
done
```

Compare abstention rates across prompts:
```bash
python -c "
import json
import glob

results = {}
for path in glob.glob('evaluation/output/swe-*/cautious_metrics.json'):
    exp_name = path.split('/')[-2].replace('swe-', '')
    with open(path) as f:
        metrics = json.load(f)
    results[exp_name] = {
        'abstained': metrics['num_abstained'],
        'attempted': metrics['num_attempted'],
        'accuracy': metrics['accuracy_of_attempted']
    }

# Sort by model then prompt
for model in ['opus', 'gpt5.2', 'gemini3']:
    print(f'\n{model.upper()}:')
    for name, metrics in sorted(results.items()):
        if model in name:
            print(f'  {name:30s} | Abstained: {metrics[\"abstained\"]:3d} | Accuracy: {metrics[\"accuracy\"]:5.1f}%')
"
```

## Expected Output Format

### Inference Results (JSONL)
Each line contains:
```json
{
  "idx": 0,
  "instance_id": "...",
  "repo": "...",
  "problem_statement": "...",
  "model_patch": "diff --git ...",
  "prompt_mode": "standard"
}
```

### Evaluation Metrics (JSON)
```json
{
  "num_total": 100,
  "num_abstained": 5,
  "num_attempted": 95,
  "num_correct": 30,
  "num_incorrect_standard": 60,
  "num_incorrect_mixed": 5,
  "accuracy_of_attempted": 31.6,
  "execution_mode": "simulated"
}
```

## Troubleshooting

### Network/Proxy Issues
If you encounter proxy errors:
```bash
# Unset proxy variables
unset ALL_PROXY all_proxy HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

# Or install SOCKS support
pip install httpx[socks]
```

### Resume Interrupted Runs
The inference pipeline is resume-safe. Just rerun the same command:
```bash
# This will skip already-completed items
python inference/inference_api_swe.py ... --save_path same_path.jsonl
```

### View Progress
Inference results are written immediately to disk, so you can check partial results:
```bash
# Count completed items
wc -l inference/results/swe_opus_standard.jsonl

# View last completed item
tail -1 inference/results/swe_opus_standard.jsonl | python -m json.tool
```

## Quick Test (5 Problems)

Before running full experiments, test with 5 problems:

```bash
source setup_keys.sh

# Use test dataset
python inference/inference_api_swe.py \
  --provider openai \
  --model gpt-4o-mini \
  --data_file swe_bench_pro_test.jsonl \
  --save_path inference/results/swe_quicktest.jsonl \
  --prompt standard \
  --num_samples 5 \
  --seed 42

# Evaluate
python evaluation/swe_eval_cautious.py \
  --data_file inference/results/swe_quicktest.jsonl \
  --output_dir evaluation/output/swe-quicktest/ \
  --execution_mode simulated

# View results
cat evaluation/output/swe-quicktest/cautious_metrics.json
```

## Comparison to Math Experiments

After running experiments, compare to math results in `CLAUDE.md`:

**Key metrics to compare:**
- Abstention rate by prompt (does SWE match math pattern?)
- Accuracy on attempted (does domain matter for calibration?)
- Response to extreme prompts (nuclear apocalypse = ignored?)

**Hypothesis:** Models will ignore consequence framing in SWE just like in math.

## Next Steps After Initial Results

1. **If simulated eval shows promise:** Switch to Docker evaluation for accurate resolve rates
2. **If abstention rates are low:** Consider harsher prompts or sequential environment
3. **If results differ from math:** Investigate domain-specific factors
4. **If results match math:** Strong evidence for cross-domain consequence insensitivity

## Files Created

Core infrastructure (all in place):
- `inference/prompts_swe.py` - 7 consequence asymmetry prompts
- `inference/swe_dataset_loader.py` - Dataset loading utilities
- `inference/inference_api_swe.py` - SWE inference pipeline
- `evaluation/swe_parser.py` - SKIP detection & patch extraction
- `evaluation/swe_test_executor.py` - Test execution
- `evaluation/swe_eval_cautious.py` - 3-way evaluator

Test data:
- `swe_bench_pro_test.jsonl` - 5 synthetic problems for testing

Documentation:
- `SWE_BENCH_EXTENSION.md` - Implementation status and details
- `SWE_QUICKSTART.md` - This guide
