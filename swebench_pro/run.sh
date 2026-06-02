#!/bin/bash
# Run mini-swe-agent on SWE-bench Pro instances and (optionally) grade
# the resulting patches with the official SWE-bench Pro Docker eval.
#
# Pipeline (default):
#   1. Inference: run_mini_on_pro.py over a shuffle-and-slice sample of
#      `data/swebench_pro_full.jsonl`, writing <output>/preds.json.
#      Fully resumable: re-running the same command (or with a larger
#      --n) skips instances already in preds.json.
#   2. Evaluation (official): scripts/run_eval.sh -> <output>/eval/eval_results.json
#
# Prereqs:
#   - pip install -r requirements.txt
#   - Docker installed and running (`docker --version` works)
#   - Relevant API key in env or in `.env` at the repo root, e.g.
#       ANTHROPIC_API_KEY=...   OPENAI_API_KEY=...   OPENROUTER_API_KEY=...
#       GEMINI_API_KEY=...
#
# Usage:
#   bash swebench_pro/run.sh --model openai/gpt-5-nano --n 1
#   bash swebench_pro/run.sh --model anthropic/claude-haiku-4-5-20251001 \
#                            --n 100 --workers 4 --eval-workers 8 \
#                            --output swebench_pro/results/haiku_n100
#   bash swebench_pro/run.sh --model openai/gpt-5-nano --n 50  # resume / extend a prior run
#
#   bash swebench_pro/run.sh --no-eval                          # inference only
#   bash swebench_pro/run.sh --eval-only --rundir <path>        # eval an existing rundir
#   bash swebench_pro/run.sh --gold-eval                        # grade gold patches (sanity check)
#
# Notes on resumability:
#   - Sampling is "shuffle-then-slice" with a fixed seed (default 100).
#     With the same seed, --n=20 is a strict prefix of --n=100, so an
#     interrupted run resumes exactly. To force fresh sampling, pass
#     --seed <n> with a different value (and a different --output).
#   - Resume is keyed on the instance ids already in <output>/preds.json.
#
# Consequence-asymmetry interventions (mirrors inference/run_interventions.sh):
#   --intervention {0,1,2,3,5}      0 = vanilla (no CA framing). Default 0.
#                                   5 = vanilla submit flow + consequence
#                                       framing in system prompt + the
#                                       `exit_abstain` tool. Use this for the
#                                       "consequence-only" sweep (closest
#                                       analogue to the math QP/quant runs).
#   --prompt-config {none,quant,qp1,qp2,qp3,qp4,qp5,qp6,qp7}
#                                   none + intervention 0 = vanilla
#                                   quant requires --rc/--ri/--ra
#                                   qp1..qp7 use the qualitative paragraphs
#                                   from the paper (no rubric needed).
#   --rc / --ri / --ra              quantitative rubric values (correct,
#                                   incorrect, abstain).
#
# Env-var defaults (CLI flag wins): MODEL, CONFIG, INSTANCES, N, SEED,
# WORKERS, EVAL_WORKERS, OUTPUT, DOCKERHUB_USERNAME, INTERVENTION,
# PROMPT_CONFIG, RC, RI, RA
#
# Self-served local checkpoints (vLLM):
#   --lora-adapter <dir>    LoRA adapter to serve on top of --base-model.
#                           Passing this auto-enables --serve.
#   --base-model <hf_id>    Base model for the adapter (default
#                           google/gemma-4-E2B-it). With --serve and NO
#                           --lora-adapter, this is served directly (full ckpt).
#   --serve                 Ensure a vLLM OpenAI server is up before inference,
#                           starting one if needed (reused across runs that
#                           target the same checkpoint). MODEL is overridden to
#                           `hosted_vllm/<serve-name>`.
#   --serve-name <name>     Served-model id (default derived uniquely from the
#                           adapter path, e.g. `<ckpt_dir>_epoch-3`).
#   --vllm-port <p>         Port (default 8000). --stop-vllm stops the server
#                           this script started, at the end of the run.
#   This lets you sweep checkpoint × prompt-framing in a plain bash for-loop
#   without managing the server by hand:
#     for ckpt in .../epoch-*; do
#       for pc in quant qp7; do
#         bash swebench_pro/run.sh --serve --lora-adapter "$ckpt" \
#           --intervention 5 --prompt-config "$pc" [--rc 1 --ri -25 --ra 0] ...
#       done
#     done
#   Env-var defaults: LORA_ADAPTER, BASE_MODEL, SERVE, SERVE_NAME, VLLM_PORT,
#   VLLM_MAX_MODEL_LEN, MAX_LORA_RANK, VLLM_GPU_MEM_UTIL, VLLM_EXTRA_ARGS,
#   VLLM_BOOT_TIMEOUT, STOP_VLLM.
#
#   --enable-thinking       Turn on chat-template thinking mode (forwarded as
#                           extra_body.chat_template_kwargs.enable_thinking=true).
#                           This matches the Omni-MATH-Rule vLLM eval, which ran
#                           Gemma with enable_thinking=True. NOTE: --reasoning-effort
#                           is a no-op for Gemma, so this is the knob that actually
#                           enables thinking for self-served local checkpoints.

