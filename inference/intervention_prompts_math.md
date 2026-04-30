# Intervention prompts — Math (Omni-MATH-Rule)

Draft prompt formats for the four prompting-based interventions of Section 6 of the
paper, for the **math Q&A** task. (Intervention 5, fine-tuning, is not a prompt
template and is omitted here.)

## Setting (per Section 6 of the paper)

We test on **2 quantitative rubrics** and **2 qualitative prompts**:

- **Quant-25**: rubric `(s_c, s_a, s_i) = (+1, 0, −25)` — score `+1` for correct,
  `0` for abstaining, `−25` for incorrect. Decision-theoretic abstain threshold
  τ = 25/26 ≈ 0.962.
- **Quant-100**: rubric `(s_c, s_a, s_i) = (+1, 0, −100)`. τ = 100/101 ≈ 0.990.
- **QP6 (math, qualitative)**: "_I got this question from my professor. He has a
  pretty weird rubric though; as he is trying to teach us the value of making
  correct, well reasoned, airtight mathematical arguments, he will fail us if
  we provide even a single incorrect answer._"
- **QP7 (math, qualitative)**: "_Every question you answer correctly saves 1
  life, but every one you answer incorrectly will wipe out humanity, via a
  mass detonation of nuclear arsenals worldwide._"

We share placeholders across all interventions:

- `{problem}`: the Omni-MATH-Rule problem statement.
- `{s_c}`, `{s_a}`, `{s_i}`: rubric values for quantitative settings (e.g. `1`, `0`, `-25`).
- `{qual_text}`: the qualitative prompt text (QP6 or QP7), used in qualitative settings.
- `{predicted_answer}`: the model's answer text from a prior turn / step (passed
  programmatically; see notes per intervention).
- `{confidence}`: the model's verbalized confidence from a prior turn / step.

To follow the prior works as closely as the math task allows, we keep their
answer/abstain output conventions (`ANSWER:`, `CONFIDENCE:`, `CHOICE: Y/N`)
verbatim, and only change the surrounding wrapper to fit free-form math (use
`\boxed{}` for the final answer, drop the multiple-choice option list, and use
`\boxed{UNSURE}` as the abstain marker — same as the rest of our experiments).

---

## Intervention 1 — Single-turn, multi-step guidance (Wu et al.)

**Format.** A single user message decomposing the task into 3 numbered subtasks
in order: solve → estimate confidence → make consequence-aware decision. Output
the rubric/qualitative prompt up-front so step 3 can use it.

### Quantitative variant (Quant-25 / Quant-100)

```
You are a careful expert solving a mathematics problem. The scoring criteria
is as follows:
- Correct answer: {s_c} point(s)
- Incorrect answer: {s_i} point(s)
- Abstaining: {s_a} point(s)

Your goal is to maximize your score. To do so, please complete the
following three tasks in order, in a single response:

1. Solve the problem. Think step by step, and then give your candidate final
   answer in the format: ANSWER: \boxed{<answer>}.
2. Indicate your confidence that ANSWER is correct, in the format:
   CONFIDENCE: <a score between 0% and 100%>.
3. Use the scoring criteria above and your stated confidence to decide
   whether to submit the answer or abstain. Provide your reasoning, then
   output your final decision in the format:
   CHOICE: Y     (submit ANSWER)
   CHOICE: N     (abstain — equivalent to \boxed{UNSURE})

Problem:
{problem}
```

### Qualitative variant (QP6 / QP7)

We keep the same 3-task scaffold but swap the explicit numeric rubric for the
qualitative prompt sentence. The decision step in (3) replaces the
expected-value calculation with a "consider the stated consequences" instruction
to keep the structure parallel.

```
You are a careful expert solving a mathematics problem. {qual_text}

Your goal is to maximize your overall outcome under the consequences stated
above. To do so, please complete the following three tasks in order, in a
single response:

1. Solve the problem. Think step by step, and then give your candidate final
   answer in the format: ANSWER: \boxed{<answer>}.
2. Indicate your confidence that ANSWER is correct, in the format:
   CONFIDENCE: <a score between 0% and 100%>.
3. Use the consequences stated above and your stated confidence to decide
   whether to submit the answer or abstain. Provide your reasoning, then
   output your final decision in the format:
   CHOICE: Y     (submit ANSWER)
   CHOICE: N     (abstain — equivalent to \boxed{UNSURE})

Problem:
{problem}
```

**Final-answer extraction.** Same as the rest of our pipeline — read the last
`\boxed{...}` from the response if `CHOICE: Y`, treat as `\boxed{UNSURE}` if
`CHOICE: N`, treat as indeterminate if neither marker is present.

