# Intervention results (math)

Source: `evaluation/output/interventions/*/cautious_metrics.json`. `acc_attempted` = `num_correct / num_attempted` (%); `abst` = `num_abstained`, `indet` = `num_indeterminate`, `mixed` = `num_incorrect_mixed`, `n` = `num_total`.

Legend: c/i/a/m/d = correct/incorrect/abstained/mixed/indeterminate

> **Update (May 2026):** the cautious evaluator was patched twice:
> 1. **Multi-turn last-box rule** — for interventions 2 and 3, only the *last* `\boxed{...}` value in the final decision turn is graded. Previously, the model quoting an earlier turn's answer in prose (`"your previous answer was \boxed{6}, but I'll abstain... \boxed{UNSURE}"`) was being mis-classified as `incorrect_mixed`. All `incorrect_mixed` counts for int2/int3 are now 0 by construction.
> 2. **LaTeX-wrapped UNSURE** — `is_unsure()` now matches `\text{UNSURE}`, `\textbf{UNSURE}`, `\mathrm{UNSURE}`, etc. Previously `\boxed{\text{UNSURE}}` extracted to `\text{UNSURE}` and was graded as `incorrect_standard` instead of `abstained`. This affects all interventions, but hit `gpt-5.4-nano` particularly hard (it almost always wraps `UNSURE` in `\text{...}`).
>
> Reasoning-trace stripping (everything up to and including the last `</think>`) remains in place for `qwen3.5-397b` and `deepseek-v4-pro`. `claude-haiku-4-5`, `gpt-5.4-nano`, and `gemini-3.1-flash-lite-preview` do not emit `</think>` markers and are unaffected by that step.

## Baselines (no consequence framing)

Source: `evaluation/output/baselines/<model>/omni-math/math_eval_cot_metrics.json`.
Run with `--prompt standard` (no abstention permitted, no rubric, no stakes); graded with the **standard** evaluator (`math_eval.py`), which scores accuracy over `num_scores` (`acc = num_correct / num_scores`). `empty` = items with no parsable `\boxed{...}` (counted as incorrect, *not* abstained — the baseline prompt offers no abstain channel).

| Model | Accuracy | n | empty | timeout | Conditional acc (correct / non-empty) |
|---|---|---|---|---|---|
| claude-haiku-4-5              | 66.0% | 100 | 0  | 0 | 66.0% |
| gpt-5.4-nano                  | 42.0% | 100 | 0  | 0 | 42.0% |
| gemini-3.1-flash-lite-preview | 60.0% | 100 | 0  | 0 | 60.0% |
| deepseek-v4-pro               | 78.6% | 98  | 13 | 0 | ≈ 90.6% (77/85) |
| qwen3.5-397b                  | 83.5% | 97  | 7  | 0 | ≈ 90.0% (81/90) |
| qwen3.5-9b                    | 53.7% | 95  | 40 | 0 | ≈ 92.7% (51/55) |
| gemma-4-31b                   | 75.0% | 96  | 0  | 0 | 75.0% |