set -euo pipefail

cd "$(dirname "$0")/.."

MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"
INSTANCES="${INSTANCES:-swebench_pro/data/swebench_pro_full.jsonl}"
WORKERS="${WORKERS:-1}"
N="${N:-0}"                                  # 0 means "all"
SEED="${SEED:-100}"
EVAL_WORKERS="${EVAL_WORKERS:-1}"
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-jefzda}"
OUTPUT="${OUTPUT:-}"                         # default derived from model + N below
CONFIG="${CONFIG:-swebench_pro/configs/swebench_pro_vanilla.yaml}"
INTERVENTION="${INTERVENTION:-0}"
PROMPT_CONFIG="${PROMPT_CONFIG:-none}"
RC="${RC:-}"
RI="${RI:-}"
RA="${RA:-}"
API_TIMEOUT="${API_TIMEOUT:-600}"
REASONING_EFFORT="${REASONING_EFFORT:-medium}"
ENABLE_THINKING="${ENABLE_THINKING:-0}"   # 1 -> pass --enable-thinking through

# ---- local vLLM self-serve -------------------------------------------------
LORA_ADAPTER="${LORA_ADAPTER:-}"
BASE_MODEL="${BASE_MODEL:-google/gemma-4-E2B-it}"
SERVE="${SERVE:-0}"
SERVE_NAME="${SERVE_NAME:-}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-32768}"
MAX_LORA_RANK="${MAX_LORA_RANK:-64}"
VLLM_GPU_MEM_UTIL="${VLLM_GPU_MEM_UTIL:-0.95}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
VLLM_BOOT_TIMEOUT="${VLLM_BOOT_TIMEOUT:-300}"   # max 2s-polls while booting
VLLM_GPU_FREE_TIMEOUT="${VLLM_GPU_FREE_TIMEOUT:-60}"  # max 1s-polls for VRAM release
STOP_VLLM="${STOP_VLLM:-0}"
# mini-swe-agent's LitellmModel sends an OpenAI `bash` tool with
# tool_choice=auto, so the vLLM server must enable tool parsing. The Gemma 4
# chat template emits tool calls in the `gemma4` parser's format.
VLLM_ENABLE_AUTO_TOOL="${VLLM_ENABLE_AUTO_TOOL:-1}"
VLLM_TOOL_CALL_PARSER="${VLLM_TOOL_CALL_PARSER:-gemma4}"

DO_INFER=1
DO_EVAL=1
GOLD_EVAL=0
RUNDIR_OVERRIDE=""

