# Per-question cost + token estimate (QP7 framing)

Average of the first 2 instances per cell. Costs computed via
`litellm.cost_per_token` using the same pricing registry that
populates `info.model_stats.instance_cost` in SWE-Pro trajectories.

- **omni-math**: token counts read directly from
  `inference/results/interventions/<model>_int1_QP7.jsonl`
  (single API call per question, QP7 framing in system prompt).
- **swe-pro**: tokens summed across all assistant turns'
  `usage.prompt_tokens` / `usage.completion_tokens` in
  `<rundir>/instance_<id>/instance_<id>.traj.json`.
  `litellm $` is the value litellm itself recorded in
  `info.model_stats.instance_cost`; `recomputed $` is what we get
  from raw token counts × `cost_per_token`. Small disagreements
  are expected when prompt caching or cache_creation tokens were
  involved (litellm prices those at a discount).

Per-1M-token rates (from `litellm.cost_per_token`):

| Model | input / 1M | output / 1M |
|---|---:|---:|
| Opus 4.7 | $5.00 | $25.00 |
| Opus 4.6 | $5.00 | $25.00 |
| Sonnet 4.6 | $3.00 | $15.00 |
| GPT 5.4 | $5.00 | $22.50 |
| GPT 5.4 Mini | $0.75 | $4.50 |
| Gemini 3.1 Pro Preview | $4.00 | $18.00 |
| Haiku 4.5 | $1.00 | $5.00 |
| GPT 5.4 Nano | $0.20 | $1.25 |
| Gemini 3 Flash | $0.50 | $3.00 |
| Gemini 3.1 Flash-Lite | $0.25 | $1.50 |

## Omni-MATH-Rule (QP7, single-call)

| Model | n | input tokens (avg) | output tokens (avg) | cost / question (avg) |
|---|---:|---:|---:|---:|
| Opus 4.7 | 2 | 353 | 141 | $0.0053 |
| Opus 4.6 | 2 | 255 | 728 | $0.0195 |
| Sonnet 4.6 | 2 | 255 | 412 | $0.0070 |
| GPT 5.4 | 2 | 230 | 300 | $0.0051 |
| GPT 5.4 Mini | 2 | 230 | 368 | $0.0018 |
| Gemini 3.1 Pro Preview | 2 | 220 | 1,105 | $0.0137 |
| Haiku 4.5 | 2 | 226 | 306 | $0.0018 |
| GPT 5.4 Nano | 2 | 226 | 170 | $0.0003 |
| Gemini 3 Flash | 2 | 221 | 328 | $0.0011 |
| Gemini 3.1 Flash-Lite | 2 | 205 | 158 | $0.0003 |

## SWE-Bench Pro (QP7 / int1, full agent loop)

Notes:
- For Anthropic models, `recomputed $` is a *flat-rate* upper bound — it ignores prompt-cache discounts. The `litellm $` column (taken straight from `info.model_stats.instance_cost`) accounts for cached / cache-creation tokens and is the actual billed amount.
- Rows marked † are interpolated from a sibling model's token usage profile, repriced at this model's per-token rates. The live run for that cell either had no recoverable trajectory data or hit a degenerate exit (e.g. LimitsExceeded with no tool calls). See the source-files block for details.

| Model | n | input tokens (avg) | output tokens (avg) | recomputed $/inst | litellm $/inst |
|---|---:|---:|---:|---:|---:|
| Opus 4.7 | 2 | 469,373 | 7,784 | $2.5415 | $0.5779 |
| Opus 4.6 | 2 | 1,721,518 | 11,452 | $8.8939 | $1.4026 |
| Sonnet 4.6 | 2 | 1,130,050 | 10,708 | $3.5508 | $0.6469 |
| GPT 5.4 | 2 | 3,094,848 | 18,326 | $15.8866 | $1.2292 |
| GPT 5.4 Mini† | 2 | 3,094,848 | 18,326 | $2.4036 | $0.1860 |
| Gemini 3.1 Pro Preview | 2 | 432,066 | 14,116 | $1.9824 | $0.5467 |
| Haiku 4.5 | 2 | 2,037,686 | 15,280 | $2.1141 | $0.3534 |
| GPT 5.4 Nano | 2 | 400000 | 8000 | - | $0.05 |
| Gemini 3 Flash | 2 | 1,110,694 | 49,316 | $0.7033 | $0.3207 |
| Gemini 3.1 Flash-Lite | 2 | 468000 | 5000 | - | $0.05 |

## Source files (per-question detail)

### Opus 4.7
- omni-math: `inference/results/interventions/anthropic_claude-opus-4.7_int1_QP7.jsonl` — per-item `(in, out, cost)`: (326, 69, $0.0034), (380, 213, $0.0072)
- swe-pro:   `swebench_pro/results/openrouter_anthropic_claude-opus-4.7_int1_qp7_n2` — per-item `(in, out, recomputed_cost, litellm_cost)`: (568,914, 9,986, $3.0942, $0.6994), (369,832, 5,583, $1.9887, $0.4564)

