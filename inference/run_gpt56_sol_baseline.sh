#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is not set. Load it from your shell configuration first." >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CONCURRENCY="${CONCURRENCY:-95}"
RESULT_FILE="$REPO_ROOT/inference/results/baselines/gpt-5.6-sol_standard.jsonl"
EVAL_DIR="$REPO_ROOT/evaluation/output/baselines/gpt-5.6-sol/omni-math"

"$PYTHON_BIN" "$REPO_ROOT/scripts/preflight_gpt56_sol.py"

"$PYTHON_BIN" "$REPO_ROOT/inference/inference_api.py" \
  --provider openrouter \
  --model openai/gpt-5.6-sol \
  --openrouter-provider openai \
  --reasoning-effort high \
  --omit-temperature \
  --max_tokens 64000 \
  --num_samples 100 \
  --seed 100 \
  --concurrency "$CONCURRENCY" \
  --data_file "$REPO_ROOT/omni_math_rule.jsonl" \
  --prompt standard \
  --save_path "$RESULT_FILE"

"$PYTHON_BIN" "$REPO_ROOT/scripts/evaluate_gpt56_sol_baseline.py" \
  --data-file "$RESULT_FILE" \
  --output-dir "$EVAL_DIR" \
  --dataset-file "$REPO_ROOT/omni_math_rule.jsonl"

"$PYTHON_BIN" "$REPO_ROOT/scripts/summarize_gpt56_sol.py" \
  --repo-root "$REPO_ROOT" \
  --num-samples 100
