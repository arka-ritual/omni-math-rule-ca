# CoT-removal experiment

## Design

This experiment compares the existing original-position QP6 and QP7
chain-of-thought (CoT) conditions with a matched no-CoT condition. The no-CoT
instruction is:

> Please respond immediately, without any thinking. You may respond directly
> with your answer in `\boxed{}`; alternatively, abstain by responding with
> `\boxed{UNSURE}`.

The consequence text, header, task sentence, consequence position, model,
provider, question, seed, temperature, and token limit are held fixed. The
five-question pilot was extended in place to the full prefix-stable seed-100
sample of 100 questions. Thus, each model has 100 matched questions under QP6
and 100 under QP7, for 1,000 new no-CoT generations and 1,000 reused CoT
controls.

As preregistered in the pilot, the no-CoT wording removes the CoT prompt's
no-box abstention pathway. A clean no-box no-CoT response is therefore a
protocol violation, not an abstention. This wording difference means the
comparison is not a clean intervention on CoT alone.

All calls used OpenRouter with the same pinned upstream providers as the
consequence-position experiment, temperature 1.0, seed 100, and a 64,000-token
completion limit.

## Results

| Model | QP | CoT as-prompted abstain | No-CoT explicit abstain | No-CoT no-box violation | Indeterminate | CoT answered/correct | CoT selective accuracy | No-CoT answered/correct | No-CoT selective accuracy | Delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | 2 | 5 | 1 | 0 | 98 / 61 | 62.2% | 94 / 64 | 68.1% | +5.9 pp |
| Claude Haiku 4.5 | QP7 | 2 | 0 | 0 | 0 | 98 / 64 | 65.3% | 100 / 62 | 62.0% | -3.3 pp |
| DeepSeek V4 Pro | QP6 | 2 | 4 | 0 | 3 | 93 / 87 | 93.5% | 93 / 86 | 92.5% | -1.0 pp |
| DeepSeek V4 Pro | QP7 | 2 | 2 | 0 | 3 | 93 / 88 | 94.6% | 95 / 86 | 90.5% | -4.1 pp |
| Gemini 3.1 Flash Lite | QP6 | 0 | 10 | 0 | 0 | 100 / 58 | 58.0% | 90 / 19 | 21.1% | -36.9 pp |
| Gemini 3.1 Flash Lite | QP7 | 1 | 2 | 0 | 0 | 99 / 61 | 61.6% | 98 / 20 | 20.4% | -41.2 pp |
| GPT-5.4 Nano | QP6 | 9 | 16 | 0 | 0 | 91 / 46 | 50.5% | 84 / 22 | 26.2% | -24.3 pp |
| GPT-5.4 Nano | QP7 | 4 | 10 | 0 | 0 | 96 / 46 | 47.9% | 90 / 18 | 20.0% | -27.9 pp |
| Qwen3.5 397B A17B | QP6 | 3 | 5 | 2 | 0 | 97 / 82 | 84.5% | 93 / 86 | 92.5% | +8.0 pp |
| Qwen3.5 397B A17B | QP7 | 9 | 1 | 3 | 0 | 91 / 81 | 89.0% | 96 / 87 | 90.6% | +1.6 pp |

### Abstention comparison

Following the requested definition, each rate is **abstained / answered**; the
underlying counts are also shown explicitly. For the original CoT prompt,
“abstained” includes both boxed `UNSURE` and an instructed no-box abstention;
the no-CoT prompt permits only explicit boxed `UNSURE`, so its no-box outputs
remain protocol violations and are not counted as abstentions.

| Model | QP | Original CoT abstained / answered | Original CoT abstention rate | No-CoT explicit abstained / answered | No-CoT abstention rate |
|---|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | 2 / 98 | 2.0% | 5 / 94 | 5.3% |
| Claude Haiku 4.5 | QP7 | 2 / 98 | 2.0% | 0 / 100 | 0.0% |
| DeepSeek V4 Pro | QP6 | 2 / 93 | 2.2% | 4 / 93 | 4.3% |
| DeepSeek V4 Pro | QP7 | 2 / 93 | 2.2% | 2 / 95 | 2.1% |
| Gemini 3.1 Flash Lite | QP6 | 0 / 100 | 0.0% | 10 / 90 | 11.1% |
| Gemini 3.1 Flash Lite | QP7 | 1 / 99 | 1.0% | 2 / 98 | 2.0% |
| GPT-5.4 Nano | QP6 | 9 / 91 | 9.9% | 16 / 84 | 19.0% |
| GPT-5.4 Nano | QP7 | 4 / 96 | 4.2% | 10 / 90 | 11.1% |
| Qwen3.5 397B A17B | QP6 | 3 / 97 | 3.1% | 5 / 93 | 5.4% |
| Qwen3.5 397B A17B | QP7 | 9 / 91 | 9.9% | 1 / 96 | 1.0% |

