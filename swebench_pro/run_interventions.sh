#!/bin/bash
# Sweep runner for SWE-bench Pro consequence-asymmetry interventions.
#
# Mirrors `inference/run_interventions.sh` (the math-side orchestrator) but
# for the agentic SWE-bench Pro setup. Iterates over the cartesian product
# of {models} × {intervention 1, 2, 3} × {prompt configs}, calling the
# vanilla `swebench_pro/run.sh` per cell. Intervention 4 is computed
# post-hoc from the intervention-1 results via apply_intervention4.py
# (no separate model run).
#
# Models (litellm slugs — same set as inference/run_interventions.sh):
#   - anthropic/claude-haiku-4-5
#   - gemini/gemini-3.1-flash-lite
#   - openai/gpt-5.4-nano
#   - openrouter/qwen/qwen3.5-397b-instruct
#   - openrouter/deepseek/deepseek-v4-pro
#
# Each cell writes to its own rundir under
# `swebench_pro/results/<slug>/`, so resumes are independent.
#
# Usage:
#   bash swebench_pro/run_interventions.sh                  # all models, all cells
#   bash swebench_pro/run_interventions.sh --model openai/gpt-5.4-nano
#   bash swebench_pro/run_interventions.sh --model openai/gpt-5.4-nano \
#       --intervention 1 --config quant_25
#
#   N=10 WORKERS=4 EVAL_WORKERS=8 \
#       bash swebench_pro/run_interventions.sh --model anthropic/claude-haiku-4-5
#
# CLI filters (each one accepted multiple times, repeated values combined):
#   --model <slug>            # restrict to this model (default: all in MODELS)
#   --intervention {1,2,3,4}  # restrict to this intervention id
#   --config <quant_25|quant_100|qp6|qp7>
#                             # restrict to this prompt config
#
# Env-var defaults (CLI wins):
#   N, NUM_SAMPLES   -> per-cell sample count (0 = all 731 instances)
#   SEED             -> shuffle seed (default 100)
#   WORKERS          -> parallel agents per cell
#   EVAL_WORKERS     -> parallel docker eval workers
#   DO_EVAL=0        -> skip the per-cell official-grader step
#   GOLD_EVAL=1      -> after each model loop, also grade gold patches
#                       (sanity check, intervention-agnostic)

set -euo pipefail

cd "$(dirname "$0")/.."

# ---- defaults ----------------------------------------------------------
N="${N:-${NUM_SAMPLES:-0}}"
SEED="${SEED:-100}"
WORKERS="${WORKERS:-1}"
EVAL_WORKERS="${EVAL_WORKERS:-1}"
DO_EVAL="${DO_EVAL:-1}"
GOLD_EVAL="${GOLD_EVAL:-0}"
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-jefzda}"
API_TIMEOUT="${API_TIMEOUT:-600}"
REASONING_EFFORT="${REASONING_EFFORT:-medium}"
INSTANCES="${INSTANCES:-swebench_pro/data/swebench_pro_full.jsonl}"
CONFIG="${CONFIG:-swebench_pro/configs/swebench_pro_vanilla.yaml}"
RESULTS_ROOT="${RESULTS_ROOT:-swebench_pro/results}"

# ---- sweep matrix ------------------------------------------------------
# Models (litellm slugs). Mirrors the math-side set in
# inference/run_interventions.sh:
#   claude-haiku-4-5, gemini-3.1-flash-lite, gpt-5.4-nano,
#   qwen3.5-397b, deepseek-v4-pro.
ALL_MODELS=(
    "anthropic/claude-haiku-4-5"
    "gemini/gemini-3.1-flash-lite-preview"
    "openai/gpt-5.4-nano"
    "openrouter/qwen/qwen3.5-397b-a17b"
    "openrouter/deepseek/deepseek-v4-pro"
)

# Prompt configs. Format:  "<key>:<prompt_config>:<rc>:<ri>:<ra>"
# (rc/ri/ra ignored for qp6/qp7).
ALL_CONFIGS=(
    "quant_25:quant:1:-5:0"
    "quant_100:quant:1:-10:0"
    "qp6:qp6::"
    "qp7:qp7::"
)

