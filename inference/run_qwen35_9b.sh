#!/usr/bin/env bash
# Run Qwen3.5 locally via vLLM and evaluate on Omni-MATH-Rule.
#
# Usage:
#   bash inference/run_qwen35_9b.sh [PROMPT] [NUM_SAMPLES]
#
# Examples:
#   bash inference/run_qwen35_9b.sh standard 100
#   bash inference/run_qwen35_9b.sh cautious 500
#   bash inference/run_qwen35_9b.sh standard 0   # 0 = all 2821 problems
#
# The script:
#   1. Starts a vLLM OpenAI-compatible server for Qwen 3.5 on port 8000
#      (skipped if a healthy server is already listening on that port)
#   2. Runs inference_api.py --provider vllm
#   3. Shuts down the vLLM server (only if this script started it)
#   4. Runs standard evaluation

set -euo pipefail

PROMPT="${1:-standard}"
NUM_SAMPLES="${2:-100}"
MODEL_ID="Qwen/Qwen3.5-0.8B"
MODEL_SHORT="qwen3.5-0.8b"
PORT=8000
VLLM_SERVER_LOG="inference/results/${MODEL_SHORT}_vllm_server.log"
SAVE_PATH="inference/results/${MODEL_SHORT}-${PROMPT}.jsonl"
MAX_MODEL_LEN=32768   # keep modest for throughput; increase if you need longer reasoning
MAX_TOKENS=30000
CONCURRENCY=8         # concurrent requests to the local server

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo " ${MODEL_ID} |  prompt=${PROMPT}  |  N=${NUM_SAMPLES}"
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
        echo "         Proceeding anyway — pass --model ${RUNNING_MODEL} to inference if needed."
    fi
else
    echo "[1/3] Starting vLLM server for ${MODEL_ID} on port ${PORT}..."
    vllm serve "$MODEL_ID" \
        --port "$PORT" \
        --tensor-parallel-size 1 \
        --max-model-len "$MAX_MODEL_LEN" \
        --reasoning-parser qwen3 \
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
    --temperature 1 \
    --max_tokens "$MAX_TOKENS" \
    --concurrency "$CONCURRENCY"

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
EXP_NAME="${MODEL_SHORT}-${PROMPT}"
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
