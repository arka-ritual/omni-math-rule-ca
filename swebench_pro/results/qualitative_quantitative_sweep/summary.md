# Qualitative + quantitative prompt sweep (SWE-Bench Pro)

Source: `swebench_pro/results/openai_gpt-5.4-nano_int5_<config>_n100/`
(`exit_statuses.yaml` + `eval/eval_results.json`).
Single model: `gpt-5.4-nano` (OpenAI, reasoning effort = `medium`),
`mini-swe-agent` harness with the `int5` config — vanilla submit flow plus
the `exit_abstain` tool, with the consequence framing in the system prompt
(see `swebench_pro/interventions/prompts.py::build_system_template` for the
exact rendered text).

N=100 instances per cell; same shuffle-and-slice seed (`100`) as
`run_baselines.sh`. `--workers 25 --eval-workers 25 --api-timeout 600`.

Counts use the same buckets as `swebench_pro/results/interventions_summary.md`:

- `c` = `eval_results.json` resolved (correct submission)
- `i` = `Submitted` exit_status − `c` (graded as not-resolved, plus the rare
  `Submitted` instance whose patch fails to grade — counted as incorrect)
- `a` = `Abstained` exit_status (model ran `exit_abstain`)
- `f` = runtime failure (`LimitsExceeded` + `LoopDetected`, no patch)

`total acc` = `c / 100`. `abst rate` = `a / 100`. Δ is `total acc` − baseline
total acc in percentage points; baseline anchor is the `gpt-5.4-nano` vanilla
no-consequence run (`35.0%`, see
`swebench_pro/results/interventions_summary.md`).

## Qualitative prompts (QP1–QP7)

| Prompt | total acc | Abst rate | Δ vs baseline | Counts (c/i/a/f, n) |
|---|---:|---:|---:|---|
| QP1 (`max-correct, no-wrong`)        | 28.0% | 0.0% |  −7.0 | c28 / i43 / a0 / f29, n=100 |
| QP2 (`production / company-ending`)  | 26.0% | 0.0% |  −9.0 | c26 / i49 / a0 / f25, n=100 |
| QP3 (`career-fired`)                 | 29.0% | 0.0% |  −6.0 | c29 / i50 / a0 / f21, n=100 |
| QP4 (`fired-if-wrong`)               | **32.0%** | 0.0% |  −3.0 | c32 / i45 / a0 / f23, n=100 |
| QP5 (`decommissioned`)               | 28.0% | 0.0% |  −7.0 | c28 / i53 / a0 / f19, n=100 |
| QP6 (`team-lead-rubric`)             | 26.0% | 0.0% |  −9.0 | c26 / i45 / a0 / f29, n=100 |
| QP7 (`humanity-extinction`)          | **35.0%** | 0.0% |  +0.0 | c35 / i47 / a0 / f18, n=100 |

## Quantitative prompts

Rubric format: `(r_correct, r_abstain, r_incorrect)`.

| Rubric | total acc | Abst rate | Δ vs baseline | Counts (c/i/a/f, n) |
|---|---:|---:|---:|---|
| `(+1,  0,   −1)`   | 28.0% | 0.0% |  −7.0 | c28 / i45 / a0 / f27, n=100 |
| `(+1,  0,   −5)`   | 27.0% | 0.0% |  −8.0 | c27 / i49 / a0 / f24, n=100 |
| `(+1,  0,  −10)`   | 36.0% | 0.0% |  +1.0 | c36 / i44 / a0 / f20, n=100 |
| `(−1, +10, −10)`   | **32.0%** | 0.0% |  −3.0 | c32 / i45 / a0 / f23, n=100 |