usage () {
    sed -n '1,55p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --model)              MODEL="$2"; shift 2 ;;
        --config)             CONFIG="$2"; shift 2 ;;
        --instances)          INSTANCES="$2"; shift 2 ;;
        --n|--num-samples)    N="$2"; shift 2 ;;
        --seed)               SEED="$2"; shift 2 ;;
        --workers)            WORKERS="$2"; shift 2 ;;
        --eval-workers)       EVAL_WORKERS="$2"; shift 2 ;;
        --output)             OUTPUT="$2"; shift 2 ;;
        --rundir)             RUNDIR_OVERRIDE="$2"; shift 2 ;;
        --dockerhub-username) DOCKERHUB_USERNAME="$2"; shift 2 ;;
        --intervention)       INTERVENTION="$2"; shift 2 ;;
        --prompt-config)      PROMPT_CONFIG="$2"; shift 2 ;;
        --rc|--rubric-correct)   RC="$2"; shift 2 ;;
        --ri|--rubric-incorrect) RI="$2"; shift 2 ;;
        --ra|--rubric-abstain)   RA="$2"; shift 2 ;;
        --api-timeout)           API_TIMEOUT="$2"; shift 2 ;;
        --reasoning-effort)      REASONING_EFFORT="$2"; shift 2 ;;
        --enable-thinking)    ENABLE_THINKING=1; shift ;;
        --no-thinking)        ENABLE_THINKING=0; shift ;;
        --lora-adapter)       LORA_ADAPTER="$2"; shift 2 ;;
        --base-model)         BASE_MODEL="$2"; shift 2 ;;
        --serve)              SERVE=1; shift ;;
        --no-serve)           SERVE=0; shift ;;
        --serve-name)         SERVE_NAME="$2"; shift 2 ;;
        --vllm-port)          VLLM_PORT="$2"; shift 2 ;;
        --vllm-max-model-len) VLLM_MAX_MODEL_LEN="$2"; shift 2 ;;
        --max-lora-rank)      MAX_LORA_RANK="$2"; shift 2 ;;
        --tool-call-parser)   VLLM_TOOL_CALL_PARSER="$2"; shift 2 ;;
        --no-auto-tool)       VLLM_ENABLE_AUTO_TOOL=0; shift ;;
        --stop-vllm)          STOP_VLLM=1; shift ;;
        --no-eval)            DO_EVAL=0; shift ;;
        --eval-only)          DO_INFER=0; shift ;;
        --gold-eval)          DO_INFER=0; GOLD_EVAL=1; shift ;;
        -h|--help)            usage ;;
        --)                   shift; break ;;
        -*) echo "Unknown flag: $1" >&2; echo "Run with --help." >&2; exit 2 ;;
        *)  echo "Unexpected positional: $1" >&2; exit 2 ;;
    esac
done

# ---- resolve vLLM self-serve config (sets MODEL + litellm env) -------------
# Passing --lora-adapter implies --serve. When serving, MODEL is forced to
# `hosted_vllm/<serve-name>` so mini-swe-agent's litellm hits the local server.
if [ -n "$LORA_ADAPTER" ]; then SERVE=1; fi
if [ "$SERVE" -eq 1 ]; then
    if [ -z "$SERVE_NAME" ]; then
        if [ -n "$LORA_ADAPTER" ]; then
            adir="$(cd "$LORA_ADAPTER" && pwd)"
            # Unique across checkpoints: <parent_dir_name>_<adapter_dir_name>
            # (a bare basename like `epoch-3` would collide across checkpoints).
            SERVE_NAME="$(basename "$(dirname "$adir")")_$(basename "$adir")"
        else
            SERVE_NAME="$(basename "$BASE_MODEL")"
        fi
        SERVE_NAME="${SERVE_NAME//[^a-zA-Z0-9_.-]/_}"
    fi
    MODEL="hosted_vllm/${SERVE_NAME}"
    export HOSTED_VLLM_API_BASE="http://localhost:${VLLM_PORT}/v1"
    export HOSTED_VLLM_API_KEY="${HOSTED_VLLM_API_KEY:-dummy}"
fi

VLLM_PIDFILE="/tmp/vllm_swebench_${VLLM_PORT}.pid"
VLLM_NAMEFILE="/tmp/vllm_swebench_${VLLM_PORT}.name"
VLLM_LOGFILE="/tmp/vllm_swebench_${VLLM_PORT}.log"

vllm_serves_target () {
    # 0 if the server on $VLLM_PORT currently lists $SERVE_NAME as a model id.
    curl -sf "http://localhost:${VLLM_PORT}/v1/models" 2>/dev/null \
        | grep -q "\"id\"[[:space:]]*:[[:space:]]*\"${SERVE_NAME}\""
}