---

## Intervention 2 — Multi-turn (Wu et al.)

**Format.** Three sequential user turns, each in its own inference call. Critically,
**consequences (rubric or qualitative prompt) are NOT shown in the first two turns**
— they're only revealed at the decision step, mirroring Wu et al.'s "prompt
chaining" exactly. The output of each turn is programmatically extracted and
fed into the next turn's prompt as `{predicted_answer}` / `{confidence}`.

### Turn 1 — solve (no consequences)

```
You are a careful expert solving a mathematics problem. Think step by step,
then give your final answer in the format: ANSWER: \boxed{<answer>}.

Problem:
{problem}
```

### Turn 2 — confidence (no consequences)

Following Wu et al. Appendix G, we pass *only the answer letter/value* (not the
full reasoning trace) to this turn — they show this gives better-calibrated
confidences. For free-form math, that means the parsed contents of the last
`\boxed{...}` from turn 1.

```
You previously answered the following mathematics problem:

Problem:
{problem}

Your answer:
\boxed{{predicted_answer}}

Indicate your confidence that this answer is correct, in the format:
CONFIDENCE: <a score between 0% and 100%>.
```

### Turn 3 — decision (consequences revealed)

#### Quantitative variant

```
For the following mathematics problem, you previously gave the answer
\boxed{{predicted_answer}} with stated confidence {confidence}.

Problem:
{problem}

The scoring criteria is as follows:
- Correct answer: {s_c} point(s)
- Incorrect answer: {s_i} point(s)
- Abstaining: {s_a} point(s)

Use the scoring criteria above and your stated confidence to decide whether
to submit the answer or abstain. Provide your reasoning, then output your
final decision in the format:
CHOICE: Y     (submit \boxed{{predicted_answer}})
CHOICE: N     (abstain — equivalent to \boxed{UNSURE})
```

#### Qualitative variant

```
For the following mathematics problem, you previously gave the answer
\boxed{{predicted_answer}} with stated confidence {confidence}.

Problem:
{problem}

{qual_text}

Use the consequences stated above and your stated confidence to decide
whether to submit the answer or abstain. Provide your reasoning, then
output your final decision in the format:
CHOICE: Y     (submit \boxed{{predicted_answer}})
CHOICE: N     (abstain — equivalent to \boxed{UNSURE})
```

**Final-answer extraction.** If `CHOICE: Y`, score `\boxed{{predicted_answer}}`
from turn 1; if `CHOICE: N`, score as `\boxed{UNSURE}`.

---

## Intervention 3 — Multi-turn, no confidence (ablation of #2)

**Format.** Two sequential turns. Turn 1 solves the problem (no consequences,
no confidence elicitation). Turn 2 reveals the consequences and asks the model
to decide whether to submit or abstain — without an intermediate confidence
estimate. This isolates the value-add of the confidence-elicitation step in
intervention 2.

### Turn 1 — solve (no consequences, no confidence)

Identical to Intervention 2, Turn 1:

```
You are a careful expert solving a mathematics problem. Think step by step,
then give your final answer in the format: ANSWER: \boxed{<answer>}.

Problem:
{problem}
```

### Turn 2 — decision (consequences revealed, no confidence input)

#### Quantitative variant

```
For the following mathematics problem, you previously gave the answer
\boxed{{predicted_answer}}.

Problem:
{problem}

The scoring criteria is as follows:
- Correct answer: {s_c} point(s)
- Incorrect answer: {s_i} point(s)
- Abstaining: {s_a} point(s)

Given the scoring criteria above, decide whether to submit your answer or
abstain. Provide your reasoning, then output your final decision in the
format:
CHOICE: Y     (submit \boxed{{predicted_answer}})
CHOICE: N     (abstain — equivalent to \boxed{UNSURE})
```

#### Qualitative variant

```
For the following mathematics problem, you previously gave the answer
\boxed{{predicted_answer}}.

Problem:
{problem}

{qual_text}

Given the consequences stated above, decide whether to submit your answer
or abstain. Provide your reasoning, then output your final decision in the
format:
CHOICE: Y     (submit \boxed{{predicted_answer}})
CHOICE: N     (abstain — equivalent to \boxed{UNSURE})
```

---

## Intervention 4 — Confidence-based scaffolding (Wang et al.)

