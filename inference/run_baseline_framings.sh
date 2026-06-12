#!/usr/bin/env bash
# Baseline grid: the ORIGINAL (untrained) model evaluated on the Omni-MATH eval
# slice under standard (no CA framing) + every CA framing, so we have a proper
# untrained anchor for each framing — mirroring the gpt-5.4-nano sweep in
# evaluation/output/qualitative_quantitative_sweep/summary.md.
#
# Framings: standard, quant_m{0_25,1,5,25,100} (penalty 0.25/1/5/25/100), QP1/4/7.
#
# Results land in the same abstention_ft namespace as the trained-model evals,
# under {slug}_original__{prompt}, so the summary/plot scripts treat them as the
# baseline. (The {slug}_original__standard cell is shared with
# run_ablation_standard.sh; the skip-if-done logic avoids recomputation.)
#
# Trained-model standard-prompt cells (the "no CA framing" trained baseline) are
# produced by inference/run_ablation_standard.sh.
#
# Usage:
#   bash inference/run_baseline_framings.sh                 # gemma (default)
#   MODEL=qwen bash inference/run_baseline_framings.sh      # qwen3.5-9b
#   PROMPTS="standard quant_m25" bash inference/run_baseline_framings.sh
set -euo pipefail

MODEL="${MODEL:-gemma}"
case "$MODEL" in
  gemma)
    BASE_MODEL_DEFAULT="google/gemma-4-E2B-it"
    SLUG_PREFIX_DEFAULT="gemma4_e2b" ;;
  qwen)
    BASE_MODEL_DEFAULT="Qwen/Qwen3.5-9B"
    SLUG_PREFIX_DEFAULT="qwen35_9b" ;;
  *) echo "Unknown MODEL='$MODEL' (use gemma|qwen)." >&2; exit 1 ;;
esac

BASE_MODEL="${BASE_MODEL:-$BASE_MODEL_DEFAULT}"
SLUG_PREFIX="${SLUG_PREFIX:-$SLUG_PREFIX_DEFAULT}"
DATA_FILE="${DATA_FILE:-data/abstention_ft/eval.jsonl}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/abstention_ft}"
OUTPUT_DIR="${OUTPUT_DIR:-evaluation/output/abstention_ft}"
PROMPTS="${PROMPTS:-standard quant_m0_25 quant_m1 quant_m5 quant_m25 quant_m100 QP1 QP4 QP7}"
END="${END:-100}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16700}"
MAX_TOKENS="${MAX_TOKENS:-16384}"

gen_args=(--temperature 1.0 --top_p 1.0 --top_k -1 --max_tokens "${MAX_TOKENS}"
          --max_model_len "${MAX_MODEL_LEN}" --seed 42 --batch_size 512
          --tensor_parallel_size 1 --enable_thinking
          --gpu_memory_utilization 0.95 --max_num_batched_tokens 65536
          --max_lora_rank 64 --end "${END}")

run_cell() {  # $1 = prompt
  local prompt="$1"
  local variant="${SLUG_PREFIX}_original"
  local out="${RESULTS_DIR}/${variant}__${prompt}.jsonl"
  local eval_out="${OUTPUT_DIR}/${variant}__${prompt}"
  if [[ -s "$out" && -s "${eval_out}/cautious_metrics.json" ]]; then
    echo "[skip] ${variant}__${prompt} (done)"; return
  fi
  echo "[run ] ${variant}__${prompt}"
  python inference/inference_vllm.py \
    --model "$BASE_MODEL" \
    --data_file "$DATA_FILE" \
    --save_path "$out" \
    --prompt "$prompt" "${gen_args[@]}"
  python evaluation/math_eval_cautious.py \
    --data_file "$out" \
    --output_dir "$eval_out"
}

echo "[info] MODEL=$MODEL  BASE_MODEL=$BASE_MODEL  SLUG_PREFIX=$SLUG_PREFIX"
echo "[info] PROMPTS='$PROMPTS'"
for prompt in $PROMPTS; do
  run_cell "$prompt"
done
echo "[done] original-model baseline framing grid complete for MODEL=$MODEL."