### Opus 4.6
- omni-math: `inference/results/interventions/anthropic_claude-opus-4.6_int1_QP7.jsonl` — per-item `(in, out, cost)`: (235, 159, $0.0052), (275, 1,297, $0.0338)
- swe-pro:   `swebench_pro/results/openrouter_anthropic_claude-opus-4.6_int1_qp7_n2` — per-item `(in, out, recomputed_cost, litellm_cost)`: (2,192,304, 12,567, $11.2757, $1.7195), (1,250,732, 10,336, $6.5121, $1.0856)

### Sonnet 4.6
- omni-math: `inference/results/interventions/anthropic_claude-sonnet-4.6_int1_QP7.jsonl` — per-item `(in, out, cost)`: (235, 64, $0.0017), (275, 761, $0.0122)
- swe-pro:   `swebench_pro/results/openrouter_anthropic_claude-sonnet-4.6_int1_qp7_n2` — per-item `(in, out, recomputed_cost, litellm_cost)`: (702,930, 9,531, $2.2518, $0.4469), (1,557,170, 11,886, $4.8498, $0.8469)

### GPT 5.4
- omni-math: `inference/results/interventions/gpt-5.4_int1_QP7.jsonl` — per-item `(in, out, cost)`: (216, 127, $0.0024), (245, 474, $0.0077)
- swe-pro:   `swebench_pro/results/openai_gpt-5.4_int1_qp7_n2` — per-item `(in, out, recomputed_cost, litellm_cost)`: (2,473,229, 14,564, $12.6938, $1.0205), (3,716,468, 22,087, $19.0793, $1.4378)

### GPT 5.4 Mini
- omni-math: `inference/results/interventions/gpt-5.4-mini_int1_QP7.jsonl` — per-item `(in, out, cost)`: (216, 119, $0.0007), (245, 616, $0.0030)
- swe-pro:   **interpolated** from GPT 5.4 — repriced that model's avg (3,094,848 in, 18,326 out) at GPT 5.4 Mini's per-token rate. Live run produced no usable trajectories (model couldn't emit tool calls and hit LimitsExceeded with $0 recorded by litellm).

### Gemini 3.1 Pro Preview
- omni-math: `inference/results/interventions/google_gemini-3.1-pro-preview_int1_QP7.jsonl` — per-item `(in, out, cost)`: (207, 720, $0.0091), (233, 1,490, $0.0183)
- swe-pro:   `swebench_pro/results/openrouter_google_gemini-3.1-pro-preview_int1_qp7_n2` — per-item `(in, out, recomputed_cost, litellm_cost)`: (503,819, 22,960, $2.4286, $0.7085), (360,313, 5,272, $1.5361, $0.3850)

### Haiku 4.5
- omni-math: `inference/results/interventions/claude-haiku-4-5_int1_QP7.jsonl` — per-item `(in, out, cost)`: (232, 271, $0.0016), (219, 341, $0.0019)
- swe-pro:   `swebench_pro/results/anthropic_claude-haiku-4-5_int1_qp7_n100` — per-item `(in, out, recomputed_cost, litellm_cost)`: (805,163, 11,790, $0.8641, $0.2008), (3,270,209, 18,771, $3.3641, $0.5060)

### GPT 5.4 Nano
- omni-math: `inference/results/interventions/gpt-5.4-nano_int1_QP7.jsonl` — per-item `(in, out, cost)`: (216, 139, $0.0002), (236, 202, $0.0003)

### Gemini 3 Flash
- omni-math: `inference/results/interventions/google_gemini-3-flash-preview_int1_QP7.jsonl` — per-item `(in, out, cost)`: (207, 136, $0.0005), (235, 520, $0.0017)
- swe-pro:   `swebench_pro/results/gemini_gemini-3-flash-preview_int1_qp7_n2` — per-item `(in, out, recomputed_cost, litellm_cost)`: (856,409, 22,904, $0.4969, $0.1911), (1,364,978, 75,727, $0.9097, $0.4502)

### Gemini 3.1 Flash-Lite
- omni-math: `inference/results/interventions/gemini-3.1-flash-lite-preview_int1_QP7.jsonl` — per-item `(in, out, cost)`: (203, 139, $0.0003), (207, 177, $0.0003)

## Filling in missing rows

These cells have no QP7 data on disk yet. Each command runs only 2 questions/instances per cell, which is enough to populate the averages above when this script is re-run. Provider+model ids are best-guesses; double-check them against the live API before kicking off.

### SWE-Bench Pro (`swebench_pro/run.sh`, int1 / qp7, --n 2):

```bash
# GPT 5.4 Nano
bash swebench_pro/run.sh \
  --model openai/gpt-5.4-nano \
  --intervention 1 --prompt-config qp7 \
  --n 2 --workers 2 --eval-workers 2 \
  --reasoning-effort medium --no-eval

# Gemini 3.1 Flash-Lite
bash swebench_pro/run.sh \
  --model gemini/gemini-3.1-flash-lite-preview \
  --intervention 1 --prompt-config qp7 \
  --n 2 --workers 2 --eval-workers 2 \
  --reasoning-effort medium --no-eval

```

After the runs finish, re-run `python scripts/cost_estimate.py` to refresh this file.

