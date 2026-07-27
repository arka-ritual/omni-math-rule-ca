# GPT-5.6 Sol Omni-MATH results analysis

## Experimental scope

GPT-5.6 Sol was evaluated on the same seed-100 set of 100 Omni-MATH
questions used for the prior GPT-5.4 Nano sweep. The four conditions were:

- \(r_{100}\): +1 correct, -100 incorrect, 0 abstain.
- \(r_{\mathrm{abstain}}\): -1 correct, -10 incorrect, +10 abstain.
- QP6: the professor/failure qualitative framing.
- QP7: the humanity-extinction qualitative framing.

GPT-5.6 Sol used explicit high reasoning effort, omitted temperature, and a
64,000-token maximum output. Every returned row was served by OpenAI through
OpenRouter and every condition contains the same 100 question IDs. There were
no truncated or indeterminate outputs.

## Main results

| Condition | Correct | Incorrect | Abstained | Coverage | Attempted accuracy | 95% Wilson CI |
|---|---:|---:|---:|---:|---:|---:|
| \(r_{100}\) | 79 | 18 | 3 | 97% | 81.4% | [72.6%, 87.9%] |
| \(r_{\mathrm{abstain}}\) | 27 | 7 | 66 | 34% | 79.4% | [63.2%, 89.7%] |
| QP6 | 74 | 24 | 2 | 98% | 75.5% | [66.1%, 83.0%] |
| QP7 | 80 | 19 | 1 | 99% | 80.8% | [72.0%, 87.4%] |

The most important result is the large behavioral change under
\(r_{\mathrm{abstain}}\). Its 66% abstention rate is 63 percentage points
higher than \(r_{100}\), while its attempted accuracy is not higher (79.4%
versus 81.4%). Thus, the explicit positive reward for abstaining substantially
reduced coverage without producing a detectable gain in selective accuracy.
The confidence interval is also wider because only 34 questions were
attempted.

By contrast, the large downside in \(r_{100}\) and the catastrophic narrative
framings in QP6/QP7 produced very little abstention: 3%, 2%, and 1%,
respectively. The corresponding 95% Wilson intervals for abstention are
[1.0%, 8.5%], [0.6%, 7.0%], and [0.2%, 5.4%]. These results suggest that this
model reacts much more strongly to an explicitly dominant abstention reward
than to downside magnitude or narrative stakes alone.

## Realized rubric behavior

The realized scores under the two quantitative rubrics expose a gap between
behavioral sensitivity and payoff maximization:

| Condition | GPT-5.6 Sol realized score | GPT-5.4 Nano realized score | Best all-abstain score |
|---|---:|---:|---:|
| \(r_{100}\) | \(79 - 100(18) = -1721\) | \(47 - 100(49) = -4853\) | 0 |
| \(r_{\mathrm{abstain}}\) | \(-27 - 10(7) + 10(66) = 563\) | \(-40 - 10(52) + 10(8) = -480\) | 1000 |

For \(r_{100}\), attempting has positive expected value only above a 99.01%
probability of correctness, but the model attempted 97 questions and achieved
81.4% empirical accuracy. GPT-5.6 Sol therefore improves the realized score
substantially over Nano but remains far below the all-abstain policy ex post.

For \(r_{\mathrm{abstain}}\), abstaining strictly dominates answering: even a
correct answer receives -1 instead of +10. GPT-5.6 Sol moved strongly toward
the dominant action, raising abstention from Nano's 8% to 66%, but still
answered 34 questions and left 437 score points relative to always
abstaining. This is evidence of substantial, but incomplete, adaptation to the
stated utility function.

## Paired behavior across GPT-5.6 Sol conditions

Because all four conditions use identical question IDs, their classifications
can be compared question by question:

| Comparison with \(r_{100}\) | Exact correct/incorrect/abstain agreement | \(r_{100}\) correct → other not correct | \(r_{100}\) not correct → other correct |
|---|---:|---:|---:|
| \(r_{\mathrm{abstain}}\) | 35/100 | 53 | 1 |
| QP6 | 94/100 | 5 | 0 |
| QP7 | 96/100 | 1 | 2 |

QP6 and QP7 are highly concordant with \(r_{100}\), reinforcing the conclusion
that these three high-stakes framings caused little decision-policy change.
QP7 produced only four three-way classification changes relative to
\(r_{100}\), and QP6 produced six.

The \(r_{\mathrm{abstain}}\) policy is qualitatively different. Of the 63
questions that \(r_{100}\) attempted but \(r_{\mathrm{abstain}}\) skipped, 52
were correct and 11 were incorrect under \(r_{100}\). The corresponding
\(r_{100}\) accuracy on this skipped subset is 82.5%, close to its overall
81.4% attempted accuracy. Conversely, on the 34 questions
\(r_{\mathrm{abstain}}\) chose to answer, \(r_{100}\) was correct on 27
(79.4%). The abstention shift therefore does not appear to isolate a
higher-accuracy subset in this sample.

## Comparison with GPT-5.4 Nano

| Condition | Δ attempted accuracy (Sol - Nano) | Δ abstention rate |
|---|---:|---:|
| \(r_{100}\) | +32.4 pp | -1.0 pp |
| \(r_{\mathrm{abstain}}\) | +35.9 pp | +58.0 pp |
| QP6 | +21.0 pp | -9.1 pp |
| QP7 | +29.3 pp | -2.0 pp |

GPT-5.6 Sol has much higher attempted accuracy in every condition. On the
shared question IDs, exact two-sided McNemar tests of correct versus
not-correct classifications give:

| Condition | Sol-only correct | Nano-only correct | Common N | Exact p-value |
|---|---:|---:|---:|---:|
| \(r_{100}\) | 36 | 4 | 100 | \(1.9 \times 10^{-7}\) |
| \(r_{\mathrm{abstain}}\) | 6 | 19 | 100 | 0.0146 |
| QP6 | 33 | 8 | 99 | 0.00011 |
| QP7 | 36 | 6 | 100 | \(2.8 \times 10^{-6}\) |

The reversed correct-count comparison for \(r_{\mathrm{abstain}}\) is not a
contradiction: GPT-5.6 Sol was more accurate conditional on attempting, but
attempted only 34 questions, so it produced fewer correct answers overall.
This distinction between selective accuracy and total correct coverage is
central to interpreting abstention experiments.

## Interpretation and limitations

The frontier-scale result strengthens two conclusions. First, the prompt can
produce a very large decision-policy change even in a substantially stronger
model, as shown by the 58-point Sol-versus-Nano increase in abstention under
\(r_{\mathrm{abstain}}\). Second, stronger mathematical performance does not
imply literal expected-utility maximization: GPT-5.6 Sol still violates the
dominant all-abstain policy in \(r_{\mathrm{abstain}}\) and attempts far too
many questions to make the \(r_{100}\) rubric profitable ex post.

Several qualifications matter:

- N=100 limits precision, especially for the 34 attempted
  \(r_{\mathrm{abstain}}\) questions.
- Each condition has one generation per question, so the uncertainty intervals
  describe variation across questions, not run-to-run model stochasticity.
- The model comparison is not a pure architecture comparison: GPT-5.6 Sol used
  high reasoning with temperature omitted, whereas the prior Nano sweep used
  medium reasoning and T=1.0.
- The stored prior Nano QP6 cell has N=99, so its aggregate comparison is based
  on one fewer question; the paired test uses the 99 common IDs.

Overall, GPT-5.6 Sol is both markedly more capable than GPT-5.4 Nano and
strongly responsive to the explicit abstention-dominant rubric, while
remaining comparatively insensitive to the other high-stakes framings and
not fully optimizing either quantitative payoff structure.
