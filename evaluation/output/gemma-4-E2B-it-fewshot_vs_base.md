# Few-shot preamble: instruct (gemma-4-E2B-it) vs base (gemma-4-E2B)

Per-row: abstention rate (fraction of all problems where the model produced `\boxed{UNSURE}` or no `\boxed{}` in a non-truncated response) and selective accuracy on the *attempted* subset (correct / (correct + incorrect)).

## Prompt: `ultra_cautious`

| Row | Instruct abst | Instruct sel.acc (n) | Base abst | Base sel.acc (n) |
|---|---|---|---|---|
| **no-fewshot** | 0.0% | 42.2% (100) | — | — (—) |
| fewshot=`normal` | 21.0% | 48.1% (100) | — | — (—) |
| fewshot=`no_conseq` | 13.0% | 48.3% (100) | — | — (—) |
| fewshot=`conseq_no_abstain` | 7.0% | 51.6% (100) | 0.0% | 4.0% (100) |
| fewshot=`conseq_random_abstain` | 13.0% | 48.3% (100) | 43.0% | 7.0% (100) |
| fewshot=`conseq_correct_abstain` | 13.0% | 54.0% (100) | 52.0% | 0.0% (100) |
| fewshot=`conseq_always_submit` | 7.0% | 49.5% (100) | 0.0% | 2.0% (100) |
| fewshot=`conseq_always_abstain` | 14.0% | 51.2% (100) | 90.0% | 0.0% (10) |

*no-fewshot abstention: instruct=0.0%, base=—*
