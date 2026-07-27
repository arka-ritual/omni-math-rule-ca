# Omni-MATH main-body rollouts — DeepSeek V4 Pro, Qwen3.5 397B, Claude Haiku 4.5, Gemini 3.1 Flash-Lite

_Assembled 2026-07-27 from gs://conseq_asym (Paperspace VM backups) for the consequence-awareness rebuttal._

## Layout

One directory per model x setting, named like Louai's GPT-5.4 nano sweep: `<model>_quant_<s_c>_<s_a>_<s_i>` for quantitative rubrics and `<model>_QPn` for qualitative prompts. Mapping to internal rubric ids: t1=quant_1_0_-1, t5=-5, t10=-10, t25=-25, t100=-100, scaled=quant_10_0_-250, abstain=quant_-1_10_-10, qual_pN=QPN.

Each row: Omni-MATH problem (`problem`, `solution`, `answer`, `domain`, `difficulty`) + `model_generation` (raw rollout), `prompt_mode`, `api_meta`, `generation_time_s`.

**When a cell has two timestamped files, they are shards/re-runs of the same cell — union rows and dedupe by `idx`.** Files named `*_consolidated.jsonl` are the canonical per-cell files from the VM's qq_result tree.

`canary_t1` dirs are tiny (1-2 rows) canary/smoke tests, NOT full runs.

## Provenance

- `gs://conseq_asym/code/exp22_paper_full_rubrics/results/math/<rid>/<fam>_<rid>_<ts>.jsonl`
- `gs://conseq_asym/baseline/qq_result/main_body/math/qual/results/qual_p{4..7}/<fam>.jsonl` (the `*_consolidated.jsonl` files)
- Prompts + graded per-cell metrics: see `reference_prompts_and_curves/` (quant_curves.json / qual_curves.json match the paper tables exactly — verified deepseek t1 91.4, qwen397b t1 86.9, haiku t1 68.7, gemini_lite t1 79.0).

## MISSING cells (not in the GCS backup — exist only on the powered-off Paperspace VMs)

| model | missing settings | where they live |
|---|---|---|
| claude-haiku-4.5 | quant_1_0_-1 (t1), quant_1_0_-100 (t100), QP1, QP2, QP3 | exp21c legacy tree on the ps hosts (haiku inherited t1/t100 + qual p1-p3 from exp21c per run_main_math_quant.sh) |
| qwen3.5-397b | quant_1_0_-1/-5/-10/-25/-100 (full t-series), QP1, QP2, QP3 | qq_result/size_family/qwen/math/results/ on the ps hosts (qwen397b inherited t1-t100 from size_family) |

Graded metrics for those missing cells ARE available in reference_prompts_and_curves/quant_curves.json and qual_curves.json (the grader ran on-VM where the files exist). To recover the raw rollouts, boot the Paperspace machines (console.paperspace.com) and pull the paths above.

## Row counts

```
claude-haiku-4.5_canary_t1                    1 rows  1 file(s)
claude-haiku-4.5_QP4                        100 rows  1 file(s)
claude-haiku-4.5_QP5                        100 rows  1 file(s)
claude-haiku-4.5_QP6                        100 rows  1 file(s)
claude-haiku-4.5_QP7                        100 rows  1 file(s)
claude-haiku-4.5_quant_-1_10_-10            100 rows  1 file(s)
claude-haiku-4.5_quant_1_0_-10              100 rows  1 file(s)
claude-haiku-4.5_quant_1_0_-25              100 rows  1 file(s)
claude-haiku-4.5_quant_1_0_-5               100 rows  1 file(s)
claude-haiku-4.5_quant_10_0_-250            100 rows  1 file(s)
deepseek-v4-pro_canary_t1                     2 rows  2 file(s)
deepseek-v4-pro_QP1                         100 rows  1 file(s)
deepseek-v4-pro_QP2                         100 rows  1 file(s)
deepseek-v4-pro_QP3                         100 rows  1 file(s)
deepseek-v4-pro_QP4                         194 rows  2 file(s)
deepseek-v4-pro_QP5                         200 rows  2 file(s)
deepseek-v4-pro_QP6                         200 rows  2 file(s)
deepseek-v4-pro_QP7                         197 rows  2 file(s)
deepseek-v4-pro_quant_-1_10_-10             100 rows  1 file(s)
deepseek-v4-pro_quant_1_0_-1                100 rows  1 file(s)
deepseek-v4-pro_quant_1_0_-10               100 rows  1 file(s)
deepseek-v4-pro_quant_1_0_-100              100 rows  1 file(s)
deepseek-v4-pro_quant_1_0_-25               100 rows  1 file(s)
deepseek-v4-pro_quant_1_0_-5                100 rows  1 file(s)
deepseek-v4-pro_quant_10_0_-250             100 rows  1 file(s)
gemini-3.1-flash-lite_canary_t1               2 rows  2 file(s)
gemini-3.1-flash-lite_QP1                   200 rows  2 file(s)
gemini-3.1-flash-lite_QP2                   200 rows  2 file(s)
gemini-3.1-flash-lite_QP3                   200 rows  2 file(s)
gemini-3.1-flash-lite_QP4                   100 rows  1 file(s)
gemini-3.1-flash-lite_QP5                   100 rows  1 file(s)
gemini-3.1-flash-lite_QP6                   100 rows  1 file(s)
gemini-3.1-flash-lite_QP7                   100 rows  1 file(s)
gemini-3.1-flash-lite_quant_-1_10_-10       200 rows  2 file(s)
gemini-3.1-flash-lite_quant_1_0_-1          200 rows  2 file(s)
gemini-3.1-flash-lite_quant_1_0_-10         200 rows  2 file(s)
gemini-3.1-flash-lite_quant_1_0_-100        200 rows  2 file(s)
gemini-3.1-flash-lite_quant_1_0_-25         200 rows  2 file(s)
gemini-3.1-flash-lite_quant_1_0_-5          200 rows  2 file(s)
gemini-3.1-flash-lite_quant_10_0_-250       200 rows  2 file(s)
qwen3.5-397b_canary_t1                        1 rows  1 file(s)
qwen3.5-397b_QP4                            200 rows  2 file(s)
qwen3.5-397b_QP5                            196 rows  2 file(s)
qwen3.5-397b_QP6                            200 rows  2 file(s)
qwen3.5-397b_QP7                            198 rows  2 file(s)
qwen3.5-397b_quant_-1_10_-10                100 rows  1 file(s)
qwen3.5-397b_quant_10_0_-250                100 rows  1 file(s)
```
