#!/usr/bin/env bash
# Sweep few-shot preamble variants on Gemma 4 E2B *instruct* (it).
#
# Companion to `inference/run_qwen35_9b.sh ... --base_model --fewshot_variant ...`
# but for the *instruction-tuned* version of the same family. The same
# preambles from `inference/fewshot.py` are reused — when --fewshot_variant
# is passed without --base_model, inference_api.py:
#   * clears the system prompt
#   * puts `preamble + format_query(...)` into the user message
#   * passes the stop sequences ["\nQ:", "\n\nQ:"] through
# so the chat-completions endpoint still gets the scaffolding intact.
#
# Cells produced (default config = ~21 runs at 100 samples each):
#   * gemma-4-E2B-it-{prompt}                              (no fewshot baseline)
#   * gemma-4-E2B-it-{prompt}_fs-{variant}                 (each fewshot variant)
#
# For the matching base-model + base-fewshot side, you already have
#   * gemma-4-E2B-{prompt}                                  (base baseline)
#   * gemma-4-E2B-{prompt}_basemodel_fs-{variant}           (base + fewshot)
# under `evaluation/output/` — `scripts/compare_fewshot_instruct_vs_base.py`
# joins all four sides into one markdown table.
#
# Usage:
#   bash inference/run_gemma4_e2b_it_fewshot.sh                  # default sweep
#   PROMPTS="ultra_cautious QP4" bash inference/run_gemma4_e2b_it_fewshot.sh
#   VARIANTS="normal no_conseq" NUM_SAMPLES=20 \
#       bash inference/run_gemma4_e2b_it_fewshot.sh
#   SKIP_EXISTING=0 bash inference/run_gemma4_e2b_it_fewshot.sh  # force rerun
#
# Env-var knobs:
#   PROMPTS        space-separated prompt presets        (default: "ultra_cautious")
#   VARIANTS       space-separated fewshot variants      (default: all 7)
#   NUM_SAMPLES    problems per cell, 0 = full 2,821     (default: 100)
#   SEED           sampling seed (pinned for resume)     (default: 100)
#   TEMPERATURE    sampling temperature                  (default: 1.0)
#   MAX_TOKENS     max completion tokens                 (default: 32768)
#   MAX_MODEL_LEN  vLLM max_model_len                    (default: 32768)
#   CONCURRENCY    in-flight requests                    (default: 16)
#   PORT           vLLM server port                      (default: 8000)
#   SKIP_EXISTING  skip cells whose save_path exists     (default: 1)
#   DO_COMPARE     run the compare script at the end     (default: 1)

set -euo pipefail
cd "$(dirname "$0")/.."

# ── knobs ──────────────────────────────────────────────────────────────────
MODEL_ID="${MODEL_ID:-google/gemma-4-E2B-it}"
MODEL_SHORT="${MODEL_SHORT:-gemma-4-E2B-it}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
MAX_TOKENS="${MAX_TOKENS:-32768}"
NUM_SAMPLES="${NUM_SAMPLES:-100}"
SEED="${SEED:-100}"
TEMPERATURE="${TEMPERATURE:-1.0}"
CONCURRENCY="${CONCURRENCY:-16}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
DO_COMPARE="${DO_COMPARE:-1}"

# Defaults chosen to match the prompts the base-model sweep used so the
# instruct results are directly comparable. Override via env if you want
# more / fewer.
PROMPTS_DEFAULT="ultra_cautious"
VARIANTS_DEFAULT="normal no_conseq conseq_no_abstain conseq_random_abstain conseq_correct_abstain conseq_always_submit conseq_always_abstain"

read -r -a PROMPTS_ARR  <<< "${PROMPTS:-$PROMPTS_DEFAULT}"
read -r -a VARIANTS_ARR <<< "${VARIANTS:-$VARIANTS_DEFAULT}"

RESULTS_DIR="inference/results"
EVAL_ROOT="evaluation/output"
VLLM_SERVER_LOG="${RESULTS_DIR}/${MODEL_SHORT}_vllm_server.log"

mkdir -p "$RESULTS_DIR"

echo "============================================================"
echo " ${MODEL_ID} | fewshot instruct sweep"
echo " prompts          : ${PROMPTS_ARR[*]}"
echo " fewshot variants : ${VARIANTS_ARR[*]}"
echo " num_samples      : ${NUM_SAMPLES}    seed=${SEED}"
echo " temperature      : ${TEMPERATURE}    max_tokens=${MAX_TOKENS}"
echo " concurrency      : ${CONCURRENCY}    skip_existing=${SKIP_EXISTING}"
echo "============================================================"