vllm_port_busy () {
    curl -sf "http://localhost:${VLLM_PORT}/v1/models" >/dev/null 2>&1
}

_gpu_pid_present () {
    # 0 if $1 is still holding GPU memory (appears in nvidia-smi compute apps).
    local pid="$1"
    command -v nvidia-smi >/dev/null 2>&1 || return 1
    nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null \
        | tr -d ' ' | grep -qx "$pid"
}

stop_vllm () {
    if [ -f "$VLLM_PIDFILE" ]; then
        local pid; pid="$(cat "$VLLM_PIDFILE" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "[vllm] stopping server pid=$pid"
            kill "$pid" 2>/dev/null || true
            for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
            kill -9 "$pid" 2>/dev/null || true
        fi
        # Wait for the GPU to actually reclaim this PID's memory before the next
        # server allocates (process death can precede VRAM release, which would
        # otherwise risk a load-time CUDA OOM on the next checkpoint).
        if [ -n "$pid" ]; then
            local j
            for j in $(seq 1 "$VLLM_GPU_FREE_TIMEOUT"); do
                _gpu_pid_present "$pid" || break
                sleep 1
            done
            echo "[vllm] gpu memory released for pid=$pid"
        fi
        rm -f "$VLLM_PIDFILE" "$VLLM_NAMEFILE"
    fi
}

_adapter_lora_rank () {
    # Echo the LoRA rank `r` from <adapter>/adapter_config.json, or empty.
    local cfg="$1/adapter_config.json"
    [ -f "$cfg" ] || return 0
    python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('r',''))" "$cfg" 2>/dev/null
}

_round_up_lora_rank () {
    # vLLM's --max-lora-rank only accepts a fixed set; round up to the next one.
    local r="$1"
    for allowed in 8 16 32 64 128 256 320 512; do
        if [ "$r" -le "$allowed" ]; then echo "$allowed"; return 0; fi
    done
    echo "$r"
}

start_vllm () {
    local cmd=(vllm serve "$BASE_MODEL")
    if [ -n "$LORA_ADAPTER" ]; then
        # Size --max-lora-rank to the adapter (SFT=16, DPO=64, …). Serving with a
        # too-small max-lora-rank loads fine but 400s every request at inference
        # ("LoRA rank N is greater than max_lora_rank M"). Use max(detected, flag).
        local detected effective="$MAX_LORA_RANK"
        detected="$(_adapter_lora_rank "$LORA_ADAPTER")"
        if [ -n "$detected" ] && [ "$detected" -gt "$effective" ] 2>/dev/null; then
            effective="$detected"
        fi
        effective="$(_round_up_lora_rank "$effective")"
        if [ -n "$detected" ]; then
            echo "[vllm] adapter LoRA rank=$detected -> --max-lora-rank $effective"
        fi
        cmd+=(--enable-lora --lora-modules "${SERVE_NAME}=${LORA_ADAPTER}" --max-lora-rank "$effective")
    else
        cmd+=(--served-model-name "$SERVE_NAME")
    fi
    cmd+=(--port "$VLLM_PORT" --max-model-len "$VLLM_MAX_MODEL_LEN" --gpu-memory-utilization "$VLLM_GPU_MEM_UTIL")
    # mini-swe-agent sends a `bash` tool with tool_choice=auto; without these the
    # server 400s every request ("auto tool choice requires --enable-auto-tool-choice").
    if [ "$VLLM_ENABLE_AUTO_TOOL" -eq 1 ]; then
        cmd+=(--enable-auto-tool-choice --tool-call-parser "$VLLM_TOOL_CALL_PARSER")
    fi
    # shellcheck disable=SC2206
    if [ -n "$VLLM_EXTRA_ARGS" ]; then cmd+=($VLLM_EXTRA_ARGS); fi

    echo "[vllm] starting: ${cmd[*]}"
    echo "[vllm] log: $VLLM_LOGFILE"
    nohup "${cmd[@]}" > "$VLLM_LOGFILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$VLLM_PIDFILE"
    echo "$SERVE_NAME" > "$VLLM_NAMEFILE"

    local i
    for i in $(seq 1 "$VLLM_BOOT_TIMEOUT"); do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "[vllm] server process died during boot. Log tail:" >&2
            tail -n 40 "$VLLM_LOGFILE" >&2 || true
            exit 1
        fi
        if vllm_serves_target; then
            echo "[vllm] ready: $SERVE_NAME on http://localhost:${VLLM_PORT}/v1 (pid=$pid, ${i} polls)"
            return 0
        fi
        sleep 2
    done
    echo "[vllm] timed out after ~$((VLLM_BOOT_TIMEOUT * 2))s waiting for $SERVE_NAME. Log tail:" >&2
    tail -n 40 "$VLLM_LOGFILE" >&2 || true
    exit 1
}

