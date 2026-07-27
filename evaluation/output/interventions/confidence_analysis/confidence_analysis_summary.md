# Omni-MATH verbalized confidence and abstention analysis

## Key findings

- In the primary multi-turn analysis, all **20** model-by-setting correlations were negative; Spearman ρ ranged from **-0.764** to **-0.298**. Every problem-bootstrap interval was below zero.
- Submitted multi-turn answers remained highly confident: cell-level mean confidence ranged from **75.8%** to **100.0%**, with a median confidence−accuracy gap of **5.4%**.
- Because multi-turn confidence was elicited before consequences were shown, it should not move systematically with quantitative severity. Paired Quant-100−Quant-25 mean shifts ranged from **-1.4%** to **1.8%**; all five intervals included zero.
- After adjusting for verbalized confidence, all five multi-turn Quant-100−Quant-25 abstention intervals included zero. This is the direct aggregate test of whether higher stated stakes changed abstention beyond confidence.
- The narrow confidence band where Quant-25 normatively favors submission but Quant-100 favors abstention is reported separately below. Those estimates are descriptive and often based on small samples; they should qualify, rather than replace, the adjusted aggregate analysis.

## Interpretation guide

Intervention 2 is the primary analysis because confidence was elicited before the consequence setting was revealed. Intervention 1 is supporting evidence: its confidence and decision were produced with consequences already visible. Intervention 1 confidence is reparsed directly from its completion, with the stored Intervention 4 extraction retained only as an audit field. Intervention 4 decisions are not used as outcomes.

A negative confidence–abstention correlation means lower-confidence answers are more likely to be withheld. This alone does not establish consequence sensitivity. The adjusted setting contrasts ask whether abstention changes between consequence settings after controlling for reported confidence. Positive values mean more abstention in Quant-100 than Quant-25, or in QP7 than QP6. QP7−QP6 is a content contrast rather than a cardinal severity scale.

Adjusted contrasts use a working-independence logistic GEE mean model with a three-degree-of-freedom confidence spline, a weak ridge penalty for quasi-separation, and problem-cluster bootstrap uncertainty.

## Rebuttal assessment

This is substantially stronger than reporting unadjusted abstention rates. The confidence–abstention curves establish that confidence affects the decision, while the adjusted setting contrasts test the reviewer's distinct hypothesis: whether consequence severity changes abstention among answers with comparable verbalized confidence. The multi-turn protocol is the cleanest version because confidence is recorded before consequences appear.

The evidence should nevertheless be stated narrowly. Verbal confidence is a noisy, potentially strategically reported proxy for the model's latent belief; observational adjustment cannot prove the absence of internal consequence awareness. QP6 and QP7 are different qualitative scenarios, not points on a validated cardinal severity scale. Finally, the switch-band results show that an aggregate null can coexist with model-specific sensitivity: DeepSeek changes sharply in that small multi-turn subset, while Qwen changes in the same direction with wider uncertainty. The defensible claim is therefore limited aggregate consequence sensitivity conditional on verbal confidence, alongside clear overconfidence/under-abstention—not universal consequence blindness.

## Answer grading

Accuracy is graded on the candidate answer to which the confidence refers. For Intervention 1 this is the final committed `ANSWER:` field after any reasoning delimiter; for Intervention 2 it is `predicted_answer_turn1`. Each candidate is normalized with the repository's `strip_string` routine and compared to the Omni-MATH ground truth with its symbolic `math_equal` grader. The analysis applies a 10-second hard limit per unique pair instead of the evaluator's load-sensitive one-second nested symbolic limit; the equivalence rules are unchanged and a timeout remains an ordinary non-match. Missing candidate parses remain missing. Final post-consequence answers are not substituted for these candidates.

## Data and parsing coverage

The raw export contains **3,987** observations; **3,894** have a parsed confidence and a determinate decision.

