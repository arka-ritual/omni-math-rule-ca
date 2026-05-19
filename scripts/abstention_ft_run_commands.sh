#!/usr/bin/env bash
set -euo pipefail

# Run from repo root.
# Set SKIP_EXISTING=0 to force rerun everything.
SKIP_EXISTING="${SKIP_EXISTING:-1}"

POSTTRAINED_MODEL="google/gemma-4-E2B-it"

GEN_TEMP="1.0"
GEN_TOP_P="1.0"
GEN_TOP_K="-1"
GEN_MAX_TOKENS="8192"
GEN_MAX_MODEL_LEN="8192"

# Bumped from 8192 -> 16384 to fit longer prefix_k * problem combinations and
# cover a larger fraction of the eligible label budget.
TRAIN_MAX_SEQ_LENGTH="${TRAIN_MAX_SEQ_LENGTH:-16384}"

# ─────────────────── Experimental axes ────────────────────────────────────────
# These are arrays so the cross-product is expanded by the loops below.

# Total #training examples per file.
SIZES=(250 500 1000)

# Fraction of rows whose target is the abstention string. p_abst=0.5 reproduces
# the previous 50/50 split. With 728 correct / 1058 incorrect (k=512) eligible,
# (n=1000, p_abst=0.25) needs 750 correct → unsatisfiable; build runs with
# --allow_partial so such cells are skipped (with a warning) rather than failing.
ABSTENTION_FRACTIONS=(0.25 0.5 0.75)

# Rubrics. mix_m25_m100 mixes per-row system prompts across the two quant
# rubrics so the model learns rubric-conditional abstention.
RUBRICS=(quant_m25 mix_m25_m100)

PREFIX_KS=(512 1024)
METHODS=(sft dpo sft_box)

# Tune mode: qlora (4-bit + LoRA r=16) or full (bf16 full FT).
# For Gemma 4 E2B, full FT fits on a single 80GB A100 with grad checkpointing.
TUNE_MODES=(qlora full)

# Reminder: the previous default max_grad_norm=1.0 may have been clipping
# benign-but-large grads. Set GRAD_NORM=5.0 (or higher, e.g. 1e9 to disable
# clipping while still recording the natural distribution in the trainer log).
GRAD_NORM="${GRAD_NORM:-5.0}"

# Eval-time prompts. The model is evaluated under each — including held-out
# rubrics it never saw during training (e.g. quant_m100 when training on m25 only).
PROMPTS=(ultra_cautious quant_m25 quant_m100 QP4 QP7)
CAUTIOUS_PROMPTS=(ultra_cautious quant_m25 quant_m100 QP4 QP7)
NATURAL_PROMPTS=()

# Paths — swap to abstention_ft_small / eval_small.json for quick signal runs,
# or abstention_ft / eval.jsonl for full 500-problem eval.
EVAL_DATA="data/abstention_ft/eval.jsonl"
RESULTS_DIR="inference/results/abstention_ft"
EVAL_DIR="evaluation/output/abstention_ft"

mkdir -p data/abstention_ft "$RESULTS_DIR" "$EVAL_DIR" checkpoints/abstention_ft logs/abstention_ft
LOG_DIR="logs/abstention_ft/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

STEP=0
LAST_LOG=""

run() {
  local name="$1"; shift
  local log
  printf -v log "%s/%03d_%s.log" "$LOG_DIR" "$STEP" "$name"
  LAST_LOG="$log"
  echo "[start] $name"
  "$@" >"$log" 2>&1
  echo "[done]  $name -> $log"
  STEP=$((STEP + 1))
}

run_if_file_missing() {
  local marker="$1"; shift
  local name="$1"; shift
  if [[ "$SKIP_EXISTING" == "1" && -s "$marker" ]]; then
    echo "[skip]  $name -> $marker exists"
  else
    run "$name" "$@"
  fi
}

run_if_marker_missing() {
  local marker="$1"; shift
  local name="$1"; shift
  if [[ "$SKIP_EXISTING" == "1" && -e "$marker" ]]; then
    echo "[skip]  $name -> $marker exists"
  else
    run "$name" "$@"
  fi
}

on_err() {
  echo "[fail] command failed. Last log: $LAST_LOG"
  if [[ -n "$LAST_LOG" && -f "$LAST_LOG" ]]; then
    echo "------ tail $LAST_LOG ------"
    tail -80 "$LAST_LOG" || true
  fi
}
trap on_err ERR

