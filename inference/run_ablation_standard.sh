#!/usr/bin/env bash
# Ablation: is the selective-accuracy gain from CA framing, or did finetuning on
# Omni-MATH data just make the model better at math?
#
# Re-evaluates the fixed-quant_m25 checkpoints under the *standard* prompt
# (NO consequence-asymmetry framing) on the same 100-problem eval slice, plus the
# original (untrained) base model as the baseline. Cautious eval gives raw
# accuracy, selective accuracy, and spurious-abstention rate under standard.
#
# Resumable: skips any (variant)__standard cell whose results already exist.
#
# Usage:
#   bash inference/run_ablation_standard.sh                 # gemma (default)
#   MODEL=qwen  bash inference/run_ablation_standard.sh     # qwen3.5-9b
#   MODEL=gemma bash inference/run_ablation_standard.sh
# Override any default via env (BASE_MODEL, CKPT_ROOT, SLUG_PREFIX, END, ...).
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
  *) echo "Unknown MODEL='$MODEL' (use gemma|qwen), or set BASE_MODEL/CKPT_ROOT/SLUG_PREFIX." >&2; exit 1 ;;
esac

BASE_MODEL="${BASE_MODEL:-$BASE_MODEL_DEFAULT}"
CKPT_ROOT="${CKPT_ROOT:-$CKPT_ROOT_DEFAULT}"
SLUG_PREFIX="${SLUG_PREFIX:-$SLUG_PREFIX_DEFAULT}"
DATA_FILE="${DATA_FILE:-data/abstention_ft/eval.jsonl}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/abstention_ft}"
OUTPUT_DIR="${OUTPUT_DIR:-evaluation/output/abstention_ft}"
END="${END:-100}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16700}"
MAX_TOKENS="${MAX_TOKENS:-16384}"
PROMPT="standard"

gen_args=(--temperature 1.0 --top_p 1.0 --top_k -1 --max_tokens "${MAX_TOKENS}"
          --max_model_len "${MAX_MODEL_LEN}" --seed 42 --batch_size 512
          --tensor_parallel_size 1 --enable_thinking
          --gpu_memory_utilization 0.95 --max_num_batched_tokens 65536
          --max_lora_rank 64 --end "${END}")

run_eval() {  # $1 = variant slug, $2 = lora adapter dir ("" for original/base)
  local variant="$1" adapter="$2"
  local out="${RESULTS_DIR}/${variant}__${PROMPT}.jsonl"
  local eval_out="${OUTPUT_DIR}/${variant}__${PROMPT}"
  if [[ -s "$out" && -s "${eval_out}/cautious_metrics.json" ]]; then
    echo "[skip] ${variant}__${PROMPT} (done)"; return
  fi
  echo "[run ] ${variant}__${PROMPT}  adapter='${adapter:-<base>}'"
  local lora_args=()
  [[ -n "$adapter" ]] && lora_args=(--lora_adapter "$adapter")
  python inference/inference_vllm.py \
    --model "$BASE_MODEL" "${lora_args[@]}" \
    --data_file "$DATA_FILE" \
    --save_path "$out" \
    --prompt "$PROMPT" "${gen_args[@]}"
  python evaluation/math_eval_cautious.py \
    --data_file "$out" \
    --output_dir "$eval_out"
}

echo "[info] MODEL=$MODEL  BASE_MODEL=$BASE_MODEL  CKPT_ROOT=$CKPT_ROOT  SLUG_PREFIX=$SLUG_PREFIX"

# 1) Original (untrained) baseline.
run_eval "${SLUG_PREFIX}_original" ""

# 2) Every fixed-quant_m25 checkpoint snapshot in CKPT_ROOT.
shopt -s nullglob
for ckpt_dir in "${CKPT_ROOT}"/qlora_*_n500_quant_m25_k512_*/; do
  base_name="$(basename "$ckpt_dir")"                       # qlora_dpo_n500_quant_m25_k512_q10
  method="$(echo "$base_name" | sed -E 's/^qlora_(.+)_n500_quant_m25_k512_.*/\1/')"
  p_tag="$(echo "$base_name" | sed -E 's/.*_[pq]([0-9]+)$/\1/')"  # 10 / 25 / 50 ...
  pp="$(printf '%02d' "$p_tag")"
  for ep_dir in "${ckpt_dir}"epoch-*/; do
    [[ -f "${ep_dir}adapter_config.json" ]] || continue
    ep_tag="$(basename "$ep_dir" | sed -E 's/^epoch-//')"   # 0p25 / 0p5 / 1 / 4
    variant="${SLUG_PREFIX}_qlora_${method}_n500_quant_m25_k512_p${pp}_ep${ep_tag}"
    run_eval "$variant" "${ep_dir%/}"
  done
done

echo "[done] ablation standard-prompt runs complete for MODEL=$MODEL."