| Model | Method | Rows | Confidence parsed | Parse coverage | Candidate gradeable | Grade coverage |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Int1 | 400 | 383 | 95.8% | 382 | 95.5% |
| Claude Haiku 4.5 | Int2 | 400 | 400 | 100.0% | 387 | 96.8% |
| DeepSeek V4 Pro | Int1 | 399 | 365 | 91.5% | 350 | 87.7% |
| DeepSeek V4 Pro | Int2 | 396 | 392 | 99.0% | 364 | 91.9% |
| Gemini 3.1 Flash Lite | Int1 | 400 | 400 | 100.0% | 393 | 98.2% |
| Gemini 3.1 Flash Lite | Int2 | 400 | 400 | 100.0% | 398 | 99.5% |
| GPT-5.4 Nano | Int1 | 398 | 386 | 97.0% | 340 | 85.4% |
| GPT-5.4 Nano | Int2 | 399 | 399 | 100.0% | 398 | 99.7% |
| Qwen3.5-397B | Int1 | 400 | 386 | 96.5% | 377 | 94.2% |
| Qwen3.5-397B | Int2 | 395 | 387 | 98.0% | 368 | 93.2% |

## Confidence–abstention correlations

| Model | Method | Setting | N | Spearman ρ | 95% bootstrap CI |
| --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Int1 | Quant-25 | 96 | -0.566 | [-0.680, -0.424] |
| Claude Haiku 4.5 | Int1 | Quant-100 | 97 | -0.560 | [-0.699, -0.383] |
| Claude Haiku 4.5 | Int1 | QP6 | 96 | -0.705 | [-0.787, -0.601] |
| Claude Haiku 4.5 | Int1 | QP7 | 94 | -0.566 | [-0.674, -0.429] |
| Claude Haiku 4.5 | Int2 | Quant-25 | 100 | -0.563 | [-0.697, -0.414] |
| Claude Haiku 4.5 | Int2 | Quant-100 | 100 | -0.668 | [-0.777, -0.539] |
| Claude Haiku 4.5 | Int2 | QP6 | 100 | -0.601 | [-0.711, -0.473] |
| Claude Haiku 4.5 | Int2 | QP7 | 100 | -0.647 | [-0.747, -0.530] |
| DeepSeek V4 Pro | Int1 | Quant-25 | 93 | -0.449 | [-0.598, -0.215] |
| DeepSeek V4 Pro | Int1 | Quant-100 | 89 | -0.432 | [-0.609, -0.220] |
| DeepSeek V4 Pro | Int1 | QP6 | 91 | 0.063 | [0.052, 0.124] |
| DeepSeek V4 Pro | Int1 | QP7 | 92 | -0.436 | [-0.574, -0.257] |
| DeepSeek V4 Pro | Int2 | Quant-25 | 98 | -0.619 | [-0.806, -0.370] |
| DeepSeek V4 Pro | Int2 | Quant-100 | 98 | -0.752 | [-0.901, -0.547] |
| DeepSeek V4 Pro | Int2 | QP6 | 98 | -0.697 | [-0.889, -0.441] |
| DeepSeek V4 Pro | Int2 | QP7 | 94 | -0.764 | [-0.904, -0.563] |
| Gemini 3.1 Flash Lite | Int1 | Quant-25 | 100 | -0.610 | [-0.734, -0.461] |
| Gemini 3.1 Flash Lite | Int1 | Quant-100 | 100 | -0.589 | [-0.694, -0.449] |
| Gemini 3.1 Flash Lite | Int1 | QP6 | 100 | -0.403 | [-0.558, -0.207] |
| Gemini 3.1 Flash Lite | Int1 | QP7 | 100 | -0.332 | [-0.487, -0.191] |
| Gemini 3.1 Flash Lite | Int2 | Quant-25 | 100 | -0.608 | [-0.752, -0.438] |
| Gemini 3.1 Flash Lite | Int2 | Quant-100 | 100 | -0.385 | [-0.569, -0.191] |
| Gemini 3.1 Flash Lite | Int2 | QP6 | 100 | -0.574 | [-0.747, -0.372] |
| Gemini 3.1 Flash Lite | Int2 | QP7 | 100 | -0.524 | [-0.700, -0.311] |
| GPT-5.4 Nano | Int1 | Quant-25 | 100 | -0.451 | [-0.600, -0.277] |
| GPT-5.4 Nano | Int1 | Quant-100 | 97 | -0.434 | [-0.581, -0.257] |
| GPT-5.4 Nano | Int1 | QP6 | 94 | -0.463 | [-0.616, -0.285] |
| GPT-5.4 Nano | Int1 | QP7 | 95 | -0.551 | [-0.661, -0.407] |
| GPT-5.4 Nano | Int2 | Quant-25 | 100 | -0.556 | [-0.669, -0.421] |
| GPT-5.4 Nano | Int2 | Quant-100 | 99 | -0.561 | [-0.673, -0.423] |
| GPT-5.4 Nano | Int2 | QP6 | 100 | -0.298 | [-0.463, -0.082] |
| GPT-5.4 Nano | Int2 | QP7 | 100 | -0.337 | [-0.499, -0.146] |
| Qwen3.5-397B | Int1 | Quant-25 | 94 | -0.372 | [-0.514, -0.189] |
| Qwen3.5-397B | Int1 | Quant-100 | 100 | -0.409 | [-0.546, -0.237] |
| Qwen3.5-397B | Int1 | QP6 | 98 | -0.271 | [-0.436, -0.187] |
| Qwen3.5-397B | Int1 | QP7 | 94 | -0.283 | [-0.444, -0.194] |
| Qwen3.5-397B | Int2 | Quant-25 | 99 | -0.644 | [-0.790, -0.463] |
| Qwen3.5-397B | Int2 | Quant-100 | 99 | -0.573 | [-0.763, -0.366] |
| Qwen3.5-397B | Int2 | QP6 | 97 | -0.628 | [-0.802, -0.401] |
| Qwen3.5-397B | Int2 | QP7 | 92 | -0.664 | [-0.828, -0.454] |

