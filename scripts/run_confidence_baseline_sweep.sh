#!/usr/bin/env bash
# Run the simultaneous-consequence baseline cells needed for the
# baseline-abstention / Int2-confidence analysis.

set -u

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
CONCURRENCY="${CONCURRENCY:-20}"
NUM_SAMPLES="${NUM_SAMPLES:-100}"
SEED="${SEED:-100}"
TEMPERATURE="${TEMPERATURE:-1.0}"
MAX_TOKENS="${MAX_TOKENS:-64000}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/qualitative_quantitative_sweep}"
LOG_DIR="${LOG_DIR:-inference/results/qualitative_quantitative_sweep/logs}"

mkdir -p "$RESULTS_DIR" "$LOG_DIR"

MODELS=(
  "claude-haiku-4-5|anthropic|claude-haiku-4-5|"
  "deepseek-v4-pro|openrouter|deepseek/deepseek-v4-pro|DeepSeek"
  "gemini-3.1-flash-lite-preview|openrouter|google/gemini-3.1-flash-lite-preview|"
  "qwen3.5-397b|openrouter|qwen/qwen3.5-397b-a17b|"
)

CONFIGS=("QP6" "QP7" "Quant-25" "Quant-100")

pids=()
labels=()
outputs=()

launch_cell() {
  local slug="$1"
  local provider="$2"
  local model="$3"
  local openrouter_provider="$4"
  local config="$5"
  local prompt
  local suffix
  local rubric_incorrect=""

  case "$config" in
    QP6|QP7)
      prompt="$config"
      suffix="$config"
      ;;
    Quant-25)
      prompt="quantitative_grading"
      suffix="quant_1_0_-25"
      rubric_incorrect="-25"
      ;;
    Quant-100)
      prompt="quantitative_grading"
      suffix="quant_1_0_-100"
      rubric_incorrect="-100"
      ;;
    *)
      echo "Unknown config: $config" >&2
      return 2
      ;;
  esac

  local out="$RESULTS_DIR/${slug}_${suffix}.jsonl"
  local log="$LOG_DIR/${slug}_${suffix}.log"
  local cmd=(
    "$PYTHON_BIN" inference/inference_api.py
    --provider "$provider"
    --model "$model"
    --prompt "$prompt"
    --save_path "$out"
    --num_samples "$NUM_SAMPLES"
    --seed "$SEED"
    --temperature "$TEMPERATURE"
    --max_tokens "$MAX_TOKENS"
    --concurrency "$CONCURRENCY"
  )

  if [[ -n "$rubric_incorrect" ]]; then
    cmd+=(
      --rubric_correct 1
      --rubric_abstain 0
      --rubric_incorrect "$rubric_incorrect"
    )
  fi
  if [[ -n "$openrouter_provider" ]]; then
    cmd+=(--openrouter-provider "$openrouter_provider")
  fi
  if [[ "$provider" == "openrouter" ]]; then
    cmd+=(--openrouter-stream)
  fi

  echo "Launching $slug / $config -> $out"
  "${cmd[@]}" >"$log" 2>&1 &
  pids+=("$!")
  labels+=("$slug/$config")
  outputs+=("$out")
}

for entry in "${MODELS[@]}"; do
  IFS='|' read -r slug provider model openrouter_provider <<<"$entry"
  for config in "${CONFIGS[@]}"; do
    launch_cell "$slug" "$provider" "$model" "$openrouter_provider" "$config"
  done
done

echo "Launched ${#pids[@]} cells with up to $CONCURRENCY requests per cell."

failed=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    echo "Completed ${labels[$i]}"
  else
    echo "FAILED ${labels[$i]} (see its log)" >&2
    failed=$((failed + 1))
  fi
done

echo "All cells exited; failed processes: $failed"

incomplete=0
for i in "${!outputs[@]}"; do
  rows=0
  nonempty=0
  if [[ -f "${outputs[$i]}" ]]; then
    rows="$(wc -l <"${outputs[$i]}")"
    nonempty="$(
      "$PYTHON_BIN" - "${outputs[$i]}" <<'PY'
import json
import sys

count = 0
with open(sys.argv[1], encoding="utf-8") as handle:
    for line in handle:
        if line.strip():
            row = json.loads(line)
            count += bool(str(row.get("model_generation", "")).strip())
print(count)
PY
    )"
  fi
  if [[ "$rows" -ne "$NUM_SAMPLES" || "$nonempty" -ne "$NUM_SAMPLES" ]]; then
    echo "INCOMPLETE ${labels[$i]}: $rows/$NUM_SAMPLES rows, $nonempty non-empty" >&2
    incomplete=$((incomplete + 1))
  fi
done

echo "Incomplete cells: $incomplete"
exit $((failed + incomplete))
