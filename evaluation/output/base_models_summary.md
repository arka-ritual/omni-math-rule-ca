# Base Models on Omni-MATH-Rule

All runs on N=100 problems unless noted. Few-shot scaffolding (4-shot) was applied
only to base models. `acc` = standard accuracy; `acc-attempted` = accuracy on
attempted (excludes deliberate `abstained` and ill-formed `indeterminate`).

## Qwen 3.5 0.8B

| Variant | Prompt | N | Abst | Indet | Attempted | acc-attempted | acc |
|---|---|---:|---:|---:|---:|---:|---:|
| **base** (no fewshot) | standard | 100 | – | – | 100 | – | **10.0%** |
| **base** (no fewshot) | ultra_cautious | 100 | 44 | – | 56 | **19.6%** | – |
| instruct | standard | 100 | – | – | 100 | – | **14.0%** |
| instruct | ultra_cautious | 100 | 9 | – | 91 | **16.5%** | – |
| instruct | quantitative_grading | 100 | 2 | – | 98 | **14.3%** | – |

The Qwen base model already follows `\boxed{}` formatting reliably without few-shot.
Instruct vs base: instruct is +4pt on standard but the base model abstains far more
under `ultra_cautious` (44 vs 9), pushing its `acc-attempted` slightly above the
instruct version (19.6% vs 16.5%).

## Gemma-4 E2B (~2B params, "effective")

| Variant | Prompt | Few-shot | N | Abst | Indet | Attempted | acc-attempted | acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **base** | standard | normal | 100 | – | 1 | 99 | – | **3.0%** |
| **base** | ultra_cautious | conseq_no_abstain | 100 | 0 | 1 | 99 | **4.0%** | – |
| **base** | ultra_cautious | conseq_random_abstain | 100 | 43 | 0 | 57 | **7.0%** | – |
| **base** | ultra_cautious | conseq_correct_abstain | 100 | 52 | 0 | 48 | **0.0%** | – |
| **base** | ultra_cautious | conseq_always_submit | 100 | 0 | 2 | 98 | **2.0%** | – |
| **base** | ultra_cautious | conseq_always_abstain | **10** | 9 | 0 | 1 | 0.0% | – |
| instruct | standard | – | 100 | – | 1 | 99 | – | **31.0%** |
| instruct | ultra_cautious | – | 100 | 0 | 17 | 83 | **42.2%** | – |
| instruct | quantitative_grading | – | 100 | 19 | – | 81 | **37.0%** | – |

Instruct is dramatically better (+28pt on standard). Few-shot scaffolding does
not help the base model — accuracy stays in 0–7% across all variants. Abstention
behavior is governed almost entirely by which abstain pattern the few-shot
demonstrates: 0% abstention with `conseq_no_abstain`/`always_submit`, ~50% with
`random`/`correct_abstain`, ~90% with `always_abstain`.

## Gemma-4 E4B (~4B params, "effective")

| Variant | Prompt | Few-shot | N | Abst | Indet | Attempted | acc-attempted | acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **base** | standard | normal | 100 | – | 0 | 100 | – | **7.0%** |
| **base** | ultra_cautious | normal | 100 | 0 | 0 | 100 | **9.0%** | – |
| **base** | ultra_cautious | conseq_no_abstain | 100 | 1 | 2 | 97 | **8.2%** | – |
| **base** | ultra_cautious | conseq_random_abstain | 100 | 33 | 1 | 66 | **10.6%** | – |
| **base** | ultra_cautious | conseq_correct_abstain | 100 | 34 | 2 | 64 | **6.2%** | – |
| **base** | ultra_cautious | conseq_always_submit | 100 | 2 | 3 | 95 | **9.5%** | – |
| **base** | ultra_cautious | conseq_always_abstain | 100 | 96 | 1 | 3 | **0.0%** | – |
| instruct | standard | – | 100 | – | 1 | 99 | – | **44.0%** |
| instruct | ultra_cautious | – | 100 | 6 | 14 | 80 | **48.8%** | – |

Instruct is again far ahead (+37pt). Among base few-shot variants, `random_abstain`
gives the best `acc-attempted` (10.6%) — i.e. mixing correct/incorrect abstain
demonstrations leaves the model with the most diverse cues, slightly outperforming
both "always submit" (9.5%) and "correct_abstain" (6.2%). The
`conseq_correct_abstain` variant (which "should" be the most useful demonstration)
actually hurts attempted accuracy compared to no-abstain, suggesting the base
model is mimicking the abstain-on-hard-problem pattern but losing precision when
it does answer.