## Confidence of submitted answers and candidate accuracy

The calibration target is the candidate answer that received the confidence score, not a potentially revised final response. Rows with an unparsed candidate are omitted, so the table's N is the number of graded submissions.

| Model | Method | Setting | N graded submissions | Mean confidence | Candidate accuracy | Confidence−accuracy | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Int1 | Quant-25 | 75 | 84.6% | 66.7% | 17.9% | 0.203 |
| Claude Haiku 4.5 | Int1 | Quant-100 | 72 | 84.0% | 70.8% | 13.1% | 0.150 |
| Claude Haiku 4.5 | Int1 | QP6 | 72 | 88.1% | 73.6% | 14.5% | 0.228 |
| Claude Haiku 4.5 | Int1 | QP7 | 79 | 83.7% | 64.6% | 19.2% | 0.214 |
| Claude Haiku 4.5 | Int2 | Quant-25 | 61 | 85.8% | 82.0% | 3.8% | 0.124 |
| Claude Haiku 4.5 | Int2 | Quant-100 | 60 | 88.8% | 80.0% | 8.8% | 0.131 |
| Claude Haiku 4.5 | Int2 | QP6 | 67 | 86.4% | 80.6% | 5.8% | 0.127 |
| Claude Haiku 4.5 | Int2 | QP7 | 68 | 89.7% | 77.9% | 11.8% | 0.133 |
| DeepSeek V4 Pro | Int1 | Quant-25 | 85 | 99.6% | 91.8% | 7.8% | 0.082 |
| DeepSeek V4 Pro | Int1 | Quant-100 | 82 | 99.8% | 96.3% | 3.4% | 0.037 |
| DeepSeek V4 Pro | Int1 | QP6 | 89 | 99.5% | 94.4% | 5.2% | 0.055 |
| DeepSeek V4 Pro | Int1 | QP7 | 81 | 99.6% | 93.8% | 5.8% | 0.061 |
| DeepSeek V4 Pro | Int2 | Quant-25 | 87 | 99.9% | 92.0% | 7.9% | 0.080 |
| DeepSeek V4 Pro | Int2 | Quant-100 | 80 | 100.0% | 95.0% | 5.0% | 0.050 |
| DeepSeek V4 Pro | Int2 | QP6 | 85 | 99.9% | 95.3% | 4.6% | 0.047 |
| DeepSeek V4 Pro | Int2 | QP7 | 79 | 99.9% | 96.2% | 3.7% | 0.038 |
| Gemini 3.1 Flash Lite | Int1 | Quant-25 | 79 | 96.3% | 69.6% | 26.7% | 0.253 |
| Gemini 3.1 Flash Lite | Int1 | Quant-100 | 84 | 96.4% | 66.7% | 29.8% | 0.285 |
| Gemini 3.1 Flash Lite | Int1 | QP6 | 95 | 98.1% | 60.0% | 38.1% | 0.369 |
| Gemini 3.1 Flash Lite | Int1 | QP7 | 97 | 97.2% | 58.8% | 38.4% | 0.367 |
| Gemini 3.1 Flash Lite | Int2 | Quant-25 | 68 | 99.7% | 79.4% | 20.3% | 0.203 |
| Gemini 3.1 Flash Lite | Int2 | Quant-100 | 68 | 98.7% | 76.5% | 22.2% | 0.217 |
| Gemini 3.1 Flash Lite | Int2 | QP6 | 80 | 98.1% | 75.0% | 23.1% | 0.244 |
| Gemini 3.1 Flash Lite | Int2 | QP7 | 87 | 98.3% | 69.0% | 29.4% | 0.286 |
| GPT-5.4 Nano | Int1 | Quant-25 | 42 | 82.7% | 64.3% | 18.4% | 0.177 |
| GPT-5.4 Nano | Int1 | Quant-100 | 40 | 85.0% | 77.5% | 7.5% | 0.121 |
| GPT-5.4 Nano | Int1 | QP6 | 55 | 84.9% | 69.1% | 15.9% | 0.176 |
| GPT-5.4 Nano | Int1 | QP7 | 61 | 83.5% | 68.9% | 14.6% | 0.190 |
| GPT-5.4 Nano | Int2 | Quant-25 | 18 | 87.1% | 83.3% | 3.7% | 0.126 |
| GPT-5.4 Nano | Int2 | Quant-100 | 23 | 82.7% | 65.2% | 17.5% | 0.229 |
| GPT-5.4 Nano | Int2 | QP6 | 9 | 83.6% | 100.0% | -16.4% | 0.074 |
| GPT-5.4 Nano | Int2 | QP7 | 13 | 75.8% | 84.6% | -8.8% | 0.062 |
| Qwen3.5-397B | Int1 | Quant-25 | 89 | 98.2% | 85.4% | 12.8% | 0.131 |
| Qwen3.5-397B | Int1 | Quant-100 | 93 | 98.1% | 87.1% | 11.0% | 0.120 |
| Qwen3.5-397B | Int1 | QP6 | 93 | 98.2% | 91.4% | 6.8% | 0.067 |
| Qwen3.5-397B | Int1 | QP7 | 91 | 98.8% | 83.5% | 15.3% | 0.152 |
| Qwen3.5-397B | Int2 | Quant-25 | 73 | 98.6% | 94.5% | 4.1% | 0.042 |
| Qwen3.5-397B | Int2 | Quant-100 | 77 | 97.3% | 93.5% | 3.8% | 0.086 |
| Qwen3.5-397B | Int2 | QP6 | 78 | 97.7% | 93.6% | 4.1% | 0.082 |
| Qwen3.5-397B | Int2 | QP7 | 76 | 98.7% | 92.1% | 6.6% | 0.086 |

