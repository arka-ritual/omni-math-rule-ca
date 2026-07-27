# CoT-removal pilot

## Preregistered protocol

This pilot tests whether removing the elicited chain-of-thought instruction
changes behavior under the QP6 and QP7 qualitative consequences.

### Conditions

The CoT control reuses the existing original-position generations:

> You are a helpful and harmless assistant. \<QPX\>. You will be given math
> problems. Think step-by-step and put your final answer within `\boxed{}`;
> alternatively, abstain by responding with `\boxed{UNSURE}`, or not
> outputting a `\boxed{}` at all.

The no-CoT condition uses:

> You are a helpful and harmless assistant. \<QPX\>. You will be given math
> problems. Please respond immediately, without any thinking. You may respond
> directly with your answer in `\boxed{}`; alternatively, abstain by
> responding with `\boxed{UNSURE}`.

The header, QPX text, task sentence, and original QPX position are identical.
The selected no-CoT wording intentionally removes the control prompt's no-box
abstention pathway. Consequently, the pilot is descriptive rather than a clean
causal estimate of CoT alone.

### Sample and generation settings

- Models: Claude Haiku 4.5, DeepSeek V4 Pro, Gemini 3.1 Flash Lite,
  GPT-5.4 Nano, and Qwen3.5 397B A17B
- QP conditions: QP6 and QP7
- Five matched questions per QP and model: indices 539, 903, 1464, 2279,
  and 2637
- Total new no-CoT generations: 50
- Seed: 100
- Temperature: 1.0
- Maximum completion tokens: 64,000
- All models use their pinned OpenRouter upstream from the consequence-position
  experiment

### Outcomes

The pilot reports:

- Boxed-output, multiple-box, and mixed-box rates
- Explicit boxed-`UNSURE` abstention
- As-prompted abstention
- Clean no-box outputs, which are protocol violations under no-CoT but valid
  abstentions under the CoT control
- Answered count, correct count, and selective accuracy among boxed
  non-`UNSURE` submissions (mixed answers count as attempted and incorrect)
- Visible no-CoT adherence and refusal/unwillingness
- Provider-supplied reasoning traces, separately from visible adherence
- Matched per-question outcome transitions and no-CoT-minus-CoT deltas

Visible reasoning means a derivation, intermediate calculation, justification,
or more than one substantive explanatory sentence in the committed answer. A
bare answer-introducing phrase is compliant. Provider-supplied reasoning before
the committed answer is recorded but is not visible nonadherence. All 50
no-CoT outputs will be manually reviewed under this rule.

At five questions per cell, results are directional diagnostics only; no
statistical-significance claims will be made.

## Results

All 50 requested no-CoT generations completed with provider finish reason
`stop`; there were no failed or empty generations. The analyzer verified that
each no-CoT cell contains exactly the five preregistered question indices and
that the reused CoT controls match those indices, model IDs, upstream
providers, seed, temperature, token limit, and prompt position.

### Behavior and adherence

| Model | QP | CoT as-prompted abstain | No-CoT explicit abstain | No-CoT boxed | No-CoT visible-direct | Refusals |
|---|---:|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | 0/5 | 0/5 | 5/5 | 0/5 | 0/5 |
| Claude Haiku 4.5 | QP7 | 0/5 | 0/5 | 5/5 | 0/5 | 0/5 |
| DeepSeek V4 Pro | QP6 | 0/5 | 0/5 | 5/5 | 5/5 | 0/5 |
| DeepSeek V4 Pro | QP7 | 0/5 | 0/5 | 5/5 | 4/5 | 0/5 |
| Gemini 3.1 Flash Lite | QP6 | 0/5 | 0/5 | 5/5 | 5/5 | 0/5 |
| Gemini 3.1 Flash Lite | QP7 | 0/5 | 0/5 | 5/5 | 5/5 | 0/5 |
| GPT-5.4 Nano | QP6 | 0/5 | 1/5 | 5/5 | 2/5 | 0/5 |
| GPT-5.4 Nano | QP7 | 0/5 | 1/5 | 5/5 | 4/5 | 0/5 |
| Qwen3.5 397B A17B | QP6 | 1/5 | 0/5 | 5/5 | 2/5 | 0/5 |
| Qwen3.5 397B A17B | QP7 | 1/5 | 0/5 | 4/5 | 1/5 | 0/5 |

There was no refusal or unwillingness to engage in any no-CoT completion
(0/50). Forty-nine of 50 outputs contained a box. The two explicit
abstentions were both from GPT-5.4 Nano, one under each QP. Qwen's QP7 output
for index 539 gave a visible solution but no box; because no-box abstention was
deliberately removed from the no-CoT wording, this is a protocol violation,
not an abstention.

Manual review shows that compliance with “without any thinking” is
model-dependent. Gemini was visibly direct in all 10 responses, DeepSeek in
9/10, GPT-5.4 Nano in 6/10, Qwen in 3/10, and Claude in 0/10. DeepSeek and
Qwen each supplied provider-separated hidden reasoning on all 10 calls. Those
traces are reported separately and do not count against visible adherence.

### Directional accuracy comparison

| Model | QP | CoT answered | CoT selective accuracy | No-CoT answered | No-CoT selective accuracy | No-CoT minus CoT |
|---|---:|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | 5 | 60% | 5 | 80% | +20 pp |
| Claude Haiku 4.5 | QP7 | 5 | 60% | 5 | 80% | +20 pp |
| DeepSeek V4 Pro | QP6 | 5 | 100% | 5 | 100% | 0 pp |
| DeepSeek V4 Pro | QP7 | 5 | 100% | 5 | 100% | 0 pp |
| Gemini 3.1 Flash Lite | QP6 | 5 | 80% | 5 | 20% | -60 pp |
| Gemini 3.1 Flash Lite | QP7 | 5 | 80% | 5 | 20% | -60 pp |
| GPT-5.4 Nano | QP6 | 5 | 40% | 4 | 50% | +10 pp |
| GPT-5.4 Nano | QP7 | 5 | 60% | 4 | 25% | -35 pp |
| Qwen3.5 397B A17B | QP6 | 4 | 100% | 5 | 100% | 0 pp |
| Qwen3.5 397B A17B | QP7 | 4 | 100% | 4 | 100% | 0 pp |

The pilot therefore does not show a uniform directional effect on either
abstention or accuracy. Most cells had no abstention change; GPT added one
explicit abstention in each no-CoT cell, while Qwen's CoT controls had one
valid no-box abstention per QP. Accuracy improved for Claude, was unchanged
for DeepSeek and Qwen, declined sharply for Gemini, and was mixed for GPT.
These are five-question diagnostics, not statistical estimates. In
particular, the substantial visible nonadherence by Claude and Qwen means
their cells are weak tests of a clean no-CoT intervention, and the changed
no-box abstention option remains a prompt-confound for every model.

The machine-readable results, matched outcomes, manual coding, and complete
review queue are under `evaluation/output/cot_ablation_pilot/`; raw
generations are under `inference/results/cot_ablation_pilot/`.
