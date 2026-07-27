# CoT-removal pilot summary

Manual visible-output coding complete: **yes**

| Model | QP | Condition | Boxed | Explicit abstain | As-prompted abstain | No box | Visible-direct | Provider reasoning | Answered | Correct | Selective accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 0/5 | 5 | 3 | 60.0% |
| Claude Haiku 4.5 | QP6 | no_cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | 0.0% | 0/5 | 5 | 4 | 80.0% |
| Claude Haiku 4.5 | QP7 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 0/5 | 5 | 3 | 60.0% |
| Claude Haiku 4.5 | QP7 | no_cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | 0.0% | 0/5 | 5 | 4 | 80.0% |
| DeepSeek V4 Pro | QP6 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 5/5 | 5 | 5 | 100.0% |
| DeepSeek V4 Pro | QP6 | no_cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | 100.0% | 5/5 | 5 | 5 | 100.0% |
| DeepSeek V4 Pro | QP7 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 5/5 | 5 | 5 | 100.0% |
| DeepSeek V4 Pro | QP7 | no_cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | 80.0% | 5/5 | 5 | 5 | 100.0% |
| Gemini 3.1 Flash Lite | QP6 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 0/5 | 5 | 4 | 80.0% |
| Gemini 3.1 Flash Lite | QP6 | no_cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | 100.0% | 0/5 | 5 | 1 | 20.0% |
| Gemini 3.1 Flash Lite | QP7 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 0/5 | 5 | 4 | 80.0% |
| Gemini 3.1 Flash Lite | QP7 | no_cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | 100.0% | 0/5 | 5 | 1 | 20.0% |
| GPT-5.4 Nano | QP6 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 0/5 | 5 | 2 | 40.0% |
| GPT-5.4 Nano | QP6 | no_cot | 5/5 (100.0%) | 1/5 (20.0%) | 1/5 (20.0%) | 0/5 | 40.0% | 0/5 | 4 | 2 | 50.0% |
| GPT-5.4 Nano | QP7 | cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | — | 0/5 | 5 | 3 | 60.0% |
| GPT-5.4 Nano | QP7 | no_cot | 5/5 (100.0%) | 1/5 (20.0%) | 1/5 (20.0%) | 0/5 | 80.0% | 0/5 | 4 | 1 | 25.0% |
| Qwen3.5 397B A17B | QP6 | cot | 4/5 (80.0%) | 0/5 (0.0%) | 1/5 (20.0%) | 1/5 | — | 5/5 | 4 | 4 | 100.0% |
| Qwen3.5 397B A17B | QP6 | no_cot | 5/5 (100.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 | 40.0% | 5/5 | 5 | 5 | 100.0% |
| Qwen3.5 397B A17B | QP7 | cot | 4/5 (80.0%) | 0/5 (0.0%) | 1/5 (20.0%) | 1/5 | — | 5/5 | 4 | 4 | 100.0% |
| Qwen3.5 397B A17B | QP7 | no_cot | 4/5 (80.0%) | 0/5 (0.0%) | 0/5 (0.0%) | 1/5 | 20.0% | 5/5 | 4 | 4 | 100.0% |

## No-CoT minus CoT deltas

| Model | QP | Boxing | Explicit abstention | As-prompted abstention | Selective accuracy |
|---|---:|---:|---:|---:|---:|
| Claude Haiku 4.5 | QP6 | +0.0 pp | +0.0 pp | +0.0 pp | +20.0 pp |
| Claude Haiku 4.5 | QP7 | +0.0 pp | +0.0 pp | +0.0 pp | +20.0 pp |
| DeepSeek V4 Pro | QP6 | +0.0 pp | +0.0 pp | +0.0 pp | +0.0 pp |
| DeepSeek V4 Pro | QP7 | +0.0 pp | +0.0 pp | +0.0 pp | +0.0 pp |
| Gemini 3.1 Flash Lite | QP6 | +0.0 pp | +0.0 pp | +0.0 pp | -60.0 pp |
| Gemini 3.1 Flash Lite | QP7 | +0.0 pp | +0.0 pp | +0.0 pp | -60.0 pp |
| GPT-5.4 Nano | QP6 | +0.0 pp | +20.0 pp | +20.0 pp | +10.0 pp |
| GPT-5.4 Nano | QP7 | +0.0 pp | +20.0 pp | +20.0 pp | -35.0 pp |
| Qwen3.5 397B A17B | QP6 | +20.0 pp | +0.0 pp | -20.0 pp | +0.0 pp |
| Qwen3.5 397B A17B | QP7 | +0.0 pp | +0.0 pp | -20.0 pp | +0.0 pp |