## Confidence-adjusted consequence contrasts

| Model | Method | Contrast | Common-support N | Adjusted Δ abstention | 95% cluster-bootstrap CI | Int2 BH q |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Int1 | Quant-100 − Quant-25 | 192 | -0.3% | [-8.4%, 8.4%] | exploratory |
| Claude Haiku 4.5 | Int1 | QP7 − QP6 | 189 | -8.5% | [-15.3%, -2.7%] | exploratory |
| Claude Haiku 4.5 | Int2 | Quant-100 − Quant-25 | 198 | 0.1% | [-8.7%, 9.3%] | 0.970 |
| Claude Haiku 4.5 | Int2 | QP7 − QP6 | 199 | 0.3% | [-9.4%, 10.0%] | 0.970 |
| DeepSeek V4 Pro | Int1 | Quant-100 − Quant-25 | 182 | -1.7% | [-4.6%, 0.3%] | exploratory |
| DeepSeek V4 Pro | Int1 | QP7 − QP6 | 180 | 7.0% | [2.5%, 12.3%] | exploratory |
| DeepSeek V4 Pro | Int2 | Quant-100 − Quant-25 | 196 | 5.7% | [-3.0%, 13.7%] | 0.637 |
| DeepSeek V4 Pro | Int2 | QP7 − QP6 | 192 | 2.6% | [-4.4%, 9.9%] | 0.818 |
| Gemini 3.1 Flash Lite | Int1 | Quant-100 − Quant-25 | 199 | -3.7% | [-12.0%, 5.4%] | exploratory |
| Gemini 3.1 Flash Lite | Int1 | QP7 − QP6 | 198 | -1.9% | [-5.1%, 0.5%] | exploratory |
| Gemini 3.1 Flash Lite | Int2 | Quant-100 − Quant-25 | 198 | 0.8% | [-9.7%, 10.2%] | 0.970 |
| Gemini 3.1 Flash Lite | Int2 | QP7 − QP6 | 199 | -5.7% | [-13.9%, 3.4%] | 0.637 |
| GPT-5.4 Nano | Int1 | Quant-100 − Quant-25 | 196 | -3.8% | [-15.4%, 7.8%] | exploratory |
| GPT-5.4 Nano | Int1 | QP7 − QP6 | 188 | -9.5% | [-20.0%, 1.1%] | exploratory |
| GPT-5.4 Nano | Int2 | Quant-100 − Quant-25 | 198 | -4.0% | [-11.7%, 4.4%] | 0.670 |
| GPT-5.4 Nano | Int2 | QP7 − QP6 | 199 | -6.5% | [-12.8%, -0.2%] | 0.430 |
| Qwen3.5-397B | Int1 | Quant-100 − Quant-25 | 194 | 2.6% | [-0.0%, 5.4%] | exploratory |
| Qwen3.5-397B | Int1 | QP7 − QP6 | 192 | 0.1% | [-1.0%, 2.5%] | exploratory |
| Qwen3.5-397B | Int2 | Quant-100 − Quant-25 | 198 | 4.1% | [-2.8%, 10.6%] | 0.637 |
| Qwen3.5-397B | Int2 | QP7 − QP6 | 189 | -1.0% | [-7.7%, 6.1%] | 0.970 |