# Interventions. 4 is post-hoc — run by the apply_intervention4.py block
# after intervention 1 finishes.
INFERENCE_INTERVENTIONS=(1 2 3)

# ---- CLI filter parsing ------------------------------------------------
FILTER_MODELS=()
FILTER_INTERVENTIONS=()
FILTER_CONFIGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --model)        FILTER_MODELS+=("$2"); shift 2 ;;
        --intervention) FILTER_INTERVENTIONS+=("$2"); shift 2 ;;
        --config)       FILTER_CONFIGS+=("$2"); shift 2 ;;
        --n|--num-samples) N="$2"; shift 2 ;;
        --seed)         SEED="$2"; shift 2 ;;
        --workers)      WORKERS="$2"; shift 2 ;;
        --eval-workers) EVAL_WORKERS="$2"; shift 2 ;;
        --api-timeout)  API_TIMEOUT="$2"; shift 2 ;;
        --reasoning-effort) REASONING_EFFORT="$2"; shift 2 ;;
        --no-eval)      DO_EVAL=0; shift ;;
        --gold-eval)    GOLD_EVAL=1; shift ;;
        -h|--help)
            sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

contains () {
    local needle="$1"; shift
    for v in "$@"; do [ "$v" = "$needle" ] && return 0; done
    return 1
}

is_active () {
    # is_active <list-name> <value>  — true if the list is empty OR contains value
    local listname="$1" val="$2"
    eval "local n=\${#${listname}[@]}"
    if [ "$n" -eq 0 ]; then return 0; fi
    eval "contains \"\$val\" \"\${${listname}[@]}\""
}

# ---- enumerate sweep ---------------------------------------------------
declare -a SWEEP=()
for model in "${ALL_MODELS[@]}"; do
    is_active FILTER_MODELS "$model" || continue
    for intv in "${INFERENCE_INTERVENTIONS[@]}"; do
        is_active FILTER_INTERVENTIONS "$intv" || continue
        for cfg_spec in "${ALL_CONFIGS[@]}"; do
            IFS=":" read -r cfg_key cfg_kind cfg_rc cfg_ri cfg_ra <<<"$cfg_spec"
            is_active FILTER_CONFIGS "$cfg_key" || continue
            SWEEP+=("${model}|${intv}|${cfg_key}|${cfg_kind}|${cfg_rc}|${cfg_ri}|${cfg_ra}")
        done
    done
done

if [ "${#SWEEP[@]}" -eq 0 ]; then
    echo "Empty sweep. Filters too restrictive?" >&2
    echo "  --model:        ${FILTER_MODELS[*]:-(no filter)}" >&2
    echo "  --intervention: ${FILTER_INTERVENTIONS[*]:-(no filter)}" >&2
    echo "  --config:       ${FILTER_CONFIGS[*]:-(no filter)}" >&2
    echo "  Available models:        ${ALL_MODELS[*]}" >&2
    echo "  Available interventions: ${INFERENCE_INTERVENTIONS[*]} (4 = post-hoc)" >&2
    echo "  Available configs:       quant_25 quant_100 qp6 qp7" >&2
    exit 2
fi

want_int4=0
if [ "${#FILTER_INTERVENTIONS[@]}" -eq 0 ] || contains 4 "${FILTER_INTERVENTIONS[@]}"; then
    want_int4=1
fi

echo "Sweep:"
echo "  cells          = ${#SWEEP[@]}  (intervention 1/2/3 inference)"
echo "  intervention 4 = $([ "$want_int4" -eq 1 ] && echo "yes (post-hoc rescore of int 1)" || echo "no")"
echo "  N (samples)    = ${N:-all}"
echo "  seed           = $SEED"
echo "  workers        = $WORKERS"
echo "  eval_workers   = $EVAL_WORKERS"
echo "  do_eval        = $DO_EVAL"
echo "  gold_eval      = $GOLD_EVAL"
echo "  api_timeout    = ${API_TIMEOUT}s"
echo "  reasoning      = $REASONING_EFFORT"

slug () {
    local s="$1"; s="${s//\//_}"; s="${s//:/_}"; echo "$s"
}

