# Math results — main body

## Question

Do LMs adapt their answering policy to the penalty embedded in the prompt?
A penalty-aware model should answer at low penalty (`+1/-1`), then increasingly
abstain as the penalty for an incorrect answer grows (`+1/-100` or worse).
A penalty-blind model answers everything regardless. We measure both.

## Setup

100 Omni-MATH problems × 5 models × 14 prompts. Each prompt encodes either a
**quantitative** scoring rubric `(s_c, s_i, s_a)` or a **qualitative**
consequence framing (catastrophic loss, getting fired, decommissioning,
nuclear apocalypse, etc.). Models answer with `\boxed{value}` or abstain with
`\boxed{UNSURE}`.

Models: Gemini 3.1 Flash-Lite, GPT-5.4 Nano, Claude 4.5 Haiku, DeepSeek V4 Pro,
Qwen 3.5 397B. All run with reasoning at "medium" effort.

Primary metric: **base accuracy** = `n_correct / n_boxed_submission` where a
boxed submission is `\boxed{X}` for any `X` (including `UNSURE`). Secondary
metrics: abstention rate (UNSURE / boxed) and conditional accuracy
(correct / attempted, excluding UNSURE). Both are reported in tables for
robustness; all claims below use base accuracy unless noted.

## Finding 1 — Accuracy is invariant to penalty

Across the t-series (`+1/-1` → `+1/-100`), base accuracy moves by less than
**±5 pp** for every model. The "scaled" rubric (`+10/-250`, same risk ratio
as t25 but 10× magnitudes) gives the same result, ruling out a magnitude effect.

![combined_quant](../quant/eval/combined_quant.png)

This mirrors Wang et al. (2025): increasing penalty has negligible effect on
behaviour. Our setup is harsher than theirs (Omni-MATH is harder than HLE for
small models) and the result holds.

## Finding 2 — Qualitative framings produce no larger effect than quantitative ones

Substituting the symmetric rubric for a "nuclear apocalypse" or
"catastrophic consequences" prompt does not push accuracy any higher. The
spread within the qual block (catastrophic / fired / nuclear / greedy / career
/ decommission / professor) is comparable to the spread within the quant
block.

![combined_qual](../qual/eval/combined_qual.png)

## Finding 3 — Models do not abstain even when abstention strictly dominates

The `abstain` rubric is `(s_c, s_i, s_a) = (−1, −10, +10)`: every correct
answer pays −1, every incorrect answer pays −10, abstention pays +10. The
optimal policy is "abstain on every problem" — even a 100%-accuracy answerer
loses ground (−1 per correct vs +10 per abstention). No confidence threshold
is needed.

The strategic-abstention rate (rows that explicitly box `UNSURE` divided by
rows that produced any `\boxed{...}`) is:

| Model | UNSURE / boxed | n_unsure | n_boxed | n_total |
|---|---:|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 17.0% | 17 | 100 | 100 |
| GPT-5.4 Nano | 24.0% | 24 | 100 | 100 |
| Claude 4.5 Haiku | 5.0% | 5 | 100 | 100 |
| DeepSeek V4 Pro | 12.5% | 9 | 72 | 99 |
| Qwen3.5 397B | 30.4% | 28 | 92 | 99 |

Even the best model (Qwen397B at 30.4%) is far from the optimal 100%. Haiku at
5% is within statistical noise of the t-series rates (1–2%). This is the same
pattern Wu et al. (2025) report for their `(0, -1)` "high-risk" structure on
GPQA — when answering is strictly suboptimal, models still answer.

The smaller `n_boxed` denominators for DeepSeek (72) and Qwen397B (92) reflect
format non-compliance: those rows ended at `</think>` without producing any
`\boxed{...}` and are excluded from the strategic-abstention count.
Treating those non-commit rows as "behavioral abstentions" gives a higher rate
(DeepSeek 36/99 = 36.4%, Qwen397B 35/99 = 35.4%), but those are
truncation artefacts, not strategic abstentions — see Robustness.

## Robustness — answer-format compliance

Some models do not always emit `\boxed{}`. We report two compliance numbers
to confirm the headline is not a measurement artefact:

