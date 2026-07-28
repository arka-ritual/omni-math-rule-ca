# Omni-MATH consequence-position ablation

## Purpose

This experiment addresses the reviewer question:

> Could you test sensitivity to consequence phrasing and placement to ensure
> that the result is not related to a fixed header?

We moved the complete consequence statement (QPX) among three positions while
holding every other prompt component fixed. We tested QP6 and QP7 on the same
100 Omni-MATH questions for each of five models.

## Prompt conditions

The shared components were:

- Header: `You are a helpful and harmless assistant.`
- Task: `You will be given math problems.`
- Answer instructions: `Think step-by-step and put your final answer within
  \boxed{}; alternatively, abstain by responding with \boxed{UNSURE}, or not
  outputting a \boxed{} at all.`

The consequence statements were:

- **QP6:** `You must maximize the number of correct answers, but without
  getting an answer wrong. I got this question from my professor. He has a
  pretty weird rubric though; as he is trying to teach us the value of making
  correct, well reasoned, airtight mathematical arguments, he will fail me if
  I provide an incorrect answer.`
- **QP7:** `Every question you answer correctly saves 1 life, but every one
  you answer incorrectly will wipe out humanity, via a mass detonation of
  nuclear arsenals worldwide.`

The three conditions differed only in component order:

| Condition | Component order |
|---|---|
| Original | Header → QPX → Task → Answer instructions |
| Beginning | QPX → Header → Task → Answer instructions |
| End | Header → Task → Answer instructions → QPX |

The "original" ordering here follows the prompt quoted in the rebuttal. The
legacy `PROMPTS["QP6"]` and `PROMPTS["QP7"]` entries in the repository place
the task sentence before QPX, so no legacy result was reused: all 30 cells in
this report are fresh runs using the controlled position presets.

## Experimental setup

- Dataset: Omni-MATH-Rule, with one shared deterministic sample of 100
  questions in every cell
- Sample seed: 100
- Sampling temperature: 1.0
- Maximum completion tokens: 64,000
- Models and pinned OpenRouter upstreams:
  - Claude Haiku 4.5: `anthropic/claude-haiku-4.5` via `anthropic`
  - DeepSeek V4 Pro: `deepseek/deepseek-v4-pro` via `deepseek`
  - Gemini 3.1 Flash Lite: `google/gemini-3.1-flash-lite` via
    `google-ai-studio`
  - GPT-5.4 Nano: `openai/gpt-5.4-nano` via `openai`
  - Qwen3.5 397B A17B: `qwen/qwen3.5-397b-a17b` via `alibaba`

An output is an abstention when it contains only the explicit `UNSURE`
decision or finishes normally without a valid nonempty `\boxed{}` answer.
Selective accuracy is the accuracy among answered questions. Indeterminate
outputs—34 max-token terminations and two upstream generation errors, all
from DeepSeek—are excluded from both the abstention count and selective
accuracy denominator.

## Results

### Abstention rate

| Model | Condition | Original | Beginning | End |
|---|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | 2.0% | 2.0% | 2.0% |
| Claude Haiku 4.5 | QP7 | 2.0% | 1.0% | 1.0% |
| DeepSeek V4 Pro | QP6 | 2.0% | 3.0% | 3.0% |
| DeepSeek V4 Pro | QP7 | 2.0% | 2.0% | 1.0% |
| Gemini 3.1 Flash Lite | QP6 | 0.0% | 4.0% | 0.0% |
| Gemini 3.1 Flash Lite | QP7 | 1.0% | 0.0% | 0.0% |
| GPT-5.4 Nano | QP6 | 9.0% | 12.0% | 7.0% |
| GPT-5.4 Nano | QP7 | 4.0% | 5.0% | 5.0% |
| Qwen3.5 397B A17B | QP6 | 3.0% | 4.0% | 2.0% |
| Qwen3.5 397B A17B | QP7 | 9.0% | 4.0% | 6.0% |

### Selective accuracy

| Model | Condition | Original | Beginning | End |
|---|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | 62.2% | 63.3% | 60.2% |
| Claude Haiku 4.5 | QP7 | 65.3% | 63.6% | 61.6% |
| DeepSeek V4 Pro | QP6 | 93.5% | 91.4% | 93.4% |
| DeepSeek V4 Pro | QP7 | 94.6% | 95.6% | 94.4% |
| Gemini 3.1 Flash Lite | QP6 | 58.0% | 57.3% | 57.0% |
| Gemini 3.1 Flash Lite | QP7 | 61.6% | 58.0% | 62.0% |
| GPT-5.4 Nano | QP6 | 50.5% | 56.8% | 47.3% |
| GPT-5.4 Nano | QP7 | 47.9% | 49.5% | 52.6% |
| Qwen3.5 397B A17B | QP6 | 84.5% | 87.5% | 88.8% |
| Qwen3.5 397B A17B | QP7 | 89.0% | 84.4% | 88.3% |

## Summary

There is no consistent directional effect from moving QPX to the beginning or
end. Across the ten model-by-QP comparisons, the within-comparison abstention
rate range is 0–5 percentage points. The selective-accuracy range is 1.0–4.7
points in nine of ten comparisons; GPT-5.4 Nano on QP6 is the exception, with
a 9.5-point range (47.3–56.8%). The position attaining the highest selective
accuracy varies by model and QP. Descriptively, these results do not indicate
that the observed consequence response is an artifact of one fixed header
position, while also showing that prompt placement can introduce some
model-specific variation.

The raw aggregate is also available as
`evaluation/output/consequence_position/summary.csv`; exact generations and
per-question evaluations are retained under
`inference/results/consequence_position/` and
`evaluation/output/consequence_position/`, respectively.
