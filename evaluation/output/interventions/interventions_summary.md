# Intervention results (math)

Source: `evaluation/output/interventions/*/cautious_metrics.json`. `acc_attempted` = `num_correct / num_attempted` (%); `abst` = `num_abstained`, `indet` = `num_indeterminate`, `mixed` = `num_incorrect_mixed`, `n` = `num_total`.

Legend: c/i/a/m/d = correct/incorrect/abstained/mixed/indeterminate

> **Update:** `qwen3.5-397b` and `deepseek-v4-pro` tables below were re-scored
> with the reasoning-trace-aware cautious evaluator (everything up to and
> including the last `</think>` token is stripped before `\boxed{...}` parsing).
> This removes the large `mixed` counts caused by tentative `\boxed{UNSURE}`
> inside the models' thinking blocks and surfaces the *committed* answer
> written after `</think>`. `claude-haiku-4-5` and `gpt-5.4-nano` do not emit
> `</think>` markers and are unaffected.

## claude-haiku-4-5

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 62.4% (c53/i30/a15/m2/d0, n=100) | 61.0% (c50/i28/a18/m4/d0, n=100) | 61.1% (c55/i33/a10/m2/d0, n=100) | 63.2% (c55/i27/a13/m5/d0, n=100) |
| 2 — multi-turn | 77.6% (c52/i15/a33/m0/d0, n=100) | 73.4% (c47/i16/a36/m1/d0, n=100) | 78.6% (c55/i14/a30/m1/d0, n=100) | 73.0% (c54/i20/a26/m0/d0, n=100) |
| 3 — multi-turn no-conf | 73.4% (c58/i21/a21/m0/d0, n=100) | 75.6% (c59/i19/a22/m0/d0, n=100) | 76.8% (c53/i14/a31/m2/d0, n=100) | 74.7% (c59/i19/a21/m1/d0, n=100) |
| 4 — post-hoc τ(λ) | 92.3% (c12/i1/a87/m0/d0, n=100) | 0.0% (c0/i0/a100/m0/d0, n=100) | 0.0% (c0/i0/a100/m0/d0, n=100) | 0.0% (c0/i0/a100/m0/d0, n=100) |

## gpt-5.4-nano

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 65.2% (c30/i9/a54/m7/d0, n=100) | 56.0% (c28/i11/a49/m11/d0, n=99) | 60.0% (c39/i8/a35/m18/d0, n=100) | 59.2% (c45/i16/a23/m15/d0, n=99) |
| 2 — multi-turn | 23.1% (c15/i45/a35/m5/d0, n=100) | 23.5% (c16/i48/a31/m4/d0, n=99) | 11.8% (c9/i65/a24/m2/d0, n=100) | 13.9% (c11/i65/a21/m3/d0, n=100) |
| 3 — multi-turn no-conf | 32.9% (c24/i39/a27/m10/d0, n=100) | 26.9% (c18/i39/a33/m10/d0, n=100) | 10.3% (c8/i66/a22/m4/d0, n=100) | 19.0% (c15/i50/a21/m14/d0, n=100) |
| 4 — post-hoc τ(λ) | 80.0% (c4/i1/a95/m0/d0, n=100) | 0.0% (c0/i0/a99/m0/d0, n=99) | 0.0% (c0/i0/a100/m0/d0, n=100) | 0.0% (c0/i0/a99/m0/d0, n=99) |

## gemini-3.1-flash-lite-preview

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 69.6% (c55/i24/a21/m0/d0, n=100) | 65.9% (c56/i29/a15/m0/d0, n=100) | 59.4% (c57/i39/a4/m0/d0, n=100) | 58.8% (c57/i40/a3/m0/d0, n=100) |
| 2 — multi-turn | 77.1% (c54/i14/a30/m2/d0, n=100) | 72.2% (c52/i16/a28/m4/d0, n=100) | 70.7% (c58/i23/a18/m1/d0, n=100) | 66.3% (c59/i28/a11/m2/d0, n=100) |
| 3 — multi-turn no-conf | 71.2% (c57/i18/a20/m5/d0, n=100) | 72.1% (c49/i16/a32/m3/d0, n=100) | 65.9% (c56/i27/a15/m2/d0, n=100) | 63.3% (c57/i31/a10/m2/d0, n=100) |
| 4 — post-hoc τ(λ) | 91.7% (c22/i2/a76/m0/d0, n=100) | 84.2% (c16/i3/a81/m0/d0, n=100) | 80.0% (c32/i8/a60/m0/d0, n=100) | 87.5% (c28/i4/a68/m0/d0, n=100) |