## Qwen 3.5 9B

> **Note:** All cautious-evaluator numbers below use the updated evaluator
> that strips reasoning traces (everything up to and including the last
> `</think>`) before parsing `\boxed{...}`. This prevents tentative
> `\boxed{UNSURE}` inside the model's thinking from overriding the final
> committed answer and significantly cleans up the instruct-sweep accuracy.

### Baselines (no consequence framing) and instruct comparisons

| Variant | Prompt | Few-shot | N | Abst | Indet | Attempted | acc-attempted | acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **base** | standard | normal | 100 | – | 3 | 97 | – | **21.0%** |
| instruct | standard | – | 117 | – | 0 | 117 | – | **85.5%** |
| instruct | ultra_cautious (=QP1) | – | 107 | 1 | 0 | 106 | **85.8%** | – |

### Base model: 9 rubrics × 5 consequence framings — `acc-attempted` (abstained / N≈100)

Each cell shows `acc-attempted%  (#abstained)`. Bold marks the best framing per rubric. Rubric format is (r_correct, r_incorrect, r_abstain).

| Rubric | conseq_no_abstain | conseq_random_abstain | conseq_correct_abstain | conseq_always_submit | conseq_always_abstain |
|---|---:|---:|---:|---:|---:|
| **QP1** (`ultra_cautious`)        | 24.5 (6)  | 22.4 (33) | 13.7 (27) | **27.9 (14)** | 26.1 (77) |
| **QP4** (`fired-if-wrong`)        | 24.4 (10) | 15.4 (35) | **25.0 (40)** | 19.1 (11) | 6.7 (85)  |
| **QP7** (`humanity-extinction`)   | 19.8 (4)  | 19.2 (27) | 10.9 (36) | **22.1 (5)**  | 12.5 (84) |
| Quant `( 1,   0,   0)`            | 16.7 (4)  | **24.5 (47)** | 7.0 (28)  | 21.5 (7)  | 0.0 (92)  |
| Quant `(10,  −1,   0)`            | 22.6 (7)  | **23.8 (37)** | 19.7 (34) | 23.1 (8)  | 13.0 (77) |
| Quant `(10,  −5,   0)`            | 19.4 (7)  | 19.1 (32) | 11.1 (37) | **23.9 (8)**  | 13.3 (85) |
| Quant `( 1,  −1,   0)`            | 15.8 (5)  | 16.7 (28) | 17.7 (38) | **25.0 (7)**  | 7.1 (86)  |
| Quant `( 1, −10,   0)`            | 18.2 (1)  | 8.7 (31)  | 11.3 (38) | **21.1 (10)** | 9.1 (89)  |
| Quant `(−1, −10, +10)`            | **28.3 (8)** | 17.6 (32) | 10.4 (32) | 20.5 (12) | 21.1 (81) |

Best framing per rubric (9/9): `always_submit` wins 5× (QP1, QP7, Q`(10,−5,0)`,
Q`(1,−1,0)`, Q`(1,−10,0)`), `random_abstain` 2× (Q`(1,0,0)`, Q`(10,−1,0)`),
`correct_abstain` 1× (QP4), and `no_abstain` 1× (the asymmetric-reward
Q`(−1,−10,+10)`). `always_abstain` never wins on a non-trivial-N basis.

The runaway "save lives by always answering" priors from the `always_submit`
few-shot keep accuracy in the 19–28% band even under heavy abstain incentives,
which is the same band as the no-framing `normal` baseline (~21.6% averaged
across quant rubrics, 23.9% on QP1 normal). Two notable exceptions:

- The "abstaining is rewarded" rubric `(1, 0, 0)` flips the winner to
  `random_abstain` — when abstaining costs nothing, mixing in 50% abstain
  demonstrations actually selects the easier problems to attempt (24.5%).
- The "asymmetric reward for correct" rubric `(−1, −10, +10)` is the only one
  where `no_abstain` is best (28.3%) — the +10 vs −1 ratio is internalized
  as "answer is 10× more rewarding than abstaining", overriding the few-shot's
  abstain pattern.

`conseq_correct_abstain` still collapses to single-digit `acc-attempted` on
rubric `(1, 0, 0)` (7.0%) and hits double-digit floors on QP1 (13.7%) and
QP7 (10.9%), confirming the earlier finding that asking the model to mimic
"abstain only when wrong" makes it abstain on its highest-confidence problems
instead.

