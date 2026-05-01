# SWE-Bench Pro — vanilla mini-swe-agent runner

Minimal harness for running mini-swe-agent on SWE-Bench Pro instances.
No consequence-asymmetry scaffolding — that lives separately and will be
layered on top of this same driver later.

## What's here

```
swebench_pro/
├── README.md                              (this file)
├── run_mini_on_pro.py                     (driver — drives mini's agent on Pro JSONL)
├── run_smoke.sh                           (one-instance smoke test entrypoint;
│                                           runs inference + official eval)
├── configs/
│   └── swebench_pro_vanilla.yaml          (mini-swe-agent config)
├── data/
│   ├── smoke.jsonl                        (5 hand-picked Pro instances)
│   └── smoke_1.jsonl                      (just the first one)
├── scripts/                               (evaluation pipeline)
│   ├── setup_eval_repo.sh                 (clone scaleapi/SWE-bench_Pro-os)
│   ├── preds_to_eval_input.py             (preds.json -> patches_for_eval.json)
│   ├── build_eval_data.py                 (filter sweap_eval_full_v2.jsonl)
│   └── run_eval.sh                        (drive official swe_bench_pro_eval.py)
├── external/                              (gitignored; cloned upstream eval repo)
└── results/                               (created at run time, gitignored)
```

## Prerequisites

1. **Python deps**:
   ```bash
   pip install -r ../requirements.txt
   pip install -e ../evaluation/latex2sympy   # only if you also use the math evaluator
   ```
2. **Docker**: the harness needs the `docker` CLI on PATH. Verify with
   `docker --version` and `docker ps`. mini-swe-agent shells out to
   `docker run …` per instance; without Docker the smoke run will exit
   with `FileNotFoundError: 'docker'` immediately after the first
   instance starts.
3. **API key**: put `ANTHROPIC_API_KEY=...` (or `OPENAI_API_KEY`,
   `OPENROUTER_API_KEY`, …) in `../.env` at the repo root, or export
   it. mini uses `litellm` under the hood, so any provider litellm
   supports works — just match the `--model` slug to litellm's naming
   (e.g. `anthropic/...`, `openai/...`, `openrouter/...`).
4. **Disk**: each Pro instance pulls a multi-GB
   `docker.io/jefzda/sweap-images:*` image on first use. A 5-instance
   smoke can pull ~30 GB.

## Running the smoke test

```bash
bash swebench_pro/run_smoke.sh                    # 1 instance, Claude Haiku 4.5
N_INSTANCES=5 bash swebench_pro/run_smoke.sh      # all 5 smoke instances

# Override defaults via env vars:
MODEL=openai/gpt-4o-mini WORKERS=2 \
INSTANCES=swebench_pro/data/smoke.jsonl \
OUTPUT=swebench_pro/results/gpt4o_mini_smoke \
bash swebench_pro/run_smoke.sh
```

For larger runs, call the driver directly:

```bash
python swebench_pro/run_mini_on_pro.py \
    --model anthropic/claude-haiku-4-5-20251001 \
    --config swebench_pro/configs/swebench_pro_vanilla.yaml \
    --instances <your-pro-jsonl> \
    --output swebench_pro/results/<run-name> \
    --workers 4
```

The driver is **resume-aware**: re-running with the same `--output`
will skip any instance already in `preds.json`.

## What to read after a run completes

For each run, `--output <dir>` ends up containing:

| File / path | What's in it |
|---|---|
| `preds.json` | `{instance_id: {model_name_or_path, instance_id, model_patch}}`. **This is the input to the SWE-Bench Pro grader.** Empty `model_patch` means the instance failed before submission. |
| `exit_statuses.yaml` | `instances_by_exit_status: {<status>: [instance_ids...]}`. Healthy run statuses: `Submitted` (patch produced), `LimitsExceeded` (hit `step_limit` / `cost_limit`), `format_errors` (model couldn't follow the format). Anything else (`FileNotFoundError`, `RuntimeError`, …) is an infrastructure failure. |
| `minisweagent.log` | Full driver log — one line per agent step, plus container start/stop / cost-tracking messages. First place to look when something fails. |
| `<instance_id>/<instance_id>.traj.json` | Per-instance trajectory: full message history (system/user/assistant/observation) + every tool call + every observation + cumulative cost + per-step `n_calls`. The single source of truth for "what did the agent actually do on this instance". |

A successful instance trajectory typically ends with messages like
`{"role": "assistant", "content": "...", "tool_calls": [{"function": {"name": "bash", "arguments": "{\"command\": \"echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat patch.txt\"}"}}]}`
followed by a `{"role": "exit", "content": "<patch>", "extra": {"exit_status": "Submitted", "submission": "<patch>"}}`.

## Grading

Grading uses the **official** SWE-Bench Pro evaluator
(`scaleapi/SWE-bench_Pro-os`). `run_smoke.sh` runs it automatically
after inference; the grader pulls the corresponding
`docker.io/jefzda/sweap-images:*` test image, applies the patch,
runs `FAIL_TO_PASS` + `PASS_TO_PASS` test sets, and writes a
boolean per instance.

```bash
# inference + grading in one shot (default):
bash swebench_pro/run_smoke.sh --model openai/gpt-5-nano

# inference only:
bash swebench_pro/run_smoke.sh --no-eval

# grade an existing rundir (skip inference):
bash swebench_pro/run_smoke.sh --eval-only \
    --rundir swebench_pro/results/smoke_<ts> --eval-workers 4

# sanity-check the grader against the released gold patches
# (downloads ScaleAI/SWE-bench_Pro from HuggingFace; no inference):
bash swebench_pro/run_smoke.sh --gold-eval --eval-workers 4
```

The grader writes:

| File / path | What's in it |
|---|---|
| `eval/eval_results.json` | `{instance_id: bool}` — true ⇔ patch satisfies all `FAIL_TO_PASS` + `PASS_TO_PASS` tests |
| `eval/patches_for_eval.json` | normalized patches list (input to `swe_bench_pro_eval.py`) |
| `eval/eval_data.jsonl` | filtered + key-renamed slice of upstream `sweap_eval_full_v2.jsonl` (only the instance ids you ran) |
| `eval/instance_<id>/mini_stdout.log` | stdout of the test run inside the container |
| `eval/instance_<id>/mini_stderr.log` | stderr of the test run |
| `eval/instance_<id>/mini_output.json` | per-test status table (`{tests: [{name, status}]}`) |
| `eval/instance_<id>/mini_patch.diff` | the actual patch handed to `git apply` |
| `eval/instance_<id>/mini_entryscript.sh` | the script that ran inside the container |

### How the eval pipeline is wired

1. `scripts/setup_eval_repo.sh` clones
   `https://github.com/scaleapi/SWE-bench_Pro-os` into
   `external/SWE-bench_Pro-os` (gitignored).
2. `scripts/preds_to_eval_input.py` turns mini's `preds.json` into
   `eval/patches_for_eval.json` and **prepends `instance_` to ids**
   because upstream's run_scripts/, dockerfiles/, and JSONL all use
   `instance_<id>` while mini uses bare ids.
3. `scripts/build_eval_data.py` filters
   `external/SWE-bench_Pro-os/helper_code/sweap_eval_full_v2.jsonl`
   down to only the instances in `preds.json`, renames
   `FAIL_TO_PASS`/`PASS_TO_PASS` to lowercase, and JSON-encodes their
   list values (the upstream eval script `eval()`s them as strings).
4. `scripts/run_eval.sh` `cd`s into `external/SWE-bench_Pro-os` (the
   eval script reads `dockerfiles/{base,instance}_dockerfile/<iid>/Dockerfile`
   relative to cwd) and invokes `swe_bench_pro_eval.py
   --use_local_docker --dockerhub_username jefzda`.

### Caveats

* The eval harness expects a **standard `git apply`-able unified diff**.
  Some models (notably `openai/gpt-5-nano`) emit OpenAI's `*** Begin
  Patch / *** Update File: ...` "apply_patch" format, which `git apply`
  rejects — the instance will be marked `false` purely for format
  reasons. Switch to a model that emits unified diffs (Claude Haiku /
  Sonnet, Gemini Flash, GPT-5 full) or post-process `preds.json` before
  evaluation.
* `--use_local_docker` requires `docker>=6.0` (Python SDK) — already in
  `requirements.txt`. The first time you eval an instance, Docker pulls
  several GB.

## Anatomy of an instance JSONL line

Each line in `data/*.jsonl` must have at minimum:

```json
{
  "instance_id":      "qutebrowser__qutebrowser-...-v2ef375a...",
  "image_name":       "docker.io/jefzda/sweap-images:qutebrowser.qutebrowser-...",
  "problem_statement": "# Deprecated Buffer Command Still Appears...\n\n## Description\n..."
}
```

`image_name` is the docker image that gets started for the instance
(`docker run --entrypoint "" <image_name> sleep 2h`). The agent's
working directory inside the container is `/app` (set in the yaml).
`problem_statement` is rendered into `instance_template`'s `{{task}}`
jinja variable.

## Differences from the upstream `mini-extra swebench` CLI

mini-swe-agent ships its own `swebench` runner that expects the dataset
to live in HuggingFace. SWE-Bench Pro distributes JSONL, so this
driver bypasses the HF loader and feeds Pro instance dicts directly
into mini's `process_instance` building blocks (`get_sb_environment`,
`ProgressTrackingAgent`, `update_preds_file`). Everything below the
driver — the agent loop, the environment, trajectory format, cost
tracking — is unmodified upstream code.

## Differences from the vanilla mini-swe-agent `swebench.yaml`

Two changes in `configs/swebench_pro_vanilla.yaml`:

1. `environment.cwd: /app` (Pro images use `/app`; vanilla SWE-Bench
   uses `/testbed`).
2. `environment.run_args: [--entrypoint, "", --rm]` — Pro images
   default-run the test harness on container start; we override the
   entrypoint to a plain shell and rely on `sleep 2h` (mini's docker
   environment does this internally).

The model slug is intentionally **not** pinned in the yaml — supply it
via `--model` so the same config covers all providers.
