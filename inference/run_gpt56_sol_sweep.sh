#!/usr/bin/env bash
set -euo pipefail

# The repository currently tracks some evaluator __pycache__ files. Avoid
# rewriting those generated artifacts while running this experiment.
export PYTHONDONTWRITEBYTECODE=1

MODE="${1:-pilot}"
case "$MODE" in
  pilot)
    NUM_SAMPLES=5
    DEFAULT_CONCURRENCY=5
    ;;
  full)
    NUM_SAMPLES=100
    DEFAULT_CONCURRENCY=95
    ;;
  *)
    echo "Usage: $0 [pilot|full]" >&2
    exit 2
    ;;
esac

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is not set. Load it from your shell configuration first." >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CONCURRENCY="${CONCURRENCY:-$DEFAULT_CONCURRENCY}"
RESULT_ROOT="$REPO_ROOT/inference/results/qualitative_quantitative_sweep"
EVAL_ROOT="$REPO_ROOT/evaluation/output/qualitative_quantitative_sweep"

COMMON_ARGS=(
  --provider openrouter
  --model openai/gpt-5.6-sol
  --openrouter-provider openai
  --reasoning-effort high
  --omit-temperature
  --max_tokens 64000
  --num_samples "$NUM_SAMPLES"
  --seed 100
  --concurrency "$CONCURRENCY"
  --data_file "$REPO_ROOT/omni_math_rule.jsonl"
)

"$PYTHON_BIN" "$REPO_ROOT/scripts/preflight_gpt56_sol.py"

run_cell() {
  local slug="$1"
  shift
  local result_file="$RESULT_ROOT/gpt-5.6-sol_${slug}.jsonl"
  local eval_dir="$EVAL_ROOT/gpt-5.6-sol_${slug}"

  "$PYTHON_BIN" "$REPO_ROOT/inference/inference_api.py" \
    "${COMMON_ARGS[@]}" \
    --save_path "$result_file" \
    "$@"

  "$PYTHON_BIN" "$REPO_ROOT/evaluation/math_eval_cautious.py" \
    --data_file "$result_file" \
    --output_dir "$eval_dir"
}

mkdir -p "$RESULT_ROOT" "$EVAL_ROOT"

pids=()

run_cell quant_1_0_-100 \
  --prompt quantitative_grading \
  --rubric_correct 1 \
  --rubric_incorrect -100 \
  --rubric_abstain 0 &
pids+=("$!")

run_cell quant_-1_10_-10 \
  --prompt quantitative_grading \
  --rubric_correct -1 \
  --rubric_incorrect -10 \
  --rubric_abstain 10 &
pids+=("$!")

run_cell QP6 --prompt QP6 &
pids+=("$!")
run_cell QP7 --prompt QP7 &
pids+=("$!")

run_status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    run_status=1
  fi
done
if (( run_status != 0 )); then
  echo "At least one sweep cell failed; rerun the same command to resume missing rows." >&2
  exit "$run_status"
fi

"$PYTHON_BIN" "$REPO_ROOT/scripts/summarize_gpt56_sol.py" \
  --repo-root "$REPO_ROOT" \
  --num-samples "$NUM_SAMPLES"
