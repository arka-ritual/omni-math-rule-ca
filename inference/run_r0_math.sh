#!/bin/bash
# The r_0 baseline on Omni-MATH-Rule, for the NeurIPS 2026 rebuttal.
#
# r_0 := (s_c, s_a, s_i) = (+1, 0, 0) — abstention is offered, but being wrong
# costs nothing. Reviewers 27Kr and LswH both asked for this cell:
#
#   "I would like to see r_0 as a baseline for the qualitative evaluation in
#    Figure 1 to distinguish between two possible interpretations of
#    'consequence-insensitive': (a) given that there is a consequence, the
#    model does not care how severe it is [what the current r_1..r_100 sweep
#    tests], or (b) the model is insensitive to consequences including whether
#    there is one at all [untested on the quantitative side]."
#
# The paper's quantitative sweep starts at r_1, so only QP1 serves as a
# no-consequence anchor and only on the qualitative side. This script adds the
# missing quantitative one.
#
# Sampling settings MUST match the existing sweep in
# `evaluation/output/qualitative_quantitative_sweep/summary.md` — T=1.0,
# max_tokens=64000, seed=100, N=100 — NOT the defaults in run_baselines.sh
# (T=0.0, 32768), or r_0 is not comparable to the r_1..r_100 cells it exists to
# be compared against.
#
# All five models route through OpenRouter (the only key available).
#
# Usage:
#   bash inference/run_r0_math.sh                              # all 5 models
#   bash inference/run_r0_math.sh --model gpt-5.4-nano         # one model
#   bash inference/run_r0_math.sh --num-samples 2 --dry-cell   # cheap smoke
#   bash inference/run_r0_math.sh --no-eval                    # inference only
#
# Knobs (CLI flag wins over env var):
#   --num-samples / NUM_SAMPLES   default 100
#   --seed        / SEED          default 100
#   --temperature / TEMPERATURE   default 1.0
#   --max-tokens  / MAX_TOKENS    default 64000
#   --concurrency / CONCURRENCY   default 20
#   --results-dir / RESULTS_DIR   default inference/results/qualitative_quantitative_sweep
#   --eval-dir    / EVAL_DIR      default evaluation/output/qualitative_quantitative_sweep
#   --rubric      / RC,RI,RA      default 1,0,0  (i.e. r_0)
#   --no-eval                     skip the per-cell cautious evaluation
#   --dry-cell                    write to a scratch cell name so a smoke run
#                                 can't pollute the real sweep outputs
#
# Requires OPENROUTER_API_KEY in the environment or in `.env` at the repo root.
#
# Inference is resume-safe (matched on `idx`), so re-running after an
# interruption picks up only the missing problems.

set -euo pipefail

cd "$(dirname "$0")/.."

# ---- knobs ------------------------------------------------------------
NUM_SAMPLES="${NUM_SAMPLES:-100}"
SEED="${SEED:-100}"
TEMPERATURE="${TEMPERATURE:-1.0}"
MAX_TOKENS="${MAX_TOKENS:-64000}"
CONCURRENCY="${CONCURRENCY:-20}"
RESULTS_DIR="${RESULTS_DIR:-inference/results/qualitative_quantitative_sweep}"
EVAL_DIR="${EVAL_DIR:-evaluation/output/qualitative_quantitative_sweep}"
DATA_FILE="${DATA_FILE:-omni_math_rule.jsonl}"
RC="${RC:-1}"
RI="${RI:-0}"
RA="${RA:-0}"

DO_EVAL=1
DRY_CELL=0
ONLY_MODEL=""

usage () { sed -n '1,48p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --model)        ONLY_MODEL="$2"; shift 2 ;;
        --num-samples)  NUM_SAMPLES="$2"; shift 2 ;;
        --seed)         SEED="$2"; shift 2 ;;
        --temperature)  TEMPERATURE="$2"; shift 2 ;;
        --max-tokens)   MAX_TOKENS="$2"; shift 2 ;;
        --concurrency)  CONCURRENCY="$2"; shift 2 ;;
        --results-dir)  RESULTS_DIR="$2"; shift 2 ;;
        --eval-dir)     EVAL_DIR="$2"; shift 2 ;;
        --data-file)    DATA_FILE="$2"; shift 2 ;;
        --rubric)       IFS=',' read -r RC RI RA <<< "$2"; shift 2 ;;
        --no-eval)      DO_EVAL=0; shift ;;
        --dry-cell)     DRY_CELL=1; shift ;;
        -h|--help)      usage ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$RESULTS_DIR" "$EVAL_DIR"

