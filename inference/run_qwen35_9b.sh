#!/usr/bin/env bash
# Run a local vLLM-served model and evaluate on Omni-MATH-Rule.
#
# Usage:
#   bash inference/run_qwen35_9b.sh PROMPT NUM_SAMPLES [extra inference_api.py args...]
#
# Examples:
#   bash inference/run_qwen35_9b.sh standard 100
#   bash inference/run_qwen35_9b.sh cautious 500
#   bash inference/run_qwen35_9b.sh standard 0
#   # Base-model autocomplete mode:
#   bash inference/run_qwen35_9b.sh standard 100 --base_model
#   # Base model + 4-shot scaffolding (variant chosen at runtime).
#   # Valid fewshot variants (paper order):
#   #   0. normal                  baseline, no consequences anywhere
#   #   1. no_conseq               consequences ONLY in the final query
#   #   2. conseq_no_abstain       consequences in examples+query, no decisions (paper: no_decision)
#   #   3. conseq_random_abstain   + random ANSWER/ABSTAIN decisions            (paper: full)
#   #   4. conseq_correct_abstain  + correct->ANSWER, wrong->ABSTAIN            (paper: correct)
#   #   5. conseq_always_submit    + always ANSWER                              (paper: all_submit)
#   #   6. conseq_always_abstain   + always ABSTAIN                             (paper: all_abstain)
#   bash inference/run_qwen35_9b.sh cautious 100 --base_model --fewshot_variant conseq_correct_abstain
#   bash inference/run_qwen35_9b.sh quantitative_grading 100 --base_model --fewshot_variant no_conseq
#
# The script:
#   1. Starts a vLLM OpenAI-compatible server on port 8000
#      (skipped if a healthy server is already listening on that port)
#   2. Runs inference_api.py --provider vllm
#   3. Shuts down the vLLM server (only if this script started it)
#   4. Runs the appropriate evaluation (standard or cautious)

set -euo pipefail

PROMPT="${1:-standard}"
NUM_SAMPLES="${2:-100}"
shift 2 2>/dev/null || true   # any remaining args are forwarded to inference_api.py
EXTRA_ARGS=("$@")

MODEL_ID="Qwen/Qwen3.5-9B-Base"
MODEL_SHORT="Qwen3.5-9B-base"
PORT=8000
VLLM_SERVER_LOG="inference/results/${MODEL_SHORT}_vllm_server.log"
MAX_MODEL_LEN=232000
MAX_TOKENS=128000
CONCURRENCY=8
SEED=100   # pinned so reruns with a smaller --num_samples reuse the prefix

# Build a save-path suffix that reflects fewshot/base-model/rubric settings
# (so runs with the same prompt but different scaffolding don't clobber).
SUFFIX="$PROMPT"
NEXT=""
RC=""; RI=""; RA=""
for arg in "${EXTRA_ARGS[@]}"; do
    case "$arg" in
        --fewshot_variant) NEXT="fs" ;;
        --rubric_correct)  NEXT="rc" ;;
        --rubric_incorrect) NEXT="ri" ;;
        --rubric_abstain)  NEXT="ra" ;;
        --base_model) SUFFIX="${SUFFIX}_basemodel" ;;
        *)
            case "$NEXT" in
                fs) SUFFIX="${SUFFIX}_fs-${arg}" ;;
                rc) RC="$arg" ;;
                ri) RI="$arg" ;;
                ra) RA="$arg" ;;
            esac
            NEXT=""
            ;;
    esac
done
if [[ "$PROMPT" == "quantitative_grading" && ( -n "$RC" || -n "$RI" || -n "$RA" ) ]]; then
    SUFFIX="${SUFFIX}_r${RC:-1}_${RI:--10}_${RA:-0}"
fi
SAVE_PATH="inference/results/${MODEL_SHORT}-${SUFFIX}.jsonl"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo " ${MODEL_ID} | prompt=${PROMPT} | N=${NUM_SAMPLES}"
echo " extra args: ${EXTRA_ARGS[*]:-(none)}"
echo " save_path : ${SAVE_PATH}"
echo "=========================================="

