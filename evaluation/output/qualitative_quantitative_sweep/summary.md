# Qualitative + quantitative prompt sweep (math)

Source: `evaluation/output/qualitative_quantitative_sweep/*/cautious_metrics.json`.
Single model: `gpt-5.4-nano` (OpenAI, reasoning effort = `medium`).
Sampling: `T=1.0`, `max_tokens=64000`, `seed=100`, N=100 problems per cell.

Each cell was scored with the cautious evaluator (`math_eval_cautious.py`).
`acc_attempted` = `num_correct / num_attempted` (%); `abst` = `num_abstained`,
`indet` = `num_indeterminate`, `mixed` = `num_incorrect_mixed`, `n` = `num_total`.
Δ is `acc_attempted` − baseline `acc` in percentage points; the baseline anchor
is the `gpt-5.4-nano` no-consequence run (`acc = 42.0%`, 0 empties, n=100) at
`evaluation/output/baselines/gpt-5.4-nano/omni-math/math_eval_cot_metrics.json`.

Legend: c/i/a/m/d = correct/incorrect/abstained/mixed/indeterminate.

## Qualitative prompts (QP1–QP7)

Abstention rate = `num_abstained / num_total`.

| Prompt | acc_attempted | Abst rate | Δ vs baseline | Counts (c/i/a/m/d, n) |
|---|---:|---:|---:|---|
| QP1 (`max-correct, no-wrong`)        | **51.9%** | 23.0% |  +9.9 | c40 / i37 / a23 / m0 / d0, n=100 |
| QP2 (`catastrophic-consequences`)    | 39.8%     |  7.0% |  −2.2 | c37 / i55 / a7  / m1 / d0, n=100 |
| QP3 (`career-fired`)                 | **56.8%** | 19.0% | +14.8 | c46 / i35 / a19 / m0 / d0, n=100 |
| QP4 (`fired-if-wrong`)               | 46.8%     | 22.2% |  +4.8 | c36 / i41 / a22 / m0 / d1, n=100  |
| QP5 (`decommissioned`)               | 47.3%     |  7.0% |  +5.3 | c44 / i49 / a7  / m0 / d0, n=100 |
| QP6 (`prof-rubric`)                  | **54.5%** | 11.1% | +12.5 | c48 / i40 / a11 / m0 / d=1, n=100  |
| QP7 (`humanity-extinction`)          | 51.5%     |  3.0% |  +9.5 | c50 / i47 / a3  / m0 / d0, n=100 |

## Quantitative prompts

Rubric format: `(r_correct, r_abstain, r_incorrect)`. Abstention rate =
`num_abstained / num_total`.

| Rubric | acc_attempted | Abst rate | Δ vs baseline | Counts (c/i/a/m/d, n) |
|---|---:|---:|---:|---|
| `(+1,  0,   −1)`   | 42.3% | 3.0% |  +0.3 | c41 / i56 / a3 / m0 / d0, n=100 |
| `(+1,  0,   −5)`   | 44.8% | 4.0% |  +2.8 | c43 / i53 / a4 / m0 / d0, n=100 |
| `(+1,  0,  −10)`   | 45.8% | 4.0% |  +3.8 | c44 / i52 / a4 / m0 / d0, n=100 |
| `(+1,  0,  −25)`   | **51.5%** | 3.0% |  +9.5 | c50 / i47 / a3 / m0 / d0, n=100 |
| `(+1,  0, −100)`   | **49.0%** | 4.0% |  +7.0 | c47 / i49 / a4 / m0 / d0, n=100 |
| `(−1, +10, −10)`   | 43.5% | 8.0% |  +1.5 | c40 / i52 / a8 / m0 / d0, n=100 |