# ── 1. Start (or reuse) vLLM server ───────────────────────────────────────
VLLM_PID=""
if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    RUNNING_MODEL=$(curl -s "http://localhost:${PORT}/v1/models" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['id'])" 2>/dev/null \
        || echo "unknown")
    echo "[server] reusing existing vLLM on port ${PORT} (model: ${RUNNING_MODEL})"
    if [ "$RUNNING_MODEL" != "$MODEL_ID" ]; then
        echo "[server] WARNING: running model differs from requested. Using $RUNNING_MODEL."
        MODEL_ID="$RUNNING_MODEL"
    fi
else
    echo "[server] starting vLLM for ${MODEL_ID} on port ${PORT}..."
    vllm serve "$MODEL_ID" \
        --port "$PORT" \
        --tensor-parallel-size 1 \
        --max-model-len "$MAX_MODEL_LEN" \
        --gpu-memory-utilization 0.90 \
        > "$VLLM_SERVER_LOG" 2>&1 &
    VLLM_PID=$!
    echo "[server] PID=${VLLM_PID}  log=${VLLM_SERVER_LOG}"

    MAX_WAIT=300
    WAITED=0
    until curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; do
        if [ "$WAITED" -ge "$MAX_WAIT" ]; then
            echo "[server] ERROR: did not become healthy within ${MAX_WAIT}s"
            tail -40 "$VLLM_SERVER_LOG" || true
            kill "$VLLM_PID" 2>/dev/null || true
            exit 1
        fi
        sleep 5; WAITED=$((WAITED + 5))
        echo "[server]   ...still waiting (${WAITED}s)"
    done
    echo "[server] ready."
fi

cleanup () {
    if [ -n "$VLLM_PID" ]; then
        echo "[server] shutting down vLLM PID=${VLLM_PID}"
        kill "$VLLM_PID" 2>/dev/null || true
        wait "$VLLM_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ── 2. Helper: one inference + cautious-eval cell ─────────────────────────
run_cell () {
    local label="$1" prompt="$2" save_path="$3"; shift 3
    local extra_args=("$@")
    local exp_name eval_dir
    exp_name="$(basename "$save_path" .jsonl)"
    eval_dir="${EVAL_ROOT}/${exp_name}/omni-math"

    if [ "$SKIP_EXISTING" -eq 1 ] && [ -s "$save_path" ] && [ -s "${eval_dir}/cautious_metrics.json" ]; then
        echo "[skip ] ${label}  (have ${eval_dir}/cautious_metrics.json)"
        return
    fi

    echo
    echo "─── ${label} ─────────────────────────────────────────────"
    echo "  save_path : ${save_path}"
    if [ ! -s "$save_path" ] || [ "$SKIP_EXISTING" -ne 1 ]; then
        python inference/inference_api.py \
            --provider vllm \
            --model "$MODEL_ID" \
            --prompt "$prompt" \
            --save_path "$save_path" \
            --num_samples "$NUM_SAMPLES" --seed "$SEED" \
            --temperature "$TEMPERATURE" --max_tokens "$MAX_TOKENS" \
            --concurrency "$CONCURRENCY" \
            "${extra_args[@]}"
    fi

    echo "  scoring   : ${eval_dir}/cautious_metrics.json"
    mkdir -p "$eval_dir"
    python evaluation/math_eval_cautious.py \
        --data_file "$save_path" \
        --output_dir "$eval_dir"
}

# ── 3. Sweep ───────────────────────────────────────────────────────────────
for prompt in "${PROMPTS_ARR[@]}"; do
    base_no_fs="${RESULTS_DIR}/${MODEL_SHORT}-${prompt}.jsonl"
    run_cell "${prompt}  | no-fewshot baseline" "$prompt" "$base_no_fs"

    for variant in "${VARIANTS_ARR[@]}"; do
        out="${RESULTS_DIR}/${MODEL_SHORT}-${prompt}_fs-${variant}.jsonl"
        run_cell "${prompt}  | fewshot=${variant}" "$prompt" "$out" --fewshot_variant "$variant"
    done
done

# ── 4. Side-by-side comparison ────────────────────────────────────────────
if [ "$DO_COMPARE" -eq 1 ]; then
    echo
    echo "============================================================"
    echo " Side-by-side comparison"
    echo "============================================================"
    python scripts/compare_fewshot_instruct_vs_base.py \
        --prompts "${PROMPTS_ARR[@]}" \
        --variants "${VARIANTS_ARR[@]}" \
        --instruct_slug "${MODEL_SHORT}" \
        --base_slug "gemma-4-E2B" \
        --eval_root "$EVAL_ROOT" \
        --output_md "${EVAL_ROOT}/${MODEL_SHORT}-fewshot_vs_base.md"
fi

echo
echo "Done."