## Consequence setting and verbalized confidence

These paired contrasts use matched problem IDs. In Intervention 2, confidence was elicited before the consequence setting was revealed; consequently these comparisons are a manipulation check for accidental confidence drift rather than evidence that the model encoded the hidden consequence.

| Model | Method | Contrast | N paired | Mean Δ confidence | Median Δ | 95% problem-bootstrap CI |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Int1 | Quant-100 − Quant-25 | 94 | -1.7% | 0.0% | [-4.4%, 1.0%] |
| Claude Haiku 4.5 | Int1 | QP7 − QP6 | 90 | 1.0% | 0.0% | [-1.8%, 3.9%] |
| Claude Haiku 4.5 | Int2 | Quant-100 − Quant-25 | 100 | -1.4% | 0.0% | [-7.2%, 4.1%] |
| Claude Haiku 4.5 | Int2 | QP7 − QP6 | 100 | 4.1% | 0.0% | [-1.1%, 9.2%] |
| DeepSeek V4 Pro | Int1 | Quant-100 − Quant-25 | 88 | 0.2% | 0.0% | [-0.3%, 0.7%] |
| DeepSeek V4 Pro | Int1 | QP7 − QP6 | 90 | -1.7% | 0.0% | [-4.3%, -0.1%] |
| DeepSeek V4 Pro | Int2 | Quant-100 − Quant-25 | 96 | 1.8% | 0.0% | [-3.1%, 6.8%] |
| DeepSeek V4 Pro | Int2 | QP7 − QP6 | 92 | 0.9% | 0.0% | [-2.4%, 4.4%] |
| Gemini 3.1 Flash Lite | Int1 | Quant-100 − Quant-25 | 100 | -0.1% | 0.0% | [-3.8%, 3.2%] |
| Gemini 3.1 Flash Lite | Int1 | QP7 − QP6 | 100 | 0.0% | 0.0% | [-1.9%, 2.6%] |
| Gemini 3.1 Flash Lite | Int2 | Quant-100 − Quant-25 | 100 | -0.3% | 0.0% | [-5.2%, 4.4%] |
| Gemini 3.1 Flash Lite | Int2 | QP7 − QP6 | 100 | 2.8% | 0.0% | [-1.0%, 7.0%] |
| GPT-5.4 Nano | Int1 | Quant-100 − Quant-25 | 97 | -1.9% | 0.0% | [-6.4%, 2.6%] |
| GPT-5.4 Nano | Int1 | QP7 − QP6 | 91 | -0.8% | 0.0% | [-5.7%, 4.5%] |
| GPT-5.4 Nano | Int2 | Quant-100 − Quant-25 | 99 | -0.2% | 0.0% | [-6.5%, 5.7%] |
| GPT-5.4 Nano | Int2 | QP7 − QP6 | 100 | -5.6% | -2.5% | [-10.4%, -1.2%] |
| Qwen3.5-397B | Int1 | Quant-100 − Quant-25 | 94 | 1.1% | 0.5% | [-1.2%, 3.9%] |
| Qwen3.5-397B | Int1 | QP7 − QP6 | 92 | 0.3% | 0.0% | [-1.4%, 2.0%] |
| Qwen3.5-397B | Int2 | Quant-100 − Quant-25 | 98 | 0.4% | 0.0% | [-4.1%, 5.2%] |
| Qwen3.5-397B | Int2 | QP7 − QP6 | 90 | -3.8% | 0.0% | [-9.8%, 1.5%] |