## qwen3.5-397b

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 86.8% (c79/i12/a9/m0/d0, n=100) | 86.2% (c81/i11/a6/m2/d0, n=100) | 86.7% (c85/i11/a2/m2/d0, n=100) | 79.8% (c75/i15/a6/m4/d0, n=100) |
| 2 — multi-turn | 94.0% (c78/i4/a17/m1/d0, n=100) | 94.0% (c78/i5/a17/m0/d0, n=100) | 87.6% (c78/i5/a11/m6/d0, n=100) | 89.4% (c76/i7/a10/m2/d0, n=95) |
| 3 — multi-turn no-conf | 88.4% (c84/i10/a5/m1/d0, n=100) | 91.3% (c84/i8/a8/m0/d0, n=100) | 92.3% (c84/i7/a9/m0/d0, n=100) | 91.4% (c85/i8/a5/m0/d0, n=98) |
| 4 — post-hoc τ(λ) | 92.8% (c64/i5/a31/m0/d0, n=100) | 90.2% (c37/i4/a59/m0/d0, n=100) | 92.7% (c51/i4/a45/m0/d0, n=100) | 90.2% (c46/i5/a49/m0/d0, n=100) |

## deepseek-v4-pro

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 94.3% (c83/i5/a6/m0/d6, n=100) | 96.5% (c83/i3/a9/m0/d5, n=100) | 95.6% (c86/i4/a3/m0/d7, n=100) | 94.0% (c78/i4/a9/m1/d7, n=99) |
| 2 — multi-turn | 91.0% (c81/i8/a11/m0/d0, n=100) | 95.0% (c76/i4/a18/m0/d2, n=100) | 94.3% (c82/i5/a12/m0/d1, n=100) | 95.1% (c77/i3/a14/m1/d1, n=96) |
| 3 — multi-turn no-conf | 92.0% (c81/i7/a12/m0/d0, n=100) | 89.3% (c75/i7/a16/m2/d0, n=100) | 92.9% (c78/i4/a16/m2/d0, n=100) | 91.0% (c81/i6/a8/m2/d1, n=98) |
| 4 — post-hoc τ(λ) | 93.7% (c59/i4/a37/m0/d0, n=100) | 89.8% (c44/i5/a51/m0/d0, n=100) | 88.5% (c46/i6/a48/m0/d0, n=100) | 97.1% (c33/i1/a65/m0/d0, n=99) |

## Abstention rate (`num_abstained / num_total`)

### claude-haiku-4-5

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 15.0% (15/100) | 18.0% (18/100) | 10.0% (10/100) | 13.0% (13/100) |
| 2 — multi-turn | 33.0% (33/100) | 36.0% (36/100) | 30.0% (30/100) | 26.0% (26/100) |
| 3 — multi-turn no-conf | 21.0% (21/100) | 22.0% (22/100) | 31.0% (31/100) | 21.0% (21/100) |
| 4 — post-hoc τ(λ) | 87.0% (87/100) | 100.0% (100/100) | 100.0% (100/100) | 100.0% (100/100) |

### gpt-5.4-nano

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 54.0% (54/100) | 49.5% (49/99) | 35.0% (35/100) | 23.2% (23/99) |
| 2 — multi-turn | 35.0% (35/100) | 31.3% (31/99) | 24.0% (24/100) | 21.0% (21/100) |
| 3 — multi-turn no-conf | 27.0% (27/100) | 33.0% (33/100) | 22.0% (22/100) | 21.0% (21/100) |
| 4 — post-hoc τ(λ) | 95.0% (95/100) | 100.0% (99/99) | 100.0% (100/100) | 100.0% (99/99) |

### gemini-3.1-flash-lite-preview

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 21.0% (21/100) | 15.0% (15/100) | 4.0% (4/100) | 3.0% (3/100) |
| 2 — multi-turn | 30.0% (30/100) | 28.0% (28/100) | 18.0% (18/100) | 11.0% (11/100) |
| 3 — multi-turn no-conf | 20.0% (20/100) | 32.0% (32/100) | 15.0% (15/100) | 10.0% (10/100) |
| 4 — post-hoc τ(λ) | 76.0% (76/100) | 81.0% (81/100) | 60.0% (60/100) | 68.0% (68/100) |

### qwen3.5-397b

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 9.0% (9/100) | 6.0% (6/100) | 2.0% (2/100) | 6.0% (6/100) |
| 2 — multi-turn | 17.0% (17/100) | 17.0% (17/100) | 11.0% (11/100) | 10.5% (10/95) |
| 3 — multi-turn no-conf | 5.0% (5/100) | 8.0% (8/100) | 9.0% (9/100) | 5.1% (5/98) |
| 4 — post-hoc τ(λ) | 31.0% (31/100) | 59.0% (59/100) | 45.0% (45/100) | 49.0% (49/100) |

### deepseek-v4-pro

| Intervention | Quant-25 | Quant-100 | QP6 | QP7 |
|---|---|---|---|---|
| 1 — single-turn multi-step | 6.0% (6/100) | 9.0% (9/100) | 3.0% (3/100) | 9.1% (9/99) |
| 2 — multi-turn | 11.0% (11/100) | 18.0% (18/100) | 12.0% (12/100) | 14.6% (14/96) |
| 3 — multi-turn no-conf | 12.0% (12/100) | 16.0% (16/100) | 16.0% (16/100) | 8.2% (8/98) |
| 4 — post-hoc τ(λ) | 37.0% (37/100) | 51.0% (51/100) | 48.0% (48/100) | 65.7% (65/99) |