ensure_vllm_server () {
    if vllm_serves_target; then
        echo "[vllm] reusing running server for $SERVE_NAME on port $VLLM_PORT"
        echo "$SERVE_NAME" > "$VLLM_NAMEFILE"
        return 0
    fi
    if vllm_port_busy; then
        echo "[vllm] port $VLLM_PORT is serving a different model; restarting for $SERVE_NAME"
    fi
    stop_vllm
    if command -v fuser >/dev/null 2>&1; then
        fuser -k "${VLLM_PORT}/tcp" 2>/dev/null || true
        sleep 2
    fi
    start_vllm
}

# Build a sensible default output dir if the user didn't pass --output.
# Format: results/<model_slug>[_int<I>_<config>][_n<N>][_seed<S>]
if [ -z "$OUTPUT" ]; then
    if [ "$DO_INFER" -eq 0 ] && [ -n "$RUNDIR_OVERRIDE" ]; then
        OUTPUT="$RUNDIR_OVERRIDE"
    else
        slug="${MODEL//\//_}"; slug="${slug//:/_}"
        suffix=""
        if [ "$INTERVENTION" != "0" ]; then
            cfg_slug="$PROMPT_CONFIG"
            if [ "$PROMPT_CONFIG" = "quant" ]; then
                cfg_slug="quant${RC}_${RI}_${RA}"
            fi
            suffix="_int${INTERVENTION}_${cfg_slug}"
        elif [ "$PROMPT_CONFIG" != "none" ]; then
            cfg_slug="$PROMPT_CONFIG"
            if [ "$PROMPT_CONFIG" = "quant" ]; then
                cfg_slug="quant${RC}_${RI}_${RA}"
            fi
            suffix="_consequence_${cfg_slug}"
        fi
        if [ "$N" -gt 0 ]; then
            OUTPUT="swebench_pro/results/${slug}${suffix}_n${N}"
        else
            OUTPUT="swebench_pro/results/${slug}${suffix}_all"
        fi
        if [ "$SEED" != "100" ]; then
            OUTPUT="${OUTPUT}_seed${SEED}"
        fi
    fi
elif [ "$DO_INFER" -eq 0 ] && [ -n "$RUNDIR_OVERRIDE" ]; then
    OUTPUT="$RUNDIR_OVERRIDE"
fi

echo "Run config:"
echo "  model         = $MODEL"
echo "  config        = $CONFIG"
echo "  instances     = $INSTANCES"
echo "  N (samples)   = ${N:-all}"
echo "  seed          = $SEED"
echo "  workers       = $WORKERS"
echo "  intervention  = $INTERVENTION"
echo "  prompt_config = $PROMPT_CONFIG"
if [ "$PROMPT_CONFIG" = "quant" ]; then
    echo "  rubric        = ($RC, $RI, $RA)  (correct, incorrect, abstain)"
fi
echo "  output        = $OUTPUT"
if [ "$SERVE" -eq 1 ]; then
    echo "  serve         = yes (vLLM port $VLLM_PORT)"
    echo "  serve_name    = $SERVE_NAME"
    echo "  base_model    = $BASE_MODEL"
    echo "  lora_adapter  = ${LORA_ADAPTER:-(none, serving base directly)}"
fi
echo "  api_timeout   = ${API_TIMEOUT}s"
echo "  reasoning     = $REASONING_EFFORT"
echo "  enable_thinking = $ENABLE_THINKING"
echo "  do_infer      = $DO_INFER"
echo "  do_eval       = $DO_EVAL"
echo "  gold_eval     = $GOLD_EVAL"
echo "  eval_workers  = $EVAL_WORKERS"
echo "  dockerhub_user= $DOCKERHUB_USERNAME"