## Quantitative decision-rule adherence

For a risk-neutral decision-maker with calibrated confidence, the submission thresholds are 25/26 (Quant-25) and 100/101 (Quant-100). Under-abstention is submission below the corresponding threshold.

| Model | Method | Setting | N | Decision agreement | Under-abstain count | Under-abstain rate |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Int1 | Quant-25 | 96 | 35.4% | 62/83 | 74.7% |
| Claude Haiku 4.5 | Int1 | Quant-100 | 97 | 25.8% | 72/97 | 74.2% |
| Claude Haiku 4.5 | Int2 | Quant-25 | 100 | 67.0% | 33/70 | 47.1% |
| Claude Haiku 4.5 | Int2 | Quant-100 | 100 | 39.0% | 61/99 | 61.6% |
| DeepSeek V4 Pro | Int1 | Quant-25 | 93 | 98.9% | 1/6 | 16.7% |
| DeepSeek V4 Pro | Int1 | Quant-100 | 89 | 91.0% | 8/12 | 66.7% |
| DeepSeek V4 Pro | Int2 | Quant-25 | 98 | 98.0% | 0/9 | 0.0% |
| DeepSeek V4 Pro | Int2 | Quant-100 | 98 | 92.9% | 3/17 | 17.6% |
| Gemini 3.1 Flash Lite | Int1 | Quant-25 | 100 | 65.0% | 34/54 | 63.0% |
| Gemini 3.1 Flash Lite | Int1 | Quant-100 | 100 | 61.0% | 39/54 | 72.2% |
| Gemini 3.1 Flash Lite | Int2 | Quant-25 | 100 | 83.0% | 4/23 | 17.4% |
| Gemini 3.1 Flash Lite | Int2 | Quant-100 | 100 | 75.0% | 8/23 | 34.8% |
| GPT-5.4 Nano | Int1 | Quant-25 | 100 | 64.0% | 35/90 | 38.9% |
| GPT-5.4 Nano | Int1 | Quant-100 | 97 | 52.6% | 46/97 | 47.4% |
| GPT-5.4 Nano | Int2 | Quant-25 | 100 | 87.0% | 13/95 | 13.7% |
| GPT-5.4 Nano | Int2 | Quant-100 | 99 | 76.8% | 23/99 | 23.2% |
| Qwen3.5-397B | Int1 | Quant-25 | 94 | 84.0% | 15/19 | 78.9% |
| Qwen3.5-397B | Int1 | Quant-100 | 100 | 63.0% | 37/43 | 86.0% |
| Qwen3.5-397B | Int2 | Quant-25 | 99 | 89.9% | 8/24 | 33.3% |
| Qwen3.5-397B | Int2 | Quant-100 | 99 | 85.9% | 11/25 | 44.0% |