### Instruct (qwen3.5-9b-instruct): 9-rubric sweep, no few-shot

| Rubric | N | Abst | Indet | Attempted | Correct | acc-attempted |
|---|---:|---:|---:|---:|---:|---:|
| **QP1** (`ultra_cautious`)        | 107 | 1 | 0 | 106 | 91 | **85.8%** |
| **QP4** (`fired-if-wrong`)        |  99 | 4 | 0 |  95 | 78 | **82.1%** |
| **QP7** (`humanity-extinction`)   |  99 | 1 | 0 |  98 | 84 | **85.7%** |
| Quant `( 1,   0,   0)`            |  99 | 1 | 0 |  98 | 82 | **83.7%** |
| Quant `(10,  −1,   0)`            | 100 | 5 | 0 |  95 | 79 | **83.2%** |
| Quant `(10,  −5,   0)`            | 100 | 2 | 0 |  98 | 82 | **83.7%** |
| Quant `( 1,  −1,   0)`            |  99 | 4 | 0 |  95 | 80 | **84.2%** |
| Quant `( 1, −10,   0)`            |  99 | 1 | 0 |  98 | 85 | **86.7%** |
| Quant `(−1, −10, +10)`            | 100 | 5 | 0 |  95 | 74 | **77.9%** |

Across all 9 rubrics, qwen3.5-9b-instruct sits in a tight **77.9–86.7%**
`acc-attempted` band (range = 8.8pt), very close to gemma-4-31b-it's band
(75.0–83.3%, range 8.3pt). Three observations:

1. **Abstention is sparse but non-zero (0–5 per 100).** Unlike the earlier
   parser, which saw 0 abstentions on most rubrics, the updated evaluator
   correctly identifies cases where Qwen commits `\boxed{UNSURE}` after its
   reasoning trace. Quant `(10, −1, 0)` and `(−1, −10, +10)` trigger 5
   abstentions each, Quant `(1, −1, 0)` triggers 4, and QP4 triggers 4.
   Abstention is still lower than `gemma-4-31b-it`'s pattern, but the
   instruct model is not entirely oblivious to reward asymmetry.
2. **The asymmetric-reward rubric `(−1, −10, +10)` is still the global floor
   (77.9%, with 5 abstentions out of 100), but no longer a *collapse*.**
   Previously reported as 62.0%, the jump to 77.9% mostly reflects removing
   mid-reasoning `\boxed{UNSURE}` from correct final answers. `(−1, −10, +10)`
   still underperforms QP1 by ~8pt — the rubric does degrade math marginally,
   but the effect is roughly half of what the old parser suggested.
3. **QP4 still underperforms QP1/QP7 (82.1% vs 85.8% / 85.7%), but only
   modestly (~3.7pt).** The `fired-if-wrong` framing lowers attempted
   accuracy by 3–4pt vs QP1, not the 9pt we previously reported. Qwen
   treats QP1's terse "catastrophic consequences" as higher signal than
   QP4's "you'll get fired", but the gap is small.

## Gemma-4 31B

### Baselines (no consequence framing) and instruct comparisons

| Variant | Prompt | Few-shot | N | Abst | Indet | Attempted | acc-attempted | acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **base** | standard | normal | 100 | – | 1 | 99 | – | **10.0%** |
| instruct | standard | – | 100 | – | 0 | 100 | – | **78.0%** |
| instruct | ultra_cautious (=QP1) | – | 98 | 1 | 0 | 97 | **78.4%** | – |

### Base model: 8 rubrics × 5 consequence framings — `acc-attempted` (abstained / 100)