# ---- model set --------------------------------------------------------
# <slug>|<provider>|<provider-model-id>[|<openrouter-subprovider>]
#
# The slug feeds the output filename and must match the slugs already used in
# this sweep directory (see gpt-5.4-nano_quant_1_0_-1.jsonl) so the summarizer
# can pair r_0 with the other rubrics for the same model.
#
# Haiku and GPT-Nano were called through their native providers in
# run_baselines.sh; here they go through OpenRouter, verified against
# openrouter.ai/api/v1/models.
#
# DeepSeek is deliberately NOT pinned, unlike run_baselines.sh, which pins it
# to the first-party "DeepSeek" upstream with allow_fallbacks=false. That
# upstream is rejected for this account — OpenRouter returns "No endpoints
# available matching your guardrail restrictions and data policy" — so the pin
# would simply 404 every request. Routing is therefore left free.
#
# Consequence to footnote: with no pin, OpenRouter picks the upstream (and its
# quantization, fp4 vs fp8) per request, so the DeepSeek r_0 cell is not
# strictly reproducible and may not match the upstream the paper's other
# DeepSeek cells ran on. `inference_api.py` records the serving upstream in
# each record's `upstream_provider` field; check the mix with:
#   python -c "import json,collections;print(collections.Counter(json.loads(l).get('upstream_provider') for l in open('inference/results/qualitative_quantitative_sweep/deepseek-v4-pro_quant_1_0_0.jsonl',encoding='utf-8')))"
MODELS=(
    "claude-haiku-4-5|openrouter|anthropic/claude-haiku-4.5"
    "gpt-5.4-nano|openrouter|openai/gpt-5.4-nano"
    "gemini-3.1-flash-lite-preview|openrouter|google/gemini-3.1-flash-lite-preview"
    "deepseek-v4-pro|openrouter|deepseek/deepseek-v4-pro"
    "qwen3.5-397b|openrouter|qwen/qwen3.5-397b-a17b"
)

# ---- validate filter --------------------------------------------------
if [ -n "$ONLY_MODEL" ]; then
    valid=0
    for entry in "${MODELS[@]}"; do
        IFS='|' read -r slug _ _ <<< "$entry"
        [ "$slug" = "$ONLY_MODEL" ] && valid=1 && break
    done
    if [ "$valid" -ne 1 ]; then
        echo "ERROR: --model '$ONLY_MODEL' did not match any known slug." >&2
        echo "  valid: $(for e in "${MODELS[@]}"; do echo -n "${e%%|*} "; done)" >&2
        exit 2
    fi
fi

# Cell name mirrors the existing convention in this directory:
#   quant_<r_correct>_<r_abstain>_<r_incorrect>
# (note: abstain before incorrect, matching gpt-5.4-nano_quant_1_0_-1.jsonl,
#  and unlike the base-model runs, which use _r<rc>_<ri>_<ra>.)
CELL="quant_${RC}_${RA}_${RI}"
[ "$DRY_CELL" -eq 1 ] && CELL="SMOKE_${CELL}"

echo "r_0 baseline sweep:"
echo "  rubric        = (correct=$RC, abstain=$RA, incorrect=$RI)  -> cell '$CELL'"
echo "  num_samples   = $NUM_SAMPLES   seed=$SEED"
echo "  temperature   = $TEMPERATURE   max_tokens=$MAX_TOKENS"
echo "  concurrency   = $CONCURRENCY"
echo "  data_file     = $DATA_FILE"
echo "  filter model  = ${ONLY_MODEL:-(all ${#MODELS[@]})}"
echo "  do_eval       = $DO_EVAL"
echo "  results_dir   = $RESULTS_DIR"
echo "  eval_dir      = $EVAL_DIR"

run_one () {
    local slug="$1" provider="$2" model="$3" or_subprovider="${4:-}"
    local out="$RESULTS_DIR/${slug}_${CELL}.jsonl"
    local eval_out="$EVAL_DIR/${slug}_${CELL}"
    local extra_args=()
    if [ -n "$or_subprovider" ]; then
        extra_args+=(--openrouter-provider "$or_subprovider")
    fi
    echo
    echo "=== ${slug} | ${CELL}${or_subprovider:+ | OR-provider=$or_subprovider} ==="
    python inference/inference_api.py \
        --provider "$provider" --model "$model" \
        --prompt quantitative_grading \
        --rubric_correct "$RC" --rubric_incorrect "$RI" --rubric_abstain "$RA" \
        --data_file "$DATA_FILE" \
        --save_path "$out" \
        --num_samples "$NUM_SAMPLES" --seed "$SEED" \
        --temperature "$TEMPERATURE" --max_tokens "$MAX_TOKENS" \
        --concurrency "$CONCURRENCY" \
        "${extra_args[@]}"

    if [ "$DO_EVAL" -eq 1 ]; then
        python evaluation/math_eval_cautious.py \
            --data_file "$out" \
            --output_dir "$eval_out"
    fi
}

for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug provider model or_subprovider <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    run_one "$slug" "$provider" "$model" "$or_subprovider"
done

echo
echo "Done. Cells written:"
for entry in "${MODELS[@]}"; do
    IFS='|' read -r slug _ _ <<< "$entry"
    [ -n "$ONLY_MODEL" ] && [ "$ONLY_MODEL" != "$slug" ] && continue
    echo "  inference: $RESULTS_DIR/${slug}_${CELL}.jsonl"
    [ "$DO_EVAL" -eq 1 ] && echo "  eval:      $EVAL_DIR/${slug}_${CELL}/cautious_metrics.json"
done
echo
echo "Summarize with:  python scripts/summarize_quant_qual_sweep.py"