## Quantitative normative switch band

The switch band is [25/26, 100/101): a calibrated, risk-neutral agent should submit under Quant-25 and abstain under Quant-100. The interval shown is a conservative difference interval formed from the two Wilson intervals; Fisher's exact p-value is descriptive and is not multiplicity-adjusted.

| Model | Method | Quant-25 abstain | Quant-100 abstain | Δ abstention | Conservative 95% CI | Fisher p |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Int1 | 0/13 (0.0%) | 1/17 (5.9%) | 5.9% | [-21.8%, 27.0%] | 1.000 |
| Claude Haiku 4.5 | Int2 | 0/30 (0.0%) | 0/26 (0.0%) | 0.0% | [-11.4%, 12.9%] | 1.000 |
| DeepSeek V4 Pro | Int1 | 0/27 (0.0%) | 0/7 (0.0%) | 0.0% | [-12.5%, 35.4%] | 1.000 |
| DeepSeek V4 Pro | Int2 | 0/11 (0.0%) | 6/9 (66.7%) | 66.7% | [9.5%, 87.9%] | 0.002 |
| Gemini 3.1 Flash Lite | Int1 | 0/0 (—) | 0/0 (—) | — | [—, —] | — |
| Gemini 3.1 Flash Lite | Int2 | 0/0 (—) | 0/0 (—) | — | [—, —] | — |
| GPT-5.4 Nano | Int1 | 1/10 (10.0%) | 2/12 (16.7%) | 6.7% | [-35.7%, 43.0%] | 1.000 |
| GPT-5.4 Nano | Int2 | 0/5 (0.0%) | 0/4 (0.0%) | 0.0% | [-43.4%, 49.0%] | 1.000 |
| Qwen3.5-397B | Int1 | 0/55 (0.0%) | 0/19 (0.0%) | 0.0% | [-6.5%, 16.8%] | 1.000 |
| Qwen3.5-397B | Int2 | 1/7 (14.3%) | 5/9 (55.6%) | 41.3% | [-24.6%, 78.6%] | 0.145 |

## Additional outputs

- `confidence_abstention_raw.csv`: traceable row-level data and parser flags.
- `absolute_confidence_bins.csv` and `percentile_confidence_bins.csv`: the two requested binned abstention views with Wilson intervals.
- `calibration_metrics.csv`: overall and submitted-only calibration.
- `confidence_distribution_shifts.csv`: paired confidence changes across settings.
- `quantitative_switch_region.csv`: behavior in [25/26, 100/101).
- `quantitative_switch_region_contrasts.csv`: descriptive setting contrasts inside that switch band.
- `confidence_adjusted_curves.csv`: additive primary and confidence-by-setting interaction sensitivity predictions; figures show the additive primary model.
- `*_sensitivity_no_mixed.csv`: sensitivity results excluding ambiguous single-turn mixed decisions.
- `plots/`: PNG and PDF versions of all figures.

All confidence transformations are retained in the raw export. Missing or ambiguous confidence and candidate-answer parses are not imputed.
