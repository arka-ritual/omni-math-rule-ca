#!/usr/bin/env bash
set -ex

# --- Standard prompt, 100 problems ---
python inference/inference_api.py \
  --provider openai --model gpt-5.2 \
  --save_path inference/results/GPT-5.2_standard.jsonl \
  --prompt standard --num_samples 100

# --- Cautious prompt, 100 problems ---
python inference/inference_api.py \
  --provider openai --model gpt-5.2 \
  --save_path inference/results/GPT-5.2_cautious.jsonl \
  --prompt cautious --num_samples 100

# --- Evaluate standard (existing pipeline) ---
cd evaluation
bash sh/eval.sh omni-math ../inference/results/GPT-5.2_standard.jsonl GPT-5.2-standard

# --- Evaluate cautious (new script) ---
python math_eval_cautious.py \
  --data_file ../inference/results/GPT-5.2_cautious.jsonl \
  --output_dir output/GPT-5.2-cautious/omni-math/
