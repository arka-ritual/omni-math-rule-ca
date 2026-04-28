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

## Cross-model takeaways

1. **Few-shot ≠ rescue for weak base models.** Gemma-4 E2B/E4B base accuracies
   stay in single digits regardless of scaffolding, vs 31%/44% for their instruct
   versions. The few-shot examples teach the *output format* but not the math.
2. **Abstention rate is steerable in base models.** It tracks the demonstrated
   abstain rate (0% → 50% → 95%) almost mechanically across variants.
3. **Steering abstention does not improve calibration.** Even
   `conseq_correct_abstain` (which models a perfect abstain-when-wrong policy)
   does not push `acc-attempted` above the no-abstain baseline.
4. **Qwen 3.5 0.8B is the outlier.** It's a base model that already produces
   `\boxed{}` answers without few-shot and even outperforms its instruct sibling
   on `acc-attempted` under `ultra_cautious` — likely because the Qwen base
   pretraining already includes substantial math-format exposure.
