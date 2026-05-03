# SWE-bench Pro intervention results

Source: `swebench_pro/results/<model>_int{1,2,3,4}_<config>_n100/`
(`preds.json` + `exit_statuses.yaml` + `eval/eval_results.json`).
All runs use 100 instances / 10 inference workers / `--reasoning-effort medium`.

Legend:
- **abst** = `Abstained` exit status (model ran `exit_abstain`); for int 4 (post-hoc) = patches blanked by τ(λ) rule.
- **fail** = `LimitsExceeded` + `LoopDetected` (runtime failures, no patch).
- **submitted** = `Submitted` exit status.
- **abst rate** = `abst / 100`.
- **total acc** = `correct / 100` (treats abst + fail + incorrect all as non-correct).
- **cond acc** = `correct / (100 - abst)` — accuracy excluding deliberate abstentions; runtime failures (`fail`) still count toward the denominator since the model didn't *choose* to skip them.

## claude-haiku-4-5

### Cell breakdown — `correct / incorrect / abst / fail` (n=100)

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| c=31 / i=69 / a=0 / f=0 | c=34 / i=62 / a=0 / f=0 | c=37 / i=62 / a=0 / f=0 | c=34 / i=65 / a=0 / f=0 |
| **2 — multi-turn (confidence then reveal)**| c=33 / i=67 / a=0 / f=0 | c=20 / i=73 / a=1 / f=0 | c=38 / i=62 / a=0 / f=0 | c=33 / i=66 / a=0 / f=0 |
| **3 — multi-turn no-conf**| c=23 / i=76 / a=0 / f=0 | c=35 / i=64 / a=0 / f=0 | c=31 / i=69 / a=0 / f=0 | c=37 / i=62 / a=0 / f=0 |
| **4 — post-hoc τ(λ)**| c=34 / i=61 / a=5 / f=0 | c=31 / i=52 / a=17 / f=0 | c=0 / i=1 / a=99 / f=0 | c=0 / i=0 / a=100 / f=0 |

### Total accuracy — `correct / 100`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| **31.0%** (31/100) | **34.0%** (34/100) | **37.0%** (37/100) | **34.0%** (34/100) |
| **2 — multi-turn (confidence then reveal)**| **33.0%** (33/100) | **20.0%** (20/100) | **38.0%** (38/100) | **33.0%** (33/100) |
| **3 — multi-turn no-conf**| **23.0%** (23/100) | **35.0%** (35/100) | **31.0%** (31/100) | **37.0%** (37/100) |
| **4 — post-hoc τ(λ)**| **34.0%** (34/100) | **31.0%** (31/100) | **0.0%** (0/100) | **0.0%** (0/100) |

### Conditional accuracy — `correct / (100 - abst)`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| **31.0%** (31/100) | **34.0%** (34/100) | **37.0%** (37/100) | **34.0%** (34/100) |
| **2 — multi-turn (confidence then reveal)**| **33.0%** (33/100) | **20.2%** (20/99) | **38.0%** (38/100) | **33.0%** (33/100) |
| **3 — multi-turn no-conf**| **23.0%** (23/100) | **35.0%** (35/100) | **31.0%** (31/100) | **37.0%** (37/100) |
| **4 — post-hoc τ(λ)**| **35.8%** (34/95) | **37.3%** (31/83) | **0.0%** (0/1) | n/a (all abstained) |

### Abstention rate — `abst / 100`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) |
| **2 — multi-turn (confidence then reveal)**| 0.0% (0/100) | 1.0% (1/100) | 0.0% (0/100) | 0.0% (0/100) |
| **3 — multi-turn no-conf**| 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) |
| **4 — post-hoc τ(λ)**| 5.0% (5/100) | 17.0% (17/100) | 99.0% (99/100) | 100.0% (100/100) |

## gpt-5.4-nano

### Cell breakdown — `correct / incorrect / abst / fail` (n=100)

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| c=32 / i=41 / a=0 / f=25 | c=28 / i=38 / a=0 / f=33 | c=28 / i=44 / a=1 / f=25 | c=34 / i=47 / a=0 / f=19 |
| **2 — multi-turn (confidence then reveal)**| c=26 / i=42 / a=0 / f=31 | c=24 / i=52 / a=0 / f=24 | c=29 / i=41 / a=0 / f=30 | c=25 / i=42 / a=0 / f=33 |
| **3 — multi-turn no-conf**| c=25 / i=45 / a=0 / f=30 | c=21 / i=40 / a=0 / f=39 | c=27 / i=43 / a=0 / f=30 | c=26 / i=46 / a=0 / f=28 |
| **4 — post-hoc τ(λ)**| c=11 / i=4 / a=85 / f=0 | c=0 / i=0 / a=100 / f=0 | c=0 / i=0 / a=100 / f=0 | c=0 / i=0 / a=100 / f=0 |

