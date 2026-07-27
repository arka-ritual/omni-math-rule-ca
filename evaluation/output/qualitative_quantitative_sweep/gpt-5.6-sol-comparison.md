# GPT-5.6 Sol comparison on Omni-MATH

GPT-5.6 Sol: OpenRouter `openai/gpt-5.6-sol`, upstream `openai`, reasoning effort `high`, temperature omitted, max output 64,000 tokens, seed 100, N=100.

Prior GPT-5.4 Nano results use reasoning effort `medium`, T=1.0, max output 64,000 tokens, and seed 100.

| Condition | Model | N | Correct | Incorrect | Abstained | Indeterminate | Attempted accuracy | Abstention rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| $r_{100}$ | GPT-5.6 Sol | 100 | 79 | 18 | 3 | 0 | 81.4% | 3.0% |
| $r_{100}$ | GPT-5.4 Nano | 100 | 47 | 49 | 4 | 0 | 49.0% | 4.0% |
| $r_{\mathrm{abstain}}$ | GPT-5.6 Sol | 100 | 27 | 7 | 66 | 0 | 79.4% | 66.0% |
| $r_{\mathrm{abstain}}$ | GPT-5.4 Nano | 100 | 40 | 52 | 8 | 0 | 43.5% | 8.0% |
| QP6 | GPT-5.6 Sol | 100 | 74 | 24 | 2 | 0 | 75.5% | 2.0% |
| QP6 | GPT-5.4 Nano | 99 | 48 | 40 | 11 | 0 | 54.5% | 11.1% |
| QP7 | GPT-5.6 Sol | 100 | 80 | 19 | 1 | 0 | 80.8% | 1.0% |
| QP7 | GPT-5.4 Nano | 100 | 50 | 47 | 3 | 0 | 51.5% | 3.0% |

## GPT-5.6 Sol minus GPT-5.4 Nano

| Condition | Δ attempted accuracy | Δ abstention rate |
|---|---:|---:|
| $r_{100}$ | +32.4 pp | -1.0 pp |
| $r_{\mathrm{abstain}}$ | +35.9 pp | +58.0 pp |
| QP6 | +21.0 pp | -9.1 pp |
| QP7 | +29.3 pp | -2.0 pp |

Note: the stored prior QP6 GPT-5.4 Nano metrics contain N=99; all other prior cells and every GPT-5.6 Sol cell contain N=100.