# ---- run each cell -----------------------------------------------------
for entry in "${SWEEP[@]}"; do
    IFS="|" read -r model intv cfg_key cfg_kind cfg_rc cfg_ri cfg_ra <<<"$entry"
    out_slug="$(slug "$model")_int${intv}_${cfg_key}"
    if [ "$N" -gt 0 ]; then out_slug="${out_slug}_n${N}"; else out_slug="${out_slug}_all"; fi
    if [ "$SEED" != "100" ]; then out_slug="${out_slug}_seed${SEED}"; fi
    out_dir="${RESULTS_ROOT}/${out_slug}"

    echo
    echo "============================================================"
    echo "[$(date +%H:%M:%S)] cell: model=$model intv=$intv cfg=$cfg_key  -> $out_dir"
    echo "============================================================"

    args=(
        --model "$model"
        --output "$out_dir"
        --instances "$INSTANCES"
        --config "$CONFIG"
        --n "$N"
        --seed "$SEED"
        --workers "$WORKERS"
        --eval-workers "$EVAL_WORKERS"
        --api-timeout "$API_TIMEOUT"
        --reasoning-effort "$REASONING_EFFORT"
        --intervention "$intv"
        --prompt-config "$cfg_kind"
        --dockerhub-username "$DOCKERHUB_USERNAME"
    )
    if [ "$cfg_kind" = "quant" ]; then
        args+=(--rc "$cfg_rc" --ri "$cfg_ri" --ra "$cfg_ra")
    fi
    if [ "$DO_EVAL" -eq 0 ]; then
        args+=(--no-eval)
    fi

    bash swebench_pro/run.sh "${args[@]}"
done

# ---- intervention 4 (post-hoc) -----------------------------------------
if [ "$want_int4" -eq 1 ]; then
    echo
    echo "============================================================"
    echo "[$(date +%H:%M:%S)] intervention 4 (post-hoc rescore of intervention 1)"
    echo "============================================================"
    for entry in "${SWEEP[@]}"; do
        IFS="|" read -r model intv cfg_key cfg_kind cfg_rc cfg_ri cfg_ra <<<"$entry"
        if [ "$intv" != "1" ]; then continue; fi
        src_slug="$(slug "$model")_int1_${cfg_key}"
        dst_slug="$(slug "$model")_int4_${cfg_key}"
        if [ "$N" -gt 0 ]; then
            src_slug="${src_slug}_n${N}"; dst_slug="${dst_slug}_n${N}"
        else
            src_slug="${src_slug}_all"; dst_slug="${dst_slug}_all"
        fi
        if [ "$SEED" != "100" ]; then
            src_slug="${src_slug}_seed${SEED}"; dst_slug="${dst_slug}_seed${SEED}"
        fi
        src_dir="${RESULTS_ROOT}/${src_slug}"
        dst_dir="${RESULTS_ROOT}/${dst_slug}"
        if [ ! -f "${src_dir}/preds.json" ]; then
            echo "[int4] skipping $dst_slug — missing ${src_dir}/preds.json"
            continue
        fi
        mkdir -p "$dst_dir"
        py_args=(--prompt-config "$cfg_kind")
        if [ "$cfg_kind" = "quant" ]; then
            py_args+=(--rc "$cfg_rc" --ri "$cfg_ri" --ra "$cfg_ra")
        fi
        echo "[int4] $src_dir -> $dst_dir"
        python swebench_pro/scripts/apply_intervention4.py "$src_dir" "$dst_dir" "${py_args[@]}"
        if [ "$DO_EVAL" -eq 1 ]; then
            bash swebench_pro/scripts/run_eval.sh "$dst_dir" \
                --workers "$EVAL_WORKERS" \
                --dockerhub-username "$DOCKERHUB_USERNAME"
        fi
    done
fi

if [ "$GOLD_EVAL" -eq 1 ]; then
    echo
    echo "============================================================"
    echo "[$(date +%H:%M:%S)] gold eval (sanity check)"
    echo "============================================================"
    bash swebench_pro/run.sh --gold-eval --eval-workers "$EVAL_WORKERS"
fi

echo
echo "Sweep complete. Results: ${RESULTS_ROOT}/"