mkdir -p inference/results

# ── 1. Start vLLM server (skip if already healthy) ────────────────────────
VLLM_PID=""
if curl -sf "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    RUNNING_MODEL=$(curl -s "http://localhost:${PORT}/v1/models" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['id'])" 2>/dev/null \
        || echo "unknown")
    echo "[1/3] vLLM server already running on port ${PORT} (model: ${RUNNING_MODEL}) — skipping startup."
    if [ "$RUNNING_MODEL" != "$MODEL_ID" ]; then
        echo "WARNING: Running model (${RUNNING_MODEL}) differs from requested (${MODEL_ID})."
        echo "         Will pass --model ${RUNNING_MODEL} to inference."
        MODEL_ID="$RUNNING_MODEL"
    fi
else
    echo "[1/3] Starting vLLM server for ${MODEL_ID} on port ${PORT}..."
    vllm serve "$MODEL_ID" \
        --port "$PORT" \
        --tensor-parallel-size 1 \
        --max-model-len "$MAX_MODEL_LEN" \
        --gpu-memory-utilization 0.90 \
        > "$VLLM_SERVER_LOG" 2>&1 &
    VLLM_PID=$!
    echo "vLLM PID: ${VLLM_PID}  (log: ${VLLM_SERVER_LOG})"

    echo "Waiting for server to be ready..."
    MAX_WAIT=300
    WAITED=0
    until curl -sf "http://localhost:${PORT}/health" > /dev/null 2>&1; do
        if [ $WAITED -ge $MAX_WAIT ]; then
            echo "ERROR: vLLM server did not become healthy within ${MAX_WAIT}s."
            echo "Last log lines:"
            tail -20 "$VLLM_SERVER_LOG"
            kill "$VLLM_PID" 2>/dev/null || true
            exit 1
        fi
        sleep 5
        WAITED=$((WAITED + 5))
        echo "  ...still waiting (${WAITED}s elapsed)"
    done
    echo "Server is up!"
fi

# ── 2. Run inference ───────────────────────────────────────────────────────
echo "[2/3] Running inference → ${SAVE_PATH}"
python inference/inference_api.py \
    --provider vllm \
    --model "$MODEL_ID" \
    --save_path "$SAVE_PATH" \
    --prompt "$PROMPT" \
    --num_samples "$NUM_SAMPLES" \
    --seed "$SEED" \
    --temperature 1 \
    --max_tokens "$MAX_TOKENS" \
    --concurrency "$CONCURRENCY" \
    "${EXTRA_ARGS[@]}"

# ── 3. Shut down vLLM server (only if we started it) ──────────────────────
if [ -n "$VLLM_PID" ]; then
    echo "[3/3] Shutting down vLLM server (PID ${VLLM_PID})..."
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
    echo "Server stopped."
else
    echo "[3/3] Server was pre-existing — leaving it running."
fi

# ── 4. Evaluate ────────────────────────────────────────────────────────────
EXP_NAME="${MODEL_SHORT}-${SUFFIX}"
echo ""
echo "=========================================="
echo " Evaluating: ${EXP_NAME}"
echo "=========================================="

if [[ "$PROMPT" == "standard" ]]; then
    python evaluation/math_eval.py \
        --data_name omni-math \
        --exp_name "$EXP_NAME" \
        --input_path "$SAVE_PATH" \
        --output_dir "evaluation/output/"
    echo "Results: evaluation/output/${EXP_NAME}/omni-math/math_eval_cot_metrics.json"
else
    python evaluation/math_eval_cautious.py \
        --data_file "$SAVE_PATH" \
        --output_dir "evaluation/output/${EXP_NAME}/omni-math/"
    echo "Results: evaluation/output/${EXP_NAME}/omni-math/cautious_metrics.json"
fi

echo "Done."