Notes:
- `n` < 100 means some inference-side failures (transient API errors); `--resume` will fill them in.
- `empty_samples` are responses with no parsable `\boxed{...}`, which `math_eval.py` counts as **incorrect** under the standard prompt (no abstain channel). The `Conditional acc` column above subtracts those from the denominator and is the closest apples-to-apples comparison vs. the intervention `acc_attempted` numbers (which also exclude responses without a parsable answer). The qwen-9b 40/95 empty rate is striking — it produced a final `\boxed{...}` only ~58% of the time. Most of those empties end mid-thought (the standard prompt doesn't tell the model when to commit) and would likely vanish under any cautious-style prompt.
- The intervention runs use a slightly different prompt (rubric or qualitative framing inside the system prompt + an explicit abstain channel via `\boxed{UNSURE}`), so accuracy on `n_attempted` for int1 is the closest comparison point to the baseline `acc` here.

## claude-haiku-4-5

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 67.9% (c53/i21/a22/m4/d0, n=100) | 66.7% (c50/i19/a25/m6/d0, n=100) | 72.4% (c55/i17/a24/m4/d0, n=100) | 64.0% (c55/i25/a14/m6/d0, n=100) |
| 2 — multi-turn | 82.5% (c52/i11/a37/m0/d0, n=100) | 75.8% (c47/i15/a38/m0/d0, n=100) | 79.7% (c55/i14/a31/m0/d0, n=100) | 76.1% (c54/i17/a29/m0/d0, n=100) |
| 3 — multi-turn no-conf | 77.3% (c58/i17/a25/m0/d0, n=100) | 77.6% (c59/i17/a24/m0/d0, n=100) | 84.4% (c54/i10/a36/m0/d0, n=100) | 80.8% (c59/i14/a27/m0/d0, n=100) |
| 4 — post-hoc τ(λ) | 92.3% (c12/i1/a87/m0/d0, n=100) | 0.0% (c0/i0/a100/m0/d0, n=100) | 0.0% (c0/i0/a100/m0/d0, n=100) | 0.0% (c0/i0/a100/m0/d0, n=100) |

## gpt-5.4-nano

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 68.2% (c30/i6/a56/m8/d0, n=100) | 59.6% (c28/i7/a52/m12/d0, n=99) | 61.9% (c39/i5/a37/m19/d0, n=100) | 61.6% (c45/i13/a26/m15/d0, n=99) |
| 2 — multi-turn | 83.3% (c15/i3/a82/m0/d0, n=100) | 69.6% (c16/i7/a76/m0/d0, n=99) | 100.0% (c9/i0/a91/m0/d0, n=100) | 84.6% (c11/i2/a87/m0/d0, n=100) |
| 3 — multi-turn no-conf | 77.4% (c24/i7/a69/m0/d0, n=100) | 64.3% (c18/i10/a72/m0/d0, n=100) | 100.0% (c8/i0/a92/m0/d0, n=100) | 75.0% (c15/i5/a80/m0/d0, n=100) |
| 4 — post-hoc τ(λ) | 80.0% (c4/i1/a95/m0/d0, n=100) | 0.0% (c0/i0/a99/m0/d0, n=99) | 0.0% (c0/i0/a100/m0/d0, n=100) | 0.0% (c0/i0/a99/m0/d0, n=99) |

## gemini-3.1-flash-lite-preview

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 69.6% (c55/i24/a21/m0/d0, n=100) | 65.9% (c56/i29/a15/m0/d0, n=100) | 59.4% (c57/i39/a4/m0/d0, n=100) | 58.8% (c57/i40/a3/m0/d0, n=100) |
| 2 — multi-turn | 79.4% (c54/i14/a32/m0/d0, n=100) | 76.5% (c52/i16/a32/m0/d0, n=100) | 71.6% (c58/i23/a19/m0/d0, n=100) | 67.8% (c59/i28/a13/m0/d0, n=100) |
| 3 — multi-turn no-conf | 76.0% (c57/i18/a25/m0/d0, n=100) | 75.4% (c49/i16/a35/m0/d0, n=100) | 67.5% (c56/i27/a17/m0/d0, n=100) | 64.8% (c57/i31/a12/m0/d0, n=100) |
| 4 — post-hoc τ(λ) | 91.7% (c22/i2/a76/m0/d0, n=100) | 84.2% (c16/i3/a81/m0/d0, n=100) | 80.0% (c32/i8/a60/m0/d0, n=100) | 87.5% (c28/i4/a68/m0/d0, n=100) |

## qwen3.5-397b

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 86.8% (c79/i12/a9/m0/d0, n=100) | 86.2% (c81/i11/a6/m2/d0, n=100) | 86.7% (c85/i11/a2/m2/d0, n=100) | 79.8% (c75/i15/a6/m4/d0, n=100) |
| 2 — multi-turn | 95.1% (c78/i4/a18/m0/d0, n=100) | 94.0% (c78/i5/a17/m0/d0, n=100) | 94.0% (c78/i5/a17/m0/d0, n=100) | 91.6% (c76/i7/a12/m0/d0, n=95) |
| 3 — multi-turn no-conf | 89.4% (c84/i10/a6/m0/d0, n=100) | 91.3% (c84/i8/a8/m0/d0, n=100) | 92.3% (c84/i7/a9/m0/d0, n=100) | 91.4% (c85/i8/a5/m0/d0, n=98) |
| 4 — post-hoc τ(λ) | 92.8% (c64/i5/a31/m0/d0, n=100) | 90.2% (c37/i4/a59/m0/d0, n=100) | 92.7% (c51/i4/a45/m0/d0, n=100) | 90.2% (c46/i5/a49/m0/d0, n=100) |

## deepseek-v4-pro

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 94.3% (c83/i5/a6/m0/d6, n=100) | 96.5% (c83/i3/a9/m0/d5, n=100) | 95.6% (c86/i4/a3/m0/d7, n=100) | 94.0% (c78/i4/a9/m1/d7, n=99) |
| 2 — multi-turn | 91.0% (c81/i8/a11/m0/d0, n=100) | 95.0% (c76/i4/a18/m0/d2, n=100) | 94.3% (c82/i5/a12/m0/d1, n=100) | 96.2% (c77/i3/a15/m0/d1, n=96) |
| 3 — multi-turn no-conf | 92.0% (c81/i7/a12/m0/d0, n=100) | 91.5% (c75/i7/a18/m0/d0, n=100) | 95.1% (c78/i4/a18/m0/d0, n=100) | 93.1% (c81/i6/a10/m0/d1, n=98) |
| 4 — post-hoc τ(λ) | 93.7% (c59/i4/a37/m0/d0, n=100) | 89.8% (c44/i5/a51/m0/d0, n=100) | 88.5% (c46/i6/a48/m0/d0, n=100) | 97.1% (c33/i1/a65/m0/d0, n=99) |

## Δ vs baseline (intervention `acc_attempted` − baseline `acc`, percentage points)

Each cell shows `delta  (acc_attempted)`. Positive = consequence framing produces higher accuracy on attempted problems than the standard prompt did over its own n. Baseline anchor for each model is the `acc` field from `evaluation/output/baselines/<model>/omni-math/math_eval_cot_metrics.json`.

Caveats:
- Baseline `acc` and intervention `acc_attempted` use slightly different denominators — baseline counts `empty_samples` as incorrect, while interventions exclude `abstained`/`indeterminate`. Direct subtraction is therefore an approximation, not a strict apples-to-apples comparison.
- `deepseek-v4-pro` and `qwen3.5-397b` baselines are deflated by `empty_samples` (responses with no parsable `\boxed{...}`); their delta tables below are anchored on the **conditional** baseline (correct / non-empty) instead of the raw `acc`, matching what the intervention `acc_attempted` already does on its side. The other models have 0 empty samples in baseline so the two anchors coincide.

### claude-haiku-4-5  (baseline = 66.0%)

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | +1.9  (67.9%) | +0.7  (66.7%) | +6.4  (72.4%) | -2.0  (64.0%) |
| 2 — multi-turn | +16.5  (82.5%) | +9.8  (75.8%) | +13.7  (79.7%) | +10.1  (76.1%) |
| 3 — multi-turn no-conf | +11.3  (77.3%) | +11.6  (77.6%) | +18.4  (84.4%) | +14.8  (80.8%) |
| 4 — post-hoc τ(λ) | +26.3  (92.3%) | n/a (a=0) | n/a (a=0) | n/a (a=0) |

### gpt-5.4-nano  (baseline = 42.0%)

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | +26.2  (68.2%) | +17.6  (59.6%) | +19.9  (61.9%) | +19.6  (61.6%) |
| 2 — multi-turn | +41.3  (83.3%) | +27.6  (69.6%) | +58.0  (100.0%) | +42.6  (84.6%) |
| 3 — multi-turn no-conf | +35.4  (77.4%) | +22.3  (64.3%) | +58.0  (100.0%) | +33.0  (75.0%) |
| 4 — post-hoc τ(λ) | +38.0  (80.0%) | n/a (a=0) | n/a (a=0) | n/a (a=0) |

### gemini-3.1-flash-lite-preview  (baseline = 60.0%)

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | +9.6  (69.6%) | +5.9  (65.9%) | -0.6  (59.4%) | -1.2  (58.8%) |
| 2 — multi-turn | +19.4  (79.4%) | +16.5  (76.5%) | +11.6  (71.6%) | +7.8  (67.8%) |
| 3 — multi-turn no-conf | +16.0  (76.0%) | +15.4  (75.4%) | +7.5  (67.5%) | +4.8  (64.8%) |
| 4 — post-hoc τ(λ) | +31.7  (91.7%) | +24.2  (84.2%) | +20.0  (80.0%) | +27.5  (87.5%) |

### deepseek-v4-pro  (conditional baseline = 90.6%, from raw acc=78.6% on 98 samples with 13 empty)

Anchored on the **conditional** baseline (77 correct / 85 non-empty), matching the qwen3.5-397b table below — the apples-to-apples comparison with intervention `acc_attempted` (which also excludes responses with no parsable answer). Using the raw `acc=78.6%` would inflate every delta below by ~12 pts and obscure the fact that for some cells the framing is roughly break-even or marginally negative on attempted accuracy.

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | +3.7  (94.3%) | +5.9  (96.5%) | +5.0  (95.6%) | +3.4  (94.0%) |
| 2 — multi-turn | +0.4  (91.0%) | +4.4  (95.0%) | +3.7  (94.3%) | +5.6  (96.2%) |
| 3 — multi-turn no-conf | +1.4  (92.0%) | +0.9  (91.5%) | +4.5  (95.1%) | +2.5  (93.1%) |
| 4 — post-hoc τ(λ) | +3.1  (93.7%) | -0.8  (89.8%) | -2.1  (88.5%) | +6.5  (97.1%) |


### qwen3.5-397b  (conditional baseline = 90.0%, from raw acc=83.5% on 97 samples with 7 empty)

Anchored on the **conditional** baseline (correct / non-empty), which is the apples-to-apples comparison vs. the intervention `acc_attempted` numbers (which also exclude responses with no parsable answer). Using the raw `acc=83.5%` would inflate every delta below by ~6.5 pts.

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | -3.2  (86.8%) | -3.8  (86.2%) | -3.3  (86.7%) | -10.2  (79.8%) |
| 2 — multi-turn | +5.1  (95.1%) | +4.0  (94.0%) | +4.0  (94.0%) | +1.6  (91.6%) |
| 3 — multi-turn no-conf | -0.6  (89.4%) | +1.3  (91.3%) | +2.3  (92.3%) | +1.4  (91.4%) |
| 4 — post-hoc τ(λ) | +2.8  (92.8%) | +0.2  (90.2%) | +2.7  (92.7%) | +0.2  (90.2%) |

## Abstention rate (`num_abstained / num_total`)

### claude-haiku-4-5

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 22.0% (22/100) | 25.0% (25/100) | 24.0% (24/100) | 14.0% (14/100) |
| 2 — multi-turn | 37.0% (37/100) | 38.0% (38/100) | 31.0% (31/100) | 29.0% (29/100) |
| 3 — multi-turn no-conf | 25.0% (25/100) | 24.0% (24/100) | 36.0% (36/100) | 27.0% (27/100) |
| 4 — post-hoc τ(λ) | 87.0% (87/100) | 100.0% (100/100) | 100.0% (100/100) | 100.0% (100/100) |

### gpt-5.4-nano

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 56.0% (56/100) | 52.5% (52/99) | 37.0% (37/100) | 26.3% (26/99) |
| 2 — multi-turn | 82.0% (82/100) | 76.8% (76/99) | 91.0% (91/100) | 87.0% (87/100) |
| 3 — multi-turn no-conf | 69.0% (69/100) | 72.0% (72/100) | 92.0% (92/100) | 80.0% (80/100) |
| 4 — post-hoc τ(λ) | 95.0% (95/100) | 100.0% (99/99) | 100.0% (100/100) | 100.0% (99/99) |

### gemini-3.1-flash-lite-preview

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 21.0% (21/100) | 15.0% (15/100) | 4.0% (4/100) | 3.0% (3/100) |
| 2 — multi-turn | 32.0% (32/100) | 32.0% (32/100) | 19.0% (19/100) | 13.0% (13/100) |
| 3 — multi-turn no-conf | 25.0% (25/100) | 35.0% (35/100) | 17.0% (17/100) | 12.0% (12/100) |
| 4 — post-hoc τ(λ) | 76.0% (76/100) | 81.0% (81/100) | 60.0% (60/100) | 68.0% (68/100) |

### qwen3.5-397b

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 9.0% (9/100) | 6.0% (6/100) | 2.0% (2/100) | 6.0% (6/100) |
| 2 — multi-turn | 18.0% (18/100) | 17.0% (17/100) | 17.0% (17/100) | 12.6% (12/95) |
| 3 — multi-turn no-conf | 6.0% (6/100) | 8.0% (8/100) | 9.0% (9/100) | 5.1% (5/98) |
| 4 — post-hoc τ(λ) | 31.0% (31/100) | 59.0% (59/100) | 45.0% (45/100) | 49.0% (49/100) |

### deepseek-v4-pro

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 6.0% (6/100) | 9.0% (9/100) | 3.0% (3/100) | 9.1% (9/99) |
| 2 — multi-turn | 11.0% (11/100) | 18.0% (18/100) | 12.0% (12/100) | 15.6% (15/96) |
| 3 — multi-turn no-conf | 12.0% (12/100) | 18.0% (18/100) | 18.0% (18/100) | 10.2% (10/98) |
| 4 — post-hoc τ(λ) | 37.0% (37/100) | 51.0% (51/100) | 48.0% (48/100) | 65.7% (65/99) |