gen_args=(
  --temperature "$GEN_TEMP"
  --top_p "$GEN_TOP_P"
  --top_k "$GEN_TOP_K"
  --max_tokens "$GEN_MAX_TOKENS"
  --max_model_len "$GEN_MAX_MODEL_LEN"
  --seed 42
  --batch_size 512
  --tensor_parallel_size 1
  --enable_thinking
  --gpu_memory_utilization 0.95
  --max_num_batched_tokens 65536
)

echo "[info] logs: $LOG_DIR"
echo "[info] generation max_tokens=$GEN_MAX_TOKENS max_model_len=$GEN_MAX_MODEL_LEN"
echo "[info] training max_seq_length=$TRAIN_MAX_SEQ_LENGTH max_grad_norm=$GRAD_NORM"
echo "[info] sizes=(${SIZES[*]}) p_abst=(${ABSTENTION_FRACTIONS[*]}) rubrics=(${RUBRICS[*]})"
echo "[info] prefix_ks=(${PREFIX_KS[*]}) methods=(${METHODS[*]}) tune_modes=(${TUNE_MODES[*]})"
echo "[info] SKIP_EXISTING=$SKIP_EXISTING"

# run "make_splits" \
#   python scripts/abstention_ft_make_splits.py \
#     --omni omni_math_rule.jsonl \
#     --eval_file inference/results/eval.jsonl \
#     --out_dir data/abstention_ft

run_if_file_missing inference/results/abstention_ft/label_gemma4_e2b_standard.jsonl "label_generate_gemma4_e2b" \
  python inference/inference_vllm.py \
    --model "$POSTTRAINED_MODEL" \
    --data_file data/abstention_ft/train_candidates.jsonl \
    --save_path inference/results/abstention_ft/label_gemma4_e2b_standard.jsonl \
    --prompt standard \
    "${gen_args[@]}"

run_if_file_missing data/abstention_ft/gemma4_e2b/labeled_standard.jsonl "label_score_gemma4_e2b" \
  python scripts/abstention_ft_label_standard.py \
    --input inference/results/abstention_ft/label_gemma4_e2b_standard.jsonl \
    --output data/abstention_ft/gemma4_e2b/labeled_standard.jsonl

# Build all (method × rubric × k × n × p_abst) training files in one pass.
# Marker is the largest-N, p50, first-rubric, first-k, sft file — sufficient
# to detect a fully-built corpus (the build script writes the full grid atomically
# per invocation; partial cells are tolerated via --allow_partial).
BUILD_MARKER="data/abstention_ft/gemma4_e2b/sft_n${SIZES[-1]}_${RUBRICS[0]}_k${PREFIX_KS[0]}_p50.jsonl"
run_if_file_missing "$BUILD_MARKER" "build_train_data_gemma4_e2b" \
  python scripts/abstention_ft_build_train_data.py \
    --labeled data/abstention_ft/gemma4_e2b/labeled_standard.jsonl \
    --model_slug gemma4_e2b \
    --base_model "$POSTTRAINED_MODEL" \
    --max_seq_length "$TRAIN_MAX_SEQ_LENGTH" \
    --sizes "${SIZES[@]}" \
    --abstention_fractions "${ABSTENTION_FRACTIONS[@]}" \
    --rubrics "${RUBRICS[@]}" \
    --prefix_ks "${PREFIX_KS[@]}" \
    --methods "${METHODS[@]}" \
    --allow_partial \
    --seed 42

p_pct() {
  python3 -c "import sys; print(f'{int(round(float(sys.argv[1])*100)):02d}')" "$1"
}

for model_slug in gemma4_e2b; do
  base_model="$POSTTRAINED_MODEL"
  for tune in "${TUNE_MODES[@]}"; do
    for rubric in "${RUBRICS[@]}"; do
      for k in "${PREFIX_KS[@]}"; do
        for n in "${SIZES[@]}"; do
          for p in "${ABSTENTION_FRACTIONS[@]}"; do
            pp=$(p_pct "$p")
            for method in "${METHODS[@]}"; do
              train_file="data/abstention_ft/${model_slug}/${method}_n${n}_${rubric}_k${k}_p${pp}.jsonl"
              if [[ ! -s "$train_file" ]]; then
                echo "[skip]  train ${model_slug} ${tune} ${method} n=${n} ${rubric} k=${k} p=${pp} -> training file absent (likely budget-skipped)"
                continue
              fi
              out_dir="checkpoints/abstention_ft/${model_slug}/${tune}_${method}_n${n}_${rubric}_k${k}_p${pp}"
              if [[ "$tune" == "qlora" ]]; then
                marker="${out_dir}/adapter_config.json"
              else
                marker="${out_dir}/config.json"
              fi
              run_if_marker_missing "$marker" "train_${model_slug}_${tune}_${method}_n${n}_${rubric}_k${k}_p${pp}" \
                python "scripts/abstention_ft_train_${method}.py" \
                  --base_model "$base_model" \
                  --train_file "$train_file" \
                  --output_dir "$out_dir" \
                  --max_seq_length "$TRAIN_MAX_SEQ_LENGTH" \
                  --peft_mode "$tune" \
                  --max_grad_norm "$GRAD_NORM"
            done
          done
        done
      done
    done
  done
