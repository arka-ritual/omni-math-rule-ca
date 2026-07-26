#!/bin/bash
# Diagonal smoke test: each of the 5 models of interest gets ONE distinct
# (intervention, framing) cell, designed to exercise:
#   - all 3 interventions (1, 2, 3)
#   - all 4 framings (quant_25, quant_100, qp6, qp7)
#   - all 5 API providers + their reasoning knobs
#   - the new intervention-2 "confidence-then-reveal" flow
#
# All cells run IN PARALLEL (each `bash run.sh` backgrounded; we wait for all
# to finish at the end). 5 instances per cell, 5 inference workers per cell,
# 5 eval workers per cell.
#
# By default ALL 5 cells run; pass `--skip <cell_slug_substring>` (repeatable)
# to skip a previously-completed cell. Output dirs are unique per cell so
# parallel runs don't collide.

set -u

cd "$(dirname "$0")/../.."

# When --root <existing-dir> is passed we reuse that smoketest directory
# (so a previously-completed cell like Haiku stays where it is and gets
# included in the final summary). Otherwise a fresh timestamped dir is made.
TS="$(date +%Y%m%d_%H%M%S)"
ROOT_OVERRIDE=""
SKIP_PATTERNS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --root) ROOT_OVERRIDE="$2"; shift 2 ;;
        --skip) SKIP_PATTERNS+=("$2"); shift 2 ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

if [ -n "$ROOT_OVERRIDE" ]; then
    ROOT="$ROOT_OVERRIDE"
else
    ROOT="swebench_pro/results/smoketest_${TS}"
fi
mkdir -p "$ROOT"

N=5
WORKERS=5
EVAL_WORKERS=5
SEED=100
REASONING_EFFORT=medium

# cell_spec format: "<model>|<intervention>|<prompt_config>|<rc>|<ri>|<ra>"
# rc/ri/ra are ignored for qp6/qp7.
CELLS=(
    "anthropic/claude-haiku-4-5|1|quant|1|-10|0"
    "gemini/gemini-3.1-flash-lite-preview|2|qp7|||"
    "openai/gpt-5.4-nano|3|quant|1|-5|0"
    "openrouter/qwen/qwen3.5-397b-a17b|1|qp6|||"
    "openrouter/deepseek/deepseek-v4-pro|2|quant|1|-10|0"
)

slug () {
    local s="$1"; s="${s//\//_}"; s="${s//:/_}"; echo "$s"
}

cell_slug () {
    local model="$1" intv="$2" pcfg="$3" rc="$4" ri="$5" ra="$6"
    local s="$(slug "$model")_int${intv}_${pcfg}"
    if [ "$pcfg" = "quant" ]; then
        s="${s}${rc}_${ri}_${ra}"
    fi
    echo "$s"
}

skip_cell () {
    local cs="$1"
    for p in "${SKIP_PATTERNS[@]:-}"; do
        if [[ "$cs" == *"$p"* ]]; then return 0; fi
    done
    return 1
}

LOGFILE="${ROOT}/sweep.log"
exec > >(tee -a "$LOGFILE") 2>&1

echo "============================================================"
echo "[$(date +%H:%M:%S)] DIAGONAL SMOKE SWEEP (PARALLEL)"
echo "============================================================"
echo "  output root      = $ROOT"
echo "  N per cell       = $N"
echo "  workers per cell = $WORKERS"
echo "  eval workers     = $EVAL_WORKERS"
echo "  seed             = $SEED"
echo "  reasoning effort = $REASONING_EFFORT"
echo "  skip patterns    = ${SKIP_PATTERNS[*]:-(none)}"
echo "  cells:"
for c in "${CELLS[@]}"; do echo "    - $c"; done

# Launch all cells in parallel.
PIDS=()
for cell in "${CELLS[@]}"; do
    IFS="|" read -r model intv pcfg rc ri ra <<<"$cell"
    cs="$(cell_slug "$model" "$intv" "$pcfg" "$rc" "$ri" "$ra")"
    if skip_cell "$cs"; then
        echo "[SKIP] $cs (matched --skip pattern)"
        continue
    fi
    out="${ROOT}/${cs}_n${N}"

    args=(
        --model "$model"
        --output "$out"
        --n "$N"
        --seed "$SEED"
        --workers "$WORKERS"
        --eval-workers "$EVAL_WORKERS"
        --reasoning-effort "$REASONING_EFFORT"
        --intervention "$intv"
        --prompt-config "$pcfg"
    )
    if [ "$pcfg" = "quant" ]; then
        args+=(--rc "$rc" --ri "$ri" --ra "$ra")
    fi

    # Each cell writes its own log so parallel output streams don't interleave.
    cell_log="${out}_cell.log"
    mkdir -p "$out"
    echo "[$(date +%H:%M:%S)] launching cell: $cs  (log: $cell_log)"
    bash swebench_pro/run.sh "${args[@]}" > "$cell_log" 2>&1 &
    PIDS+=($!)
done

echo
echo "[$(date +%H:%M:%S)] All cells launched (${#PIDS[@]} bg jobs). Waiting..."
echo "  Tail any cell's log to follow per-cell progress, e.g.:"
echo "    tail -f $ROOT/*_cell.log"

# Wait for all to finish. We don't `set -e`; some cells may fail and we
# still want the summary at the end.
for pid in "${PIDS[@]}"; do
    wait "$pid" || echo "  cell pid $pid exited non-zero"
done

echo
echo "============================================================"
echo "[$(date +%H:%M:%S)] SWEEP COMPLETE"
echo "============================================================"
echo
echo "Per-cell results:"
for cell in "${CELLS[@]}"; do
    IFS="|" read -r model intv pcfg rc ri ra <<<"$cell"
    cs="$(cell_slug "$model" "$intv" "$pcfg" "$rc" "$ri" "$ra")"
    out="${ROOT}/${cs}_n${N}"
    if [ -f "$out/eval/eval_results.json" ]; then
        python3 -c "
import json
d = json.load(open('$out/eval/eval_results.json'))
n=len(d); k=sum(d.values())
pct = (100.0*k/n) if n else 0.0
print(f'  {\"$cs\":80s} {k}/{n} ({pct:.1f}%)')
"
    else
        echo "  $cs  (no eval_results.json)"
    fi
done

echo
echo "Full log: $LOGFILE"