| Rubric | conseq_no_abstain | conseq_random_abstain | conseq_correct_abstain | conseq_always_submit | conseq_always_abstain |
|---|---:|---:|---:|---:|---:|
| **QP1** (`ultra_cautious`)        | 16.5 (9)  | 14.3 (57) | 10.6 (53) | **20.0 (30)** | 6.2 (84)  |
| **QP4** (`fired-if-wrong`)        | 12.6 (13) | **15.2 (54)** | 13.3 (55) | 14.5 (31) | 0.0 (94)  |
| **QP7** (`humanity-extinction`)   | 11.2 (10) | 10.4 (52) | **13.5 (48)** | 11.7 (23) | 0.0 (92)  |
| Quant `( 1,   0,   0)`            | 13.4 (18) | 13.0 (45) | 9.1 (45)  | **17.6 (24)** | 12.5 (92) |
| Quant `(10,  −1,   0)`            | **16.3 (14)** | **16.3 (57)** | 9.6 (48)  | 13.3 (24) | 7.7 (87)  |
| Quant `(10,  −5,   0)`            | 14.3 (16) | **17.9 (44)** | 5.6 (46)  | 17.1 (24) | 7.7 (87)  |
| Quant `( 1,  −1,   0)`            | 14.4 (10) | 5.8 (48)  | **15.6 (55)** | 15.1 (26) | 10.0 (90) |
| Quant `( 1, −10,   0)`            | 14.3 (15) | 11.1 (46) | 10.6 (52) | **17.2 (35)** | 0.0 (90)  |
| Quant `(−1, −10, +10)`            | 12.6 (13) | 11.8 (48) | 16.7 (52) | 14.5 (38) | **42.9 (93)** |

Same overall picture as Qwen 9B but compressed into a much narrower band
(roughly 0–18% vs 0–28%): the absolute ceiling reflects Gemma 31B's much
weaker base math ability (10–11% vs 21–24% on the `normal` baselines), and
*no framing rescues this* — the best base-model cell (20.0% on QP1
`always_submit`) is still less than half of even Qwen 9B's worst rubric peak.

`always_submit` is again the most common winner (4/8 rubrics), but the spread
across framings is small (typically 5–7pt on each row), so the few-shot
abstain pattern is exerting much less leverage than on Qwen 9B. The
`(−1, −10, +10)` row's `always_abstain` cell (42.9%) is a small-N artifact
(7 attempts, 3 correct).

The instruct comparison is the most striking part: Gemma-4 31B-it under QP1
hits **78.4%** with only 1 abstention — i.e. instruction tuning lifts attempted
accuracy by **+67pt** while almost completely suppressing the cautious-prompt's
abstain behavior. Whatever mechanism the base model is using to interpret
the consequence framing is essentially absent in the instruct version.

### Instruct (gemma-4-31b-it): 8-rubric sweep, no few-shot

| Rubric | N | Abst | Indet | Attempted | Correct | acc-attempted |
|---|---:|---:|---:|---:|---:|---:|
| **QP1** (`ultra_cautious`)        |  98 | 1 | 0 |  97 | 76 | **78.4%** |
| **QP4** (`fired-if-wrong`)        | 100 | 0 | 0 | 100 | 78 | **78.0%** |
| **QP7** (`humanity-extinction`)   | 100 | 0 | 0 | 100 | 79 | **79.0%** |
| Quant `( 1,   0,   0)`            | 100 | 0 | 0 | 100 | 76 | **76.0%** |
| Quant `(10,  −1,   0)`            | 100 | 3 | 0 |  97 | 79 | **81.4%** |
| Quant `(10,  −5,   0)`            | 100 | 0 | 0 | 100 | 75 | **75.0%** |
| Quant `( 1,  −1,   0)`            | 100 | 1 | 0 |  99 | 75 | **75.8%** |
| Quant `( 1, −10,   0)`            | 100 | 4 | 0 |  96 | 75 | **78.1%** |
| Quant `(−1, −10, +10)`            | 100 | 4 | 0 |  96 | 80 | **83.3%** |

Across all 9 rubrics, gemma-4-31b-it sits in a tight **75.0–83.3%**
`acc-attempted` band (range = 8.3pt). Two further observations:

1. **Abstention is essentially off (0–4 per 100), regardless of framing.**
   Even rubrics that explicitly reward abstaining (`(1, 0, 0)`,
   `(−1, −10, +10)`) elicit at most 4 abstentions out of 100. The
   instruct model treats every cautious/quantitative framing as a polite
   request to "give your best answer", not as an expected-value problem.
2. **Abstention, when it happens, is calibrated.** The 4 abstentions on
   `(−1, −10, +10)` lift `acc-attempted` to **83.3%** (the global peak),
   and the 3 abstentions on `(10, −1, 0)` lift it to **81.4%** (peak among
   non-abstention-rewarding rubrics). On the *same* underlying question
   distribution, removing those few items actually improves the attempted
   pool — so when this instruct model does choose to abstain, it picks
   harder problems. This is the opposite of the base model's behavior
   (where `correct_abstain` few-shot collapses accuracy because the model
   abstains on its highest-confidence problems).

## Cross-model takeaways (updated)

### Best `acc-attempted` per base model

