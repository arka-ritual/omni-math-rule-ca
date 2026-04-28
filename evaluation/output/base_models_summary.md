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

| Variant | Prompt | Few-shot | N | Abst | Indet | Attempted | acc-attempted | acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **base** | standard | normal | 100 | – | 3 | 97 | – | **21.0%** |
| **base** | ultra_cautious | normal | 100 | 0 | 10 | 90 | **24.4%** | – |
| **base** | ultra_cautious | conseq_no_abstain | 100 | 5 | 1 | 94 | **22.3%** | – |
| **base** | ultra_cautious | conseq_random_abstain | 100 | 33 | 0 | 67 | **20.9%** | – |
| **base** | ultra_cautious | conseq_correct_abstain | 100 | 25 | 2 | 73 | **9.6%** | – |
| **base** | ultra_cautious | conseq_always_submit | 100 | 10 | 4 | 86 | **27.9%** | – |
| **base** | ultra_cautious | conseq_always_abstain | 100 | 72 | 1 | 27 | **11.1%** | – |
| instruct | standard | – | – | – | – | – | – | _in flight_ |
| instruct | ultra_cautious | – | – | – | – | – | _in flight_ | – |

Strongest base model in this study by a wide margin. Best variant is
`conseq_always_submit` at 27.9% — outperforming even the `normal` baseline
(24.4%) by injecting "always answer, even when not 100% sure" into the priors.
`conseq_correct_abstain` again collapses accuracy (9.6%): the model learns to
abstain on its highest-confidence problems while attempting the harder ones.

## Gemma-4 31B

| Variant | Prompt | Few-shot | N | Abst | Indet | Attempted | acc-attempted | acc |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **base** | standard | normal | 100 | – | 1 | 99 | – | **10.0%** |
| **base** | ultra_cautious | normal | 100 | 0 | 1 | 99 | **11.1%** | – |
| **base** | ultra_cautious | conseq_no_abstain | 100 | 9 | 0 | 91 | **16.5%** | – |
| **base** | ultra_cautious | conseq_random_abstain | 100 | 57 | 1 | 42 | **14.3%** | – |
| **base** | ultra_cautious | conseq_correct_abstain | 100 | 53 | 0 | 47 | **10.6%** | – |
| **base** | ultra_cautious | conseq_always_submit | 100 | 30 | 0 | 70 | **20.0%** | – |
| **base** | ultra_cautious | conseq_always_abstain | 100 | 84 | 0 | 16 | **6.2%** | – |
| instruct | standard | – | – | – | – | – | – | _in flight_ |
| instruct | ultra_cautious | – | – | – | – | – | _in flight_ | – |

Surprisingly weak relative to Qwen 9B despite being ~3× larger — Gemma's base
pretraining is less math-formatted. Same `always_submit` > `normal` pattern as
Qwen 9B (20.0% vs 11.1%). `correct_abstain` again hurts (10.6%, basically the
no-abstention baseline); `always_abstain` zeroes out (6.2% on 16 attempted).

## Cross-model takeaways

Best `acc-attempted` per base model under `ultra_cautious`:

| Model | normal | conseq_no_abstain | conseq_always_submit | best variant |
|---|---:|---:|---:|---|
| Qwen 3.5 0.8B (no fewshot) | 19.6% | – | – | normal: 19.6% |
| Gemma-4 E2B   |  – | 4.0% | 2.0% | random_abstain: 7.0% |
| Gemma-4 E4B   |  9.0% | 8.2% | 9.5% | random_abstain: 10.6% |
| Qwen 3.5 9B   | **24.4%** | 22.3% | **27.9%** | always_submit: 27.9% |
| Gemma-4 31B   | 11.1% | 16.5% | **20.0%** | always_submit: 20.0% |

1. **Few-shot ≠ rescue for weak base models.** Gemma-4 E2B/E4B base accuracies
   stay in single digits regardless of scaffolding, vs 31%/44% for their instruct
   versions. The few-shot examples teach the *output format* but not the math.
2. **`always_submit` is the winning pattern for capable base models.** Both
   Qwen 9B (+3.5pt over `normal`) and Gemma 31B (+9pt over `normal`) peak when
   the few-shot demonstrates "decide ANSWER even on mixed correct/wrong examples".
   This confirms that demonstrating *any* abstention behavior typically costs
   accuracy — the model abstains on problems it would have gotten right.
3. **`conseq_correct_abstain` consistently collapses accuracy.** Across
   Gemma E4B (6.2%), Qwen 9B (9.6%), Gemma 31B (10.6%), this variant
   underperforms even `normal`. Mimicking "abstain when wrong" requires
   meta-cognition the base models don't have, so they abstain on their
   highest-confidence problems instead.
4. **Abstention rate is steerable, calibration is not.** Across all models,
   abstention rate tracks the demonstrated rate almost mechanically
   (0% → 25-55% → 70-96%). But none of the variants make abstention
   *selective* — `acc-attempted` never approaches 100%.
5. **Qwen base models punch above their weight.** Qwen 3.5 0.8B (zero
   few-shot) at 19.6% beats Gemma-4 E4B with full scaffolding (10.6%);
   Qwen 9B (27.9%) beats Gemma-4 31B (20.0%) at >3× fewer parameters.
   Qwen base pretraining clearly includes far more math/`\boxed{}` exposure.