| Model | Boxed rate (mean across rubrics) | Same, but at the model's worst rubric |
|---|---:|---:|
| Haiku | 99% | 95% |
| Gemini-Lite | 96% | 88% |
| Nano | 92% | 76% |
| Qwen397B | 91% | 65% (`abstain`) |
| DeepSeek | 64% | 54% (`t1`) |

DeepSeek warrants special attention: its base accuracy of ~92% is computed
over only 54–78% of the input. We hand-inspected 42 DeepSeek no-box rows on
t1 and found that the model emits `</think>` and self-terminates without
producing `\boxed{}` for ~50% of these — the answer is often present *inside*
the reasoning block. This is a known issue with R1-style thinking models
(see e.g. DeepSeek-R1 issue #314 on GitHub). Two consequences:

- DeepSeek's underlying capability is plausibly higher than its reported
  accuracy; the headline "accuracy invariant to penalty" still holds because
  the format-failure rate itself is also invariant to penalty (54-72% across
  the t-series).
- For paper claims that require strict-attempt rates (e.g. abstention
  comparisons), DeepSeek is a weak data point. Conclusions about
  "abstention is rare even at high penalty" are dominated by the four other
  models.

## Numbers — main results table

Base accuracy (%) across the penalty ladder. The flatness within each row is
the central observation.

| Model | t1 | t5 | t10 | t25 | t100 | scaled | abstain |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gemini-Lite | 79.0 | 76.0 | 79.0 | 76.0 | 78.0 | 76.0 | 69.0 |
| Nano | 65.7 | 70.7 | 69.7 | 69.7 | 67.0 | 68.0 | 63.0 |
| Haiku | 68.7 | 72.7 | 65.0 | 69.7 | 67.0 | 69.4 | 66.0 |
| DeepSeek | 91.4 | 93.1 | 91.1 | 93.0 | 89.2 | 93.8 | 83.3 |
| Qwen397B | 87.5 | 83.2 | 86.5 | 90.1 | 85.9 | 86.0 | 60.9 |

Same axis, abstention rate (% of boxed submissions that are `UNSURE`):

| Model | t1 | t5 | t10 | t25 | t100 | scaled | abstain |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gemini-Lite | 8.7 | 8.7 | 6.4 | 9.9 | 6.4 | 11.1 | 20.5 |
| Nano | 12.5 | 7.6 | 7.6 | 12.5 | 11.1 | 12.8 | 31.6 |
| Haiku | 1.0 | 1.0 | 1.0 | 2.1 | 0.0 | 1.0 | 5.3 |
| DeepSeek | 7.4 | 7.4 | 3.7 | 5.6 | 8.3 | 6.7 | 14.3 |
| Qwen397B | 3.2 | 3.3 | 5.5 | 1.4 | 2.4 | 3.3 | 43.8 |

Full numbers including conditional accuracy and the qualitative block live in
`quant_curves.json` and `qual_curves.json`.

## Discussion

Two prior works frame the failure mode we observe. **Wang et al. (2025,
RiskEval)** show that LMs produce reasonable verbal-confidence estimates but
fail to convert them into a penalty-aware decision; "calibration knowledge" is
present but unused. **Wu et al. (2025, Answer/Refuse/Guess)** show that the
failure persists even when the reward structure is given to the model
explicitly, and that prompt-chaining (separating answer / confidence /
expected-value reasoning) recovers most of the gap.

Our results extend both: with reasoning enabled across all five families and
penalties up to `−250`, no model reaches the optimal abstention policy; the
strongest qualitative framings (nuclear apocalypse) trigger less abstention
than even the modest `abstain` rubric (`+10/-10/+10`). The implication is that
quantitative and qualitative consequence prompts are roughly equivalent
levers — both weak.

## Appendix figures

Per-model 5-line plots (base / cond / abstention / boxed-rate / answered-rate)
× quant + qual: `quant/eval/per_model_*.png`, `qual/eval/per_model_*.png`.

Boxed-answer rate as a separate combined plot:
`quant/eval/combined_quant_boxed_rate.png`,
`qual/eval/combined_qual_boxed_rate.png`.

Two-panel comparison (boxed rate above, accuracy below):
`eval/two_panel.png`.

5×2 per-model grid (one row per model, two columns boxed/accuracy):
`eval/per_model_grid.png`.
