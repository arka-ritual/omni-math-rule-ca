# GPT-5.4 Nano: original abstention paired with Int2 confidence

## Design

The outcome is the abstention decision from the original simultaneous-consequence sweep. The confidence proxy comes from a separate Intervention 2 rollout of the same model, setting, and Omni-MATH problem. In Intervention 2, the answer and confidence were generated before consequences were revealed. No new model inference was performed.

This design prevents confidence elicitation from causing the baseline decision and supplies a confidence value even when the baseline rollout abstained. However, the confidence belongs to the independently generated Int2 candidate, not necessarily to the exact baseline candidate. It should therefore be described as a pre-consequence, cross-rollout confidence proxy.

The primary proxy is the setting-matched Int2 confidence. As a sensitivity analysis, `question_mean` averages the available consequence-blind Int2 confidence reports across the four settings for each problem. This reduces single-draw noise but is even more explicitly a problem-level proxy.

## Key findings

- The setting-matched analysis contains **398** matched rows and **21** baseline abstentions.
- Pooled Spearman ρ between the proxy and baseline abstention is **-0.103** [-0.219, 0.014]. Negative values mean lower Int2 confidence is associated with more baseline abstention.
- In a setting-adjusted linear-logit model, the odds ratio for baseline abstention per 10-point increase in confidence is **0.832** [0.646, 1.008].
- Because there are only 21 baseline abstentions, condition-specific and confidence-adjusted severity estimates are imprecise and should be presented with their intervals rather than as definitive null effects.

## Join coverage

| Setting | Baseline N | Int2 N | Joined N | Confidence N | Baseline-only idx | Int2-only idx |
| --- | --- | --- | --- | --- | --- | --- |
| Quant-25 | 100 | 100 | 100 | 100 | — | — |
| Quant-100 | 100 | 99 | 99 | 99 | 2115 | — |
| QP6 | 99 | 100 | 99 | 99 | — | 1671 |
| QP7 | 100 | 100 | 100 | 100 | — | — |

## Baseline decisions and cross-rollout confidence

| Setting | N | Baseline abstained | Abstention rate | Mean confidence: abstained | Mean confidence: submitted | Abstained−submitted |
| --- | --- | --- | --- | --- | --- | --- |
| Quant-25 | 100 | 3 | 3.0% | 40.0% | 53.8% | -13.8% |
| Quant-100 | 99 | 4 | 4.0% | 12.5% | 54.7% | -42.2% |
| QP6 | 99 | 11 | 11.1% | 49.3% | 59.4% | -10.1% |
| QP7 | 100 | 3 | 3.0% | 45.0% | 52.8% | -7.8% |

## Confidence–baseline-abstention association

`lower_confidence_auc` is the probability that a randomly chosen baseline-abstained problem has lower proxy confidence than a randomly chosen submitted problem, with ties receiving half credit.

| Proxy | Setting | N | Abstentions | Spearman ρ | 95% CI | Lower-confidence AUC | 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| setting_matched | Quant-25 | 100 | 3 | -0.057 | [-0.240, 0.184] | 0.596 | [0.111, 0.894] |
| setting_matched | Quant-100 | 99 | 4 | -0.264 | [-0.381, -0.122] | 0.886 | [0.792, 0.979] |
| setting_matched | QP6 | 99 | 11 | -0.118 | [-0.302, 0.093] | 0.608 | [0.414, 0.788] |
| setting_matched | QP7 | 100 | 3 | -0.023 | [-0.227, 0.231] | 0.540 | [0.030, 0.889] |
| setting_matched | Pooled | 398 | 21 | -0.103 | [-0.219, 0.014] | 0.632 | [0.482, 0.791] |
| question_mean | Quant-25 | 100 | 3 | -0.074 | [-0.219, 0.100] | 0.625 | [0.265, 0.847] |
| question_mean | Quant-100 | 100 | 4 | -0.094 | [-0.244, 0.078] | 0.638 | [0.333, 0.893] |
| question_mean | QP6 | 99 | 11 | -0.250 | [-0.392, -0.082] | 0.729 | [0.581, 0.852] |
| question_mean | QP7 | 100 | 3 | -0.098 | [-0.262, 0.106] | 0.667 | [0.253, 0.929] |
| question_mean | Pooled | 399 | 21 | -0.141 | [-0.263, -0.000] | 0.683 | [0.500, 0.837] |

## Confidence-adjusted consequence contrasts

Positive differences mean more baseline abstention under Quant-100 than Quant-25, or under QP7 than QP6, at the same proxy-confidence distribution.
The quantitative pair changes a cardinal penalty magnitude. QP6 and QP7 are different qualitative scenarios, so their contrast is a consequence-setting comparison—not an estimate of a one-dimensional severity dose response.

| Proxy | Contrast | Common-support N | Adjusted Δ abstention | 95% cluster-bootstrap CI | Bootstrap p |
| --- | --- | --- | --- | --- | --- |
| setting_matched | Quant-100 − Quant-25 | 198 | 1.0% | [-2.0%, 4.5%] | 0.490 |
| setting_matched | QP7 − QP6 | 198 | -8.7% | [-15.1%, -4.0%] | 0.001 |
| question_mean | Quant-100 − Quant-25 | 200 | 1.0% | [-2.1%, 4.9%] | 0.759 |
| question_mean | QP7 − QP6 | 199 | -8.1% | [-13.6%, -3.2%] | 0.001 |

## Original versus Int2 rollout behavior

| Setting | Joined N | Original abstained | Int2 abstained | Int2−original |
| --- | --- | --- | --- | --- |
| Quant-25 | 100 | 3 (3.0%) | 82 (82.0%) | 79.0% |
| Quant-100 | 99 | 4 (4.0%) | 76 (76.8%) | 72.7% |
| QP6 | 99 | 11 (11.1%) | 90 (90.9%) | 79.8% |
| QP7 | 100 | 3 (3.0%) | 87 (87.0%) | 84.0% |

The large differences above are why Int2 abstention should not be substituted for the original outcome when answering the reviewer's question.

## Quantitative proxy decision adherence

These calculations treat Int2 confidence as if it were the belief governing the original quantitative decision. Because it is cross-rollout confidence, this is a diagnostic proxy rather than literal decision-theoretic compliance.

| Setting | Threshold | N | Proxy says abstain | Original under-abstained | Under-abstention rate | Agreement |
| --- | --- | --- | --- | --- | --- | --- |
| Quant-25 | 96.2% | 100 | 95 | 92/95 | 96.8% | 8.0% |
| Quant-100 | 99.0% | 99 | 99 | 95/99 | 96.0% | 4.0% |

## Files

- `baseline_int2_confidence_raw.csv`: all 399 original baseline rows, including the unmatched Quant-100 row.
- `join_audit.csv`: exact overlap and missing problem IDs.
- `proxy_summaries.csv` and `confidence_baseline_abstention_correlations.csv`: setting-matched and question-mean results.
- `absolute_confidence_bins.csv` and `percentile_confidence_bins.csv`: requested binned views for the primary setting-matched proxy.
- `confidence_adjusted_contrasts.csv`: consequence-setting contrasts for both proxies.
- `plots/`: PNG and PDF figures.