| Model                  | `normal` baseline | best base cell                       | best framing on QP1   | instruct (`standard`) | instruct (QP1) |
|---|---:|---|---|---:|---:|
| Qwen 3.5 0.8B (no FS)  | 19.6%             | 19.6% (QP1, normal)                  | 19.6% (normal, no FS) | 14.0%                 | 16.5% |
| Gemma-4 E2B            | 4.0%              | 7.0% (QP1, random_abstain)           | 7.0% (random_abstain) | 31.0%                 | 42.2% |
| Gemma-4 E4B            | 9.0%              | 10.6% (QP1, random_abstain)          | 10.6% (random_abstain)| 44.0%                 | 48.8% |
| **Qwen 3.5 9B**        | **~23.9%**        | **28.3%** (Q`(−1,−10,+10)`, no_abstain) | always_submit: 27.9%  | **85.5%**             | **85.8%** |
| **Gemma-4 31B**        | 11.1%             | 20.0% (QP1, always_submit)           | always_submit: 20.0%  | 78.0%                 | 78.4% |

### Across the 8-rubric sweep (Qwen 9B + Gemma 31B)

1. **`always_submit` wins most rubric × model cells (8/16).** Across both
   capable base models and all 8 rubrics, the framing that demonstrates "answer
   confidently regardless of correctness" is the single most common winner.
   Remaining wins: `random_abstain` 4× (with one Gemma tie), `correct_abstain`
   3× (QP4 Qwen, QP7 Gemma, `(1,−1,0)` Gemma), `no_abstain` 1× (the
   asymmetric-reward `(−1,−10,+10)` rubric on Qwen). Crucially, *no rubric
   ever selects `always_abstain` as best on a non-trivial-N basis* — abstaining
   en-masse always tanks `acc-attempted`. (Gemma's `(−1,−10,+10)` `always_abstain`
   cell at 42.9% is a small-N artifact: 3 correct out of 7 attempts.)
2. **The reward asymmetry has small effects on framing rank.** Even rubrics
   that strongly reward abstention (e.g. `(−1, −10, +10)`: abstain is +10 vs
   answer expected ≈ −5.5 at base accuracy) don't reliably tilt the winner
   toward `always_abstain` or `correct_abstain`. The few-shot pattern dominates
   the rubric semantics — the model cargo-cults the demonstrations rather than
   reasoning about expected value.
3. **Qualitative QP4/QP7 underperform QP1 on Qwen 9B.** Both `fired-if-wrong`
   (QP4, 25.0% best) and `humanity-extinction` (QP7, 22.1% best) trail QP1
   (`ultra_cautious`, 27.9% best) on Qwen 9B despite stronger consequence
   language — Qwen reads QP1's terse "catastrophic consequences" framing as
   higher signal than QP7's vivid "wipes out humanity". Gemma 31B is roughly
   indifferent across QP1/QP4/QP7 (peak 14.5–20.0%).
4. **Instruct tuning ≫ any prompting trick.** Across all four 9B/31B base ×
   instruct pairs, instruction tuning lifts QP1 `acc-attempted` by
   +30 to +67 points and roughly nullifies the cautious-prompt abstain
   behavior (Qwen 9B-it abstains 1/107, Gemma 31B-it abstains 1/98). No
   combination of rubric × few-shot framing recovers more than a few points
   of this gap on the base model. The full 9-rubric instruct sweeps on
   gemma-4-31b-it and qwen3.5-9b-it both stay in tight ~8pt bands
   (**75.0–83.3%** and **77.9–86.7%** respectively) — i.e. the rubric framing
   moves accuracy by at most ~9pt for the instruct model vs the 0–28% spread
   on the base model.
6. **Instruct vs base abstention is calibrated in opposite directions.**
   On gemma-4-31b-it the rare abstentions (0–4 per 100) actually *lift*
   `acc-attempted` (peak 83.3% on `(−1,−10,+10)`, with 4 abstentions),
   meaning the instruct model abstains on its hardest items. The base
   model under `conseq_correct_abstain` few-shot does the opposite —
   abstaining most on problems it would have answered correctly.
5. **Original takeaways still hold.** Few-shot teaches output *format*, not
   *math*; abstention rate is steerable but calibration is not; Qwen base
   pretraining is markedly more math-formatted than Gemma's at every scale
   (Qwen 0.8B base ≈ Gemma E4B base on `acc-attempted`; Qwen 9B base
   substantially exceeds Gemma 31B base across all 40 rubric × framing cells).
