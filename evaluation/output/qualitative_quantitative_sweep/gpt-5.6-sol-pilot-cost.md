# GPT-5.6 Sol pilot cost estimate

Pilot: 5 Omni-MATH questions per condition (20 calls total), OpenRouter model `openai/gpt-5.6-sol`, upstream `openai`, reasoning effort `high`, temperature omitted, max output 64,000 tokens, seed 100.

| Condition | Calls | Input tokens | Output tokens | Reasoning tokens | Actual cost | Mean/call | Projected N=100 |
|---|---:|---:|---:|---:|---:|---:|---:|
| $r_{100}$ | 5 | 781 | 5,975 | 4,815 | $0.183155 | $0.036631 | $3.66 |
| $r_{\mathrm{abstain}}$ | 5 | 781 | 1,413 | 1,203 | $0.046295 | $0.009259 | $0.93 |
| QP6 | 5 | 926 | 7,974 | 6,552 | $0.243850 | $0.048770 | $4.88 |
| QP7 | 5 | 776 | 5,796 | 4,491 | $0.177760 | $0.035552 | $3.56 |
| **Total** | **20** | **3,264** | **21,158** | **17,061** | **$0.651060** | — | **$13.02** |

Linear projection for the remaining 95 calls per condition: **$12.37**. The projection uses exact per-request OpenRouter charges from this pilot; the realized cost can vary with response length.

## Pilot outcomes

| Condition | Correct | Incorrect | Abstained | Indeterminate | Attempted accuracy |
|---|---:|---:|---:|---:|---:|
| $r_{100}$ | 5 | 0 | 0 | 0 | 100.0% |
| $r_{\mathrm{abstain}}$ | 2 | 0 | 3 | 0 | 100.0% |
| QP6 | 3 | 2 | 0 | 0 | 60.0% |
| QP7 | 5 | 0 | 0 | 0 | 100.0% |

Pilot sample IDs (shared by all four conditions): `539, 903, 1464, 2279, 2637`.