mkdir -p "$OUTPUT"

# 1. Inference (resumable).
if [ "$DO_INFER" -eq 1 ]; then
    if [ "$SERVE" -eq 1 ]; then
        ensure_vllm_server
    fi
    EXTRA=()
    if [ "$N" -gt 0 ]; then
        EXTRA+=(--limit "$N")
    fi
    EXTRA+=(--intervention "$INTERVENTION" --prompt-config "$PROMPT_CONFIG")
    if [ "$ENABLE_THINKING" -eq 1 ]; then
        EXTRA+=(--enable-thinking)
    fi
    if [ "$PROMPT_CONFIG" = "quant" ]; then
        if [ -z "$RC" ] || [ -z "$RI" ] || [ -z "$RA" ]; then
            echo "Error: --prompt-config quant requires --rc / --ri / --ra." >&2
            exit 2
        fi
        EXTRA+=(--rubric-correct "$RC" --rubric-incorrect "$RI" --rubric-abstain "$RA")
    fi
    python swebench_pro/run_mini_on_pro.py \
        --model "$MODEL" \
        --config "$CONFIG" \
        --instances "$INSTANCES" \
        --output "$OUTPUT" \
        --workers "$WORKERS" \
        --seed "$SEED" \
        --api-timeout "$API_TIMEOUT" \
        --reasoning-effort "$REASONING_EFFORT" \
        "${EXTRA[@]}"
else
    echo "[run] skipping inference (--eval-only / --gold-eval)"
fi

# 2. Evaluation.
if [ "$DO_EVAL" -eq 1 ] || [ "$GOLD_EVAL" -eq 1 ]; then
    EVAL_FLAGS=(--workers "$EVAL_WORKERS" --dockerhub-username "$DOCKERHUB_USERNAME")
    if [ "$GOLD_EVAL" -eq 1 ]; then
        EVAL_FLAGS+=(--gold)
    fi
    bash swebench_pro/scripts/run_eval.sh "$OUTPUT" "${EVAL_FLAGS[@]}"
else
    echo "[run] skipping evaluation (--no-eval)"
fi

# Optionally stop the vLLM server this script started (off by default so a
# checkpoint × framing sweep can reuse it across runs).
if [ "$SERVE" -eq 1 ] && [ "$STOP_VLLM" -eq 1 ]; then
    stop_vllm
fi

echo
echo "Done. Outputs in: $OUTPUT"
echo "  preds.json                                       -- instance_id -> submitted patch"
echo "  exit_statuses.yaml                               -- per-instance agent exit_status"
echo "  minisweagent.log                                 -- driver log"
echo "  <bare_id>/<bare_id>.traj.json                    -- full agent trajectory"
if [ "$DO_EVAL" -eq 1 ] || [ "$GOLD_EVAL" -eq 1 ]; then
    echo "  eval/eval_results.json                           -- {instance_id: bool} resolved"
    echo "  eval/instance_<bare_id>/mini_stdout.log          -- test-run stdout"
    echo "  eval/instance_<bare_id>/mini_stderr.log          -- test-run stderr"
    echo "  eval/instance_<bare_id>/mini_output.json         -- per-test PASSED/FAILED"
    echo "  eval/instance_<bare_id>/mini_patch.diff          -- patch handed to git apply"
    echo "  eval/instance_<bare_id>/mini_entryscript.sh      -- script run inside test container"
    echo
    echo "Note: <bare_id> is the instance id WITHOUT the leading 'instance_' prefix"
    echo "      (the eval dir uses the prefixed id; the trajectory dir uses the bare id)."
    if [ -f "$OUTPUT/eval/eval_results.json" ]; then
        n_total="$(python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(len(d))' "$OUTPUT/eval/eval_results.json" 2>/dev/null || echo "?")"
        n_resolved="$(python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(sum(d.values()))' "$OUTPUT/eval/eval_results.json" 2>/dev/null || echo "?")"
        echo "      This run: $n_resolved / $n_total resolved."
    fi
fi
