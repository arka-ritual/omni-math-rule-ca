# Intervention results (math)

Source: `evaluation/output/interventions/*/cautious_metrics.json`. `acc_attempted` = `num_correct / num_attempted` (%); `abst` = `num_abstained`, `indet` = `num_indeterminate`, `mixed` = `num_incorrect_mixed`, `n` = `num_total`.

Legend: c/i/a/m/d = correct/incorrect/abstained/mixed/indeterminate
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