### Total accuracy — `correct / 100`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| **32.0%** (32/100) | **28.0%** (28/100) | **28.0%** (28/100) | **34.0%** (34/100) |
| **2 — multi-turn (confidence then reveal)**| **26.0%** (26/100) | **24.0%** (24/100) | **29.0%** (29/100) | **25.0%** (25/100) |
| **3 — multi-turn no-conf**| **25.0%** (25/100) | **21.0%** (21/100) | **27.0%** (27/100) | **26.0%** (26/100) |
| **4 — post-hoc τ(λ)**| **11.0%** (11/100) | **0.0%** (0/100) | **0.0%** (0/100) | **0.0%** (0/100) |

### Conditional accuracy — `correct / (100 - abst)`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| **32.0%** (32/100) | **28.0%** (28/100) | **28.3%** (28/99) | **34.0%** (34/100) |
| **2 — multi-turn (confidence then reveal)**| **26.0%** (26/100) | **24.0%** (24/100) | **29.0%** (29/100) | **25.0%** (25/100) |
| **3 — multi-turn no-conf**| **25.0%** (25/100) | **21.0%** (21/100) | **27.0%** (27/100) | **26.0%** (26/100) |
| **4 — post-hoc τ(λ)**| **73.3%** (11/15) | n/a (all abstained) | n/a (all abstained) | n/a (all abstained) |

### Abstention rate — `abst / 100`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| 0.0% (0/100) | 0.0% (0/100) | 1.0% (1/100) | 0.0% (0/100) |
| **2 — multi-turn (confidence then reveal)**| 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) |
| **3 — multi-turn no-conf**| 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) |
| **4 — post-hoc τ(λ)**| 85.0% (85/100) | 100.0% (100/100) | 100.0% (100/100) | 100.0% (100/100) |

## gemini-3.1-flash-lite-preview

### Cell breakdown — `correct / incorrect / abst / fail` (n=100)

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| c=24 / i=69 / a=0 / f=1 | c=24 / i=70 / a=1 / f=3 | c=15 / i=78 / a=3 / f=2 | c=19 / i=76 / a=0 / f=3 |
| **2 — multi-turn (confidence then reveal)**| c=22 / i=77 / a=1 / f=0 | c=15 / i=79 / a=0 / f=6 | c=15 / i=79 / a=0 / f=3 | c=20 / i=74 / a=0 / f=5 |
| **3 — multi-turn no-conf**| c=22 / i=76 / a=0 / f=2 | c=18 / i=80 / a=0 / f=2 | c=23 / i=74 / a=1 / f=2 | c=27 / i=71 / a=0 / f=2 |
| **4 — post-hoc τ(λ)**| c=20 / i=71 / a=9 / f=0 | c=18 / i=52 / a=30 / f=0 | c=17 / i=46 / a=37 / f=0 | c=17 / i=42 / a=41 / f=0 |

### Total accuracy — `correct / 100`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| **24.0%** (24/100) | **24.0%** (24/100) | **15.0%** (15/100) | **19.0%** (19/100) |
| **2 — multi-turn (confidence then reveal)**| **22.0%** (22/100) | **15.0%** (15/100) | **15.0%** (15/100) | **20.0%** (20/100) |
| **3 — multi-turn no-conf**| **22.0%** (22/100) | **18.0%** (18/100) | **23.0%** (23/100) | **27.0%** (27/100) |
| **4 — post-hoc τ(λ)**| **20.0%** (20/100) | **18.0%** (18/100) | **17.0%** (17/100) | **17.0%** (17/100) |

