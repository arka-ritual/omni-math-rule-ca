#!/bin/bash
# Re-evaluate every existing intervention rundir with the fixed
# preds_to_eval_input pipeline (the .strip() bug that was silently
# corrupting every patch's trailing newline is fixed in
# swebench_pro/scripts/preds_to_eval_input.py).
#
# For each rundir we:
#   1. Wipe the stale eval/ directory (so the grader starts fresh and
#      uses the fixed preds_to_eval_input.py to rebuild patches_for_eval.json).
#   2. Re-run scripts/run_eval.sh.
#   3. Print the new pass count.
#
# Sequential across rundirs (high per-rundir EVAL_WORKERS instead) to
# avoid Docker juggling many big test images at once.

set -u

EVAL_WORKERS="${EVAL_WORKERS:-16}"

RUNDIRS=(
    "swebench_pro/results/gemini_gemini-3.1-flash-lite-preview_int0_n20"
    "swebench_pro/results/gemini_gemini-3.1-flash-lite-preview_int1_qp6_all"
    "swebench_pro/results/gemini_gemini-3.1-flash-lite-preview_int1_quant_100_all"
    "swebench_pro/results/gemini_gemini-3.1-flash-lite-preview_int1_quant_25_all"
    "swebench_pro/results/openai_gpt-5.4-nano_int1_quant_100_all"
    "swebench_pro/results/openai_gpt-5.4-nano_int1_quant_25_all"
    "swebench_pro/results/openrouter_deepseek_deepseek-v4-pro_int1_quant_100_all"
    "swebench_pro/results/openrouter_deepseek_deepseek-v4-pro_int1_quant_25_all"
)

cd "$(dirname "$0")/../.."

for rd in "${RUNDIRS[@]}"; do
    echo
    echo "============================================================"
    echo "[$(date +%H:%M:%S)] re-eval: $rd"
    echo "============================================================"
    if [ ! -f "$rd/preds.json" ]; then
        echo "  SKIP: no preds.json"
        continue
    fi
    npreds=$(python3 -c "import json; print(len(json.load(open('$rd/preds.json'))))")
    echo "  preds.json contains $npreds entries"
    if [ -d "$rd/eval" ]; then
        echo "  Wiping stale $rd/eval/"
        rm -rf "$rd/eval"
    fi
    bash swebench_pro/scripts/run_eval.sh "$rd" --workers "$EVAL_WORKERS"
    if [ -f "$rd/eval/eval_results.json" ]; then
        python3 -c "
import json
d = json.load(open('$rd/eval/eval_results.json'))
n = len(d); k = sum(d.values())
pct = (100.0 * k / n) if n else 0.0
print(f'  RESULT: {k}/{n} resolved ({pct:.1f}%)')
"
    else
        echo "  WARN: no eval_results.json produced"
    fi
done

echo
echo "============================================================"
echo "[$(date +%H:%M:%S)] re-eval sweep complete"
echo "============================================================"
echo
echo "Summary:"
for rd in "${RUNDIRS[@]}"; do
    if [ -f "$rd/eval/eval_results.json" ]; then
        python3 -c "
import json, os
d = json.load(open('$rd/eval/eval_results.json'))
n = len(d); k = sum(d.values())
pct = (100.0 * k / n) if n else 0.0
print(f'  {os.path.basename(\"$rd\"):80s}  {k:3d}/{n:3d}  ({pct:5.1f}%)')
"
    fi
done
