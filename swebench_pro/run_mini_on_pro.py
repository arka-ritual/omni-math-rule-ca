#!/usr/bin/env python3
"""Drive mini-swe-agent on SWE-bench Pro instances.

mini-swe-agent's built-in CLI (`mini-extra swebench …`) loads instances from
HuggingFace datasets. SWE-bench Pro is distributed as a JSONL of
instance dicts (with at least `instance_id`, `image_name`,
`problem_statement`), so we drive `ProgressTrackingAgent` directly here.

This is a **vanilla** runner — no consequence-asymmetry / abstain
machinery. It uses mini's stock `swebench.yaml` config and the standard
`submit` flow (`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat patch.txt`).

Outputs (in `--output <dir>`):

  preds.json            — `{instance_id: {model_name_or_path, instance_id,
                          model_patch}}` for every completed instance.
                          This is the exact format SWE-bench Pro's grader
                          consumes.
  exit_statuses.yaml    — per-instance exit_status as the run progresses.
  minisweagent.log      — full driver log (one line per step).
  <instance_id>/<instance_id>.traj.json — full trajectory (messages, tool
                          calls, observations, model_stats, exit_status).

Usage:
  python swebench_pro/run_mini_on_pro.py \
      --model anthropic/claude-haiku-4-5-20251001 \
      --config swebench_pro/configs/swebench_pro_vanilla.yaml \
      --instances swebench_pro/data/smoke.jsonl \
      --output swebench_pro/results/smoke \
      --workers 1
"""
import argparse
import concurrent.futures
import json
import logging
import os
import sys
from pathlib import Path

# litellm crashes when computing cost for models it doesn't have in its
# pricing registry (Qwen, custom OpenRouter, vLLM). Tell it to ignore.
os.environ.setdefault("MSWEA_COST_TRACKING", "ignore_errors")

# Load .env from the repo root BEFORE importing minisweagent / litellm
# so that ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY etc.
# are available when those libraries read os.environ at import time.
# (mini-swe-agent only loads its own ~/.config/mini-swe-agent/.env, not
# the repo's local .env — that's the gotcha behind the
# "Missing Anthropic API Key" error you'll see if you forget this.)
try:
    from dotenv import load_dotenv  # type: ignore
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_repo_root, ".env"))
except Exception:
    pass

from minisweagent.models import get_model
from minisweagent.run.benchmarks.swebench import (
    ProgressTrackingAgent,
    get_sb_environment,
    update_preds_file,
)
from minisweagent.run.benchmarks.utils.batch_progress import RunBatchProgressManager
from minisweagent.utils.log import add_file_handler

logger = logging.getLogger("minisweagent")
logger.setLevel(logging.INFO)


def process_instance(instance, model_name, config, output_path, progress_manager):
    instance_id = instance["instance_id"]
    instance_dir = output_path / instance_id
    instance_dir.mkdir(exist_ok=True, parents=True)
    (instance_dir / f"{instance_id}.traj.json").unlink(missing_ok=True)

    # Override model_name in config so get_model picks our flag value.
    model_config = dict(config.get("model", {}))
    model_config["model_name"] = model_name
    model = get_model(config=model_config)

    task = instance["problem_statement"]
    progress_manager.on_instance_start(instance_id)
    progress_manager.update_instance_status(instance_id, "Starting environment")

    agent = None
    exit_status = None
    result = ""
    extra_info = {}
    try:
        env = get_sb_environment(config, instance)
        agent = ProgressTrackingAgent(
            model, env,
            progress_manager=progress_manager,
            instance_id=instance_id,
            **config.get("agent", {}),
        )
        info = agent.run(task)
        exit_status = info.get("exit_status")
        result = info.get("submission") or ""
    except Exception as e:
        logger.error(f"Error processing instance {instance_id}: {e}", exc_info=True)
        exit_status, result = type(e).__name__, ""
        import traceback
        extra_info = {"traceback": traceback.format_exc(), "exception_str": str(e)}
    finally:
        try:
            if agent is not None:
                agent.save(
                    instance_dir / f"{instance_id}.traj.json",
                    {
                        "info": {
                            "exit_status": exit_status,
                            "submission": result,
                            **extra_info,
                        },
                        "instance_id": instance_id,
                    },
                )
        except Exception:
            pass

    update_preds_file(output_path / "preds.json", instance_id, model_name, result)
    progress_manager.on_instance_end(instance_id, exit_status)
    return exit_status


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--model", required=True,
                    help="Model id passed to litellm (e.g. "
                         "'anthropic/claude-haiku-4-5-20251001', "
                         "'openai/gpt-4o-mini', "
                         "'openrouter/qwen/qwen3.5-9b').")
    ap.add_argument("--config", required=True,
                    help="Path to mini-swe-agent yaml config (see "
                         "swebench_pro/configs/swebench_pro_vanilla.yaml)")
    ap.add_argument("--output", required=True,
                    help="Output directory (created if missing)")
    ap.add_argument("--instances", required=True,
                    help="Path to a JSONL of SWE-Bench-Pro instances. "
                         "Each line must have at minimum: instance_id, "
                         "image_name, problem_statement.")
    ap.add_argument("--workers", type=int, default=1,
                    help="Parallel docker containers (default: 1)")
    ap.add_argument("--limit", type=int, default=0,
                    help="If >0, sample N instances (shuffle-then-slice "
                         "with --seed). With a fixed seed, increasing N "
                         "is a strict superset of the smaller N — so "
                         "resuming a run with a larger --limit picks up "
                         "where the smaller one left off.")
    ap.add_argument("--seed", type=int, default=100,
                    help="Random seed for shuffle-and-slice sampling "
                         "(default: 100, mirrors inference_api.py).")
    args = ap.parse_args()

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    add_file_handler(output_path / "minisweagent.log")

    import yaml
    config = yaml.safe_load(open(args.config))

    instances = []
    with open(args.instances) as f:
        for line in f:
            line = line.strip()
            if line:
                instances.append(json.loads(line))
    total_loaded = len(instances)
    # Shuffle-and-slice sampling. With a fixed seed, the prefix of the
    # shuffled list is stable across runs, so a run with --limit=20 is
    # a strict subset of a run with --limit=100. Combined with the
    # resume logic below, this means: re-running with a larger --limit
    # only does the *additional* instances; re-running with a smaller
    # --limit does nothing if those were already processed.
    import random
    rng = random.Random(args.seed)
    rng.shuffle(instances)
    if args.limit > 0:
        instances = instances[: args.limit]
    logger.info(f"Loaded {total_loaded} instances from {args.instances}; "
                f"sampled {len(instances)} (seed={args.seed}, limit={args.limit or 'all'})")

    # Resume: skip instances already in preds.json.
    preds_path = output_path / "preds.json"
    if preds_path.exists():
        try:
            existing = set(json.loads(preds_path.read_text()).keys())
            before = len(instances)
            instances = [i for i in instances if i["instance_id"] not in existing]
            if len(instances) != before:
                logger.info(f"Resume: skipping {before - len(instances)} instances "
                            f"already in {preds_path}")
        except Exception as e:
            logger.warning(f"Couldn't read existing preds.json ({e}); will rerun all.")

    if not instances:
        logger.info("Nothing to do.")
        return

    progress_manager = RunBatchProgressManager(
        len(instances), output_path / "exit_statuses.yaml"
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [
            ex.submit(process_instance, inst, args.model, config, output_path, progress_manager)
            for inst in instances
        ]
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error(f"future error: {e}")
    if hasattr(progress_manager, "print_report"):
        progress_manager.print_report()


if __name__ == "__main__":
    main()