### Conditional accuracy — `correct / (100 - abst)`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| **24.0%** (24/100) | **24.2%** (24/99) | **15.5%** (15/97) | **19.0%** (19/100) |
| **2 — multi-turn (confidence then reveal)**| **22.2%** (22/99) | **15.0%** (15/100) | **15.0%** (15/100) | **20.0%** (20/100) |
| **3 — multi-turn no-conf**| **22.0%** (22/100) | **18.0%** (18/100) | **23.2%** (23/99) | **27.0%** (27/100) |
| **4 — post-hoc τ(λ)**| **22.0%** (20/91) | **25.7%** (18/70) | **27.0%** (17/63) | **28.8%** (17/59) |

### Abstention rate — `abst / 100`

| Intervention | Quant-25 (+1/-5/0) | Quant-100 (+1/-10/0) | QP6 (team-lead) | QP7 (humanity) |
|---|---|---|---|---|
| **1 — single-turn multi-step**| 0.0% (0/100) | 1.0% (1/100) | 3.0% (3/100) | 0.0% (0/100) |
| **2 — multi-turn (confidence then reveal)**| 1.0% (1/100) | 0.0% (0/100) | 0.0% (0/100) | 0.0% (0/100) |
| **3 — multi-turn no-conf**| 0.0% (0/100) | 0.0% (0/100) | 1.0% (1/100) | 0.0% (0/100) |
| **4 — post-hoc τ(λ)**| 9.0% (9/100) | 30.0% (30/100) | 37.0% (37/100) | 41.0% (41/100) |

## Cross-model takeaways

### 1. Live-run abstention is essentially off for Haiku and GPT-5.4-nano

Across the 24 live cells (`int1`/`int2`/`int3` × 4 framings) for these two
models, the `Abstained` exit status fires a total of **2/2400** instances —
Haiku abstains once (int2/quant_100) and GPT-5.4-nano once (int1/qp6).
Neither the quantitative penalty (−10 / submission), the team-lead framing,
nor the humanity framing trigger meaningful abstention behavior. The
`exit_abstain` tool is available throughout, and the system prompt
explicitly tells the model it can use it; both models simply don't.
This mirrors the math finding that Claude in particular ignores
consequence framing.

### 2. GPT-5.4-nano's `LimitsExceeded` rate is the dominant signal

Per-cell `LimitsExceeded`+`LoopDetected` count for GPT-5.4-nano ranges
from 19 to 39 (out of 100), vs 0–6 for Gemini and 0 for Haiku. These are
instances where the agent ran out of step/cost budget before submitting —
functionally unattempted, but distinct from a deliberate abstention.
Conditional accuracy here (`correct / (100 - abst)`) leaves these in the
denominator on purpose, so the GPT-5.4-nano conditional numbers
understate its accuracy on cells it actually finished.

### 3. Gemini abstains slightly more under qualitative framings

Live-run abstention for Gemini: int1 sees 0/1/3/0 across quant_25 / quant_100 /
qp6 / qp7; the qp6 / qp7 cells under post-hoc τ(λ) blank 37%/41% of patches
vs only 9%/30% for the quant cells. This suggests Gemini's stated confidence
is lower under qualitative consequence framings than under explicit −5/−10
rubrics — the opposite of the (intended) calibration story.

### 4. Int4 (post-hoc τ(λ)) over-abstains on Haiku for QP6/QP7

Haiku under int4 + qp6/qp7 blanks **99–100 of 100 patches**, leaving total
accuracy at 0%. The post-hoc threshold rule + Haiku's habit of reporting
low numerical confidence under qualitative framings combine to suppress
everything. The same rule on Haiku + quant_25 keeps 95/100 patches and
nudges conditional accuracy from 31.0% (int1 baseline) → 35.8%.

### 5. No intervention/framing combo Pareto-dominates int1 on total accuracy

Per-model best total accuracy across all 16 cells:
- **Haiku**: 38.0% (int2 / qp6) vs 37.0% int1 baseline (qp6) — +1pt.
- **GPT-5.4-nano**: 34.0% (int1 / qp7) — int1 wins outright; int4 collapses to ≤11%.
- **Gemini-3.1-flash-lite**: 27.0% (int3 / qp7) vs 19.0% int1 (qp7) — +8pt; int3 (no confidence step) is the only intervention that meaningfully helps Gemini.

Conditional accuracy improvements from int4 are real for Haiku/Gemini
(post-hoc filtering does select a slightly higher-confidence subset when
it leaves anything to score), but they come at the cost of huge total-
accuracy drops — i.e. the model's confidence signal is *correlated* with
correctness but not strongly enough for τ(λ) thresholding to be
competitive with just submitting everything.

