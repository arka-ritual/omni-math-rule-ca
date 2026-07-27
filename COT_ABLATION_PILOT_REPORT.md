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

Pending pilot execution.