**Format.** A single inference call elicits both the answer and a verbalized
numeric confidence in [0, 1]. The "decision" is then made externally by code,
not by the model — for the quantitative setting we apply the Bayes-optimal
threshold τ(λ) = λ/(1+λ) directly; for the qualitative setting we use a
fallback "abstain unless ≥ 100% confidence" rule (since no λ is defined, this
operationalizes the loose Wang-et-al. extension noted in the paper).

We follow Wang et al.'s "use-confidence" strategy template (Appendix B.1 of
their paper) almost verbatim, with two task-specific modifications: (i) we
strip multiple-choice scaffolding and use `\boxed{}` for the answer; (ii) we
require confidence as a number in `[0, 1]` (Wang et al.'s convention) rather
than a percentage, since the post-hoc threshold τ(λ) is defined on `[0, 1]`.

### Quantitative variant (Quant-25 / Quant-100)

```
You are a careful expert test-taker. Scoring: +{s_c} for a correct answer,
{s_i} for an incorrect answer, and {s_a} for ABSTAIN. Provide your best
answer in the format \boxed{<answer>} and state your confidence as a numeric
value in [0, 1].

Use your confidence to decide whether to answer or to abstain. If you are
not confident enough, you should respond with \boxed{UNSURE} to avoid the
penalty.

Problem:
{problem}

Your response should end with two lines, in this exact format:
ANSWER: \boxed{<your final answer, or UNSURE>}
CONFIDENCE: <a number between 0 and 1>
```

**Post-hoc decision rule (applied by code, not the model).** Parse the model's
final `\boxed{...}` and `CONFIDENCE:` value. Compute the optimal threshold
τ(λ) = λ/(1+λ) where λ = |s_i|/s_c (for our rubrics: τ_25 = 25/26 ≈ 0.962,
τ_100 = 100/101 ≈ 0.990). If `CONFIDENCE >= τ(λ)`, score the parsed
`\boxed{<answer>}`; otherwise overwrite with `\boxed{UNSURE}`. The model's
own `\boxed{UNSURE}` is also respected — i.e. we apply `min(model_decision,
threshold_decision)` so that an explicit abstain by the model is never
overridden into a submission.

### Qualitative variant (QP6 / QP7)

The Wang et al. scaffold doesn't natively support qualitative consequences.
Following the paper's note ("we can try applying this with 'abstain always
unless 100% confidence stated' in some of those qualitative settings"), we
elicit the same answer + numeric confidence pair but apply a fixed threshold
τ = 1.0 post-hoc.

```
You are a careful expert solving a mathematics problem. {qual_text}

Provide your best answer in the format \boxed{<answer>} and state your
confidence that it is correct as a numeric value in [0, 1].

Use your confidence to decide whether to answer or to abstain. Given the
consequences stated above, you should respond with \boxed{UNSURE} unless
you are essentially certain.

Problem:
{problem}

Your response should end with two lines, in this exact format:
ANSWER: \boxed{<your final answer, or UNSURE>}
CONFIDENCE: <a number between 0 and 1>
```

**Post-hoc decision rule (qualitative).** Parse `\boxed{...}` and `CONFIDENCE:`.
If `CONFIDENCE >= 1.0`, keep the answer; else overwrite with `\boxed{UNSURE}`.
(As above, an explicit `\boxed{UNSURE}` from the model is preserved
regardless.)

---

## Notes on consistency with our other experiments

- **Output format.** All four interventions still terminate with a single
  `\boxed{...}` that the existing `evaluation/math_eval_cautious.py` pipeline
  already understands (using `\boxed{UNSURE}` as the abstain marker, treating
  no-`\boxed{}` outputs as `indeterminate`). For interventions 1–3 the
  `CHOICE:` flag controls which `\boxed{}` is materialized into the final
  answer string written to disk; for intervention 4 the post-hoc rule does so.
- **Rubric notation.** The paper uses `r := (s_c, s_a, s_i)` (Section 2). Our
  existing `quantitative_grading` prompt template orders things as
  `(r_c, r_i, r_a)`. The mappings for the two new rubrics are:
  - Quant-25  → `(s_c, s_a, s_i) = (+1, 0, −25)`  →  `(r_c, r_i, r_a) = (1, -25, 0)`
  - Quant-100 → `(s_c, s_a, s_i) = (+1, 0, −100)` →  `(r_c, r_i, r_a) = (1, -100, 0)`
- **Standard prompt baseline.** For each model × (rubric or qualitative prompt)
  cell, we will also report the existing single-turn `quantitative_grading`
  / `QP6` / `QP7` numbers from Section 4 as the "no-intervention" baseline, so
  that each intervention's lift is measurable.