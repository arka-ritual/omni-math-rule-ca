#!/usr/bin/env bash
# OOD non-agentic generalization test: evaluate the fixed-quant_m25 checkpoints
# (and the original base model) on Humanity's Last Exam (Humanities/Social
# Science slice) under the standard prompt + the CA framings, mirroring the
# Omni-MATH (in-distribution) and SWE-bench Pro (OOD agentic) evals.
#
# Results are namespaced to *_hle dirs so they never collide with the Omni-MATH
# runs that share the same {variant}__{prompt} naming.
#
# Resumable: skips any cell whose results already exist.
#
# Usage:
#   bash inference/run_hle_ood.sh                       # gemma, all framings
#   MODEL=qwen bash inference/run_hle_ood.sh            # qwen3.5-9b
#   PROMPTS="standard quant_m25" bash inference/run_hle_ood.sh
set -euo pipefail

MODEL="${MODEL:-gemma}"
case "$MODEL" in
  gemma)
    BASE_MODEL_DEFAULT="google/gemma-4-E2B-it"
    CKPT_ROOT_DEFAULT="checkpoints/abstention_ft/gemma4_axisEpochsXPabst"
    SLUG_PREFIX_DEFAULT="gemma4_e2b" ;;
  qwen)
    BASE_MODEL_DEFAULT="Qwen/Qwen3.5-9B"
    CKPT_ROOT_DEFAULT="checkpoints/abstention_ft/qwen35_axisEpochsXPabst"
    SLUG_PREFIX_DEFAULT="qwen35_9b" ;;
  *) echo "Unknown MODEL='$MODEL' (use gemma|qwen)." >&2; exit 1 ;;
esac

BASE_MODEL="${BASE_MODEL:-$BASE_MODEL_DEFAULT}"
CKPT_ROOT="${CKPT_ROOT:-$CKPT_ROOT_DEFAULT}"
SLUG_PREFIX="${SLUG_PREFIX:-$SLUG_PREFIX_DEFAULT}"
DATA_FILE="${DATA_FILE:-data/hle/hle_humanities_ss_n100.jsonl}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/abstention_ft_hle}"
OUTPUT_DIR="${OUTPUT_DIR:-evaluation/output/abstention_ft_hle}"
PROMPTS="${PROMPTS:-standard quant_m5 quant_m25 quant_m100 QP1 QP4 QP7}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16700}"
MAX_TOKENS="${MAX_TOKENS:-16384}"

gen_args=(--temperature 1.0 --top_p 1.0 --top_k -1 --max_tokens "${MAX_TOKENS}"
          --max_model_len "${MAX_MODEL_LEN}" --seed 42 --batch_size 512
          --tensor_parallel_size 1 --enable_thinking
          --gpu_memory_utilization 0.95 --max_num_batched_tokens 65536
          --max_lora_rank 64)

run_cell() {  # $1 = variant slug, $2 = adapter dir ("" for base), $3 = prompt
  local variant="$1" adapter="$2" prompt="$3"
  local out="${RESULTS_DIR}/${variant}__${prompt}.jsonl"
  local eval_out="${OUTPUT_DIR}/${variant}__${prompt}"
  if [[ -s "$out" && -s "${eval_out}/cautious_metrics.json" ]]; then
    echo "[skip] ${variant}__${prompt} (done)"; return
  fi
  echo "[run ] ${variant}__${prompt}  adapter='${adapter:-<base>}'"
  local lora_args=()
  [[ -n "$adapter" ]] && lora_args=(--lora_adapter "$adapter")
  python inference/inference_vllm.py \
    --model "$BASE_MODEL" "${lora_args[@]}" \
    --data_file "$DATA_FILE" \
    --save_path "$out" \
    --prompt "$prompt" "${gen_args[@]}"
  python evaluation/math_eval_cautious.py \
    --data_file "$out" \
    --output_dir "$eval_out"
}

echo "[info] MODEL=$MODEL  BASE_MODEL=$BASE_MODEL  CKPT_ROOT=$CKPT_ROOT"
echo "[info] DATA_FILE=$DATA_FILE  PROMPTS='$PROMPTS'"

# 1) Original (untrained) baseline across all framings.
for prompt in $PROMPTS; do
  run_cell "${SLUG_PREFIX}_original" "" "$prompt"
done

# 2) Every fixed-quant_m25 checkpoint snapshot x framing.
shopt -s nullglob
for ckpt_dir in "${CKPT_ROOT}"/qlora_*_n500_quant_m25_k512_*/; do
  base_name="$(basename "$ckpt_dir")"
  method="$(echo "$base_name" | sed -E 's/^qlora_(.+)_n500_quant_m25_k512_.*/\1/')"
  p_tag="$(echo "$base_name" | sed -E 's/.*_[pq]([0-9]+)$/\1/')"
  pp="$(printf '%02d' "$p_tag")"
  for ep_dir in "${ckpt_dir}"epoch-*/; do
    [[ -f "${ep_dir}adapter_config.json" ]] || continue
    ep_tag="$(basename "$ep_dir" | sed -E 's/^epoch-//')"
    variant="${SLUG_PREFIX}_qlora_${method}_n500_quant_m25_k512_p${pp}_ep${ep_tag}"
    for prompt in $PROMPTS; do
      run_cell "$variant" "${ep_dir%/}" "$prompt"
    done
  done
done

echo "[done] HLE OOD runs complete for MODEL=$MODEL."