done


VARIANTS=(gemma4_e2b_original)
MODEL_PATHS=("$POSTTRAINED_MODEL")
ADAPTER_PATHS=("")
TUNE_KINDS=("original")

for model_slug in gemma4_e2b; do
  base_model="$POSTTRAINED_MODEL"
  for tune in "${TUNE_MODES[@]}"; do
    for rubric in "${RUBRICS[@]}"; do
      for k in "${PREFIX_KS[@]}"; do
        for n in "${SIZES[@]}"; do
          for p in "${ABSTENTION_FRACTIONS[@]}"; do
            pp=$(p_pct "$p")
            for method in "${METHODS[@]}"; do
              ckpt_dir="checkpoints/abstention_ft/${model_slug}/${tune}_${method}_n${n}_${rubric}_k${k}_p${pp}"
              if [[ "$tune" == "qlora" ]]; then
                marker="${ckpt_dir}/adapter_config.json"
              else
                marker="${ckpt_dir}/config.json"
              fi
              if [[ ! -e "$marker" ]]; then
                continue
              fi
              variant="${model_slug}_${tune}_${method}_n${n}_${rubric}_k${k}_p${pp}"
              VARIANTS+=("$variant")
              if [[ "$tune" == "qlora" ]]; then
                MODEL_PATHS+=("$base_model")
                ADAPTER_PATHS+=("$ckpt_dir")
              else
                MODEL_PATHS+=("$ckpt_dir")
                ADAPTER_PATHS+=("")
              fi
              TUNE_KINDS+=("$tune")
            done
          done
        done
      done
    done
  done
done


for i in "${!VARIANTS[@]}"; do
  variant="${VARIANTS[$i]}"
  model_path="${MODEL_PATHS[$i]}"
  adapter_path="${ADAPTER_PATHS[$i]}"

  for prompt in "${PROMPTS[@]}"; do
    out="${RESULTS_DIR}/${variant}__${prompt}.jsonl"

    if [[ -n "$adapter_path" ]]; then
      run_if_file_missing "$out" "eval_gen_${variant}__${prompt}" \
        python inference/inference_vllm.py \
          --model "$model_path" \
          --lora_adapter "$adapter_path" \
          --data_file "$EVAL_DATA" \
          --save_path "$out" \
          --prompt "$prompt" \
          "${gen_args[@]}"
    else
      run_if_file_missing "$out" "eval_gen_${variant}__${prompt}" \
        python inference/inference_vllm.py \
          --model "$model_path" \
          --data_file "$EVAL_DATA" \
          --save_path "$out" \
          --prompt "$prompt" \
          "${gen_args[@]}"
    fi
  done
done


for variant in "${VARIANTS[@]}"; do
  for prompt in "${CAUTIOUS_PROMPTS[@]}"; do
    run_if_file_missing "${EVAL_DIR}/${variant}__${prompt}/cautious_metrics.json" "score_cautious_${variant}__${prompt}" \
      python evaluation/math_eval_cautious.py \
        --data_file "${RESULTS_DIR}/${variant}__${prompt}.jsonl" \
        --output_dir "/home/paperspace/Public/omni-math-rule-ca/${EVAL_DIR}/${variant}__${prompt}"
  done
done

for prompt in "${CAUTIOUS_PROMPTS[@]}"; do
  run "aggregate_${prompt}" \
    python scripts/abstention_ft_aggregate.py \
      --results_dir "$RESULTS_DIR" \
      --output_root "$EVAL_DIR" \
      --prompt "$prompt" \
      --summary_csv "${EVAL_DIR}/summary_${prompt}.csv" \
      --summary_md "${EVAL_DIR}/summary_${prompt}.md"
done

echo "[finished] all stages complete"
echo "[finished] logs: $LOG_DIR"