### Abstention-rate significance comparison

| Model | Condition | Original CoT abstention rate | No-CoT abstention rate | Delta abstention rate | Holm-adjusted significant difference |
|---|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | 2.0% | 5.3% | +3.3 pp | No (`p_adj = 1.000`) |
| Claude Haiku 4.5 | QP7 | 2.0% | 0.0% | -2.0 pp | No (`p_adj = 1.000`) |
| DeepSeek V4 Pro | QP6 | 2.2% | 4.3% | +2.2 pp | No (`p_adj = 1.000`) |
| DeepSeek V4 Pro | QP7 | 2.2% | 2.1% | -0.05 pp | No (`p_adj = 1.000`) |
| Gemini 3.1 Flash Lite | QP6 | 0.0% | 11.1% | +11.1 pp | **Yes (`p_adj = 0.0195`)** |
| Gemini 3.1 Flash Lite | QP7 | 1.0% | 2.0% | +1.0 pp | No (`p_adj = 1.000`) |
| GPT-5.4 Nano | QP6 | 9.9% | 19.0% | +9.2 pp | No (`p_adj = 0.646`) |
| GPT-5.4 Nano | QP7 | 4.2% | 11.1% | +6.9 pp | No (`p_adj = 0.250`) |
| Qwen3.5 397B A17B | QP6 | 3.1% | 5.4% | +2.3 pp | No (`p_adj = 1.000`) |
| Qwen3.5 397B A17B | QP7 | 9.9% | 1.0% | -8.8 pp | No (`p_adj = 0.0703`) |

Delta is no-CoT minus original CoT and is calculated from the unrounded
abstained/answered ratios. Significance uses a two-sided exact McNemar test on
the 100 matched question-level abstention indicators in each row. The final
column reports p-values Holm-adjusted across all ten comparisons, and bolded
cells are significant at the adjusted 5% level.

The effect of removing the CoT instruction is strongly model-dependent. It
substantially reduces selective accuracy for Gemini and GPT-5.4 Nano, is
slightly negative for DeepSeek, is mixed for Claude, and is positive for Qwen
on this sample. Abstention also does not move uniformly: the no-CoT condition
increases explicit abstention most clearly for Gemini QP6 and both GPT cells,
while Qwen QP7 has fewer as-prompted abstentions than its CoT control.

Across the 1,000 no-CoT outputs, 988 contained at least one box. There were 55
explicit boxed-`UNSURE` abstentions, six no-box protocol violations, one mixed
answer/`UNSURE` response (scored as an attempted incorrect response), and six
length-truncated DeepSeek generations with no committed answer, classified as
indeterminate. All other generations had provider finish reason `stop`.

## Refusal and adherence audit

One no-CoT response out of 1,000 was a refusal or unwillingness to complete
the task: Claude QP6 on index 873 requested the omitted multiple-choice answer
options instead of answering. This was a task-format refusal, not a safety
refusal. All automatically flagged refusal candidates were manually checked;
a Qwen mathematical use of “cannot” was rejected as a false positive.

The five-question pilot's visible-reasoning labels were manually reviewed.
For the full sample, visible-direct rates in the machine-readable summary use
a conservative automated screen and should be treated as provisional rather
than as manually coded adherence results. Provider-separated hidden reasoning
was present on every DeepSeek and Qwen call and is reported separately from
the committed answer.

## Integrity checks

Each of the ten no-CoT files contains exactly 100 unique seed-100 sample
indices. The analyzer verified exact agreement of question indices with the
reused CoT controls and checked the persisted prompt, model ID, pinned
provider, seed, temperature, and token limit for every row. The two malformed
Qwen responses observed during the first pass were omitted and retried by
index; both retries succeeded, leaving no missing or duplicate rows.

Raw generations are retained under
`inference/results/cot_ablation_pilot/`. Standard evaluations and the full
matched summary, per-question outcomes, and review queue are under
`evaluation/output/cot_ablation_full/`.
