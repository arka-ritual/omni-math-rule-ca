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
import datetime
import json
import logging
import os
import subprocess
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
from minisweagent.run.benchmarks.swebench import update_preds_file
from minisweagent.run.benchmarks.utils.batch_progress import RunBatchProgressManager
from minisweagent.utils.log import add_file_handler

# Local intervention package (kept in this repo, separate from the upstream
# mini-swe-agent install).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from swebench_pro.interventions import (  # noqa: E402
    DockerEnvironmentWithAbstain,
    ResumableProgressAgent,
    build_system_template,
    build_reveal_text,
    build_instance_template,
    render_install_script,
)

logger = logging.getLogger("minisweagent")
logger.setLevel(logging.INFO)


# ---- Reasoning-effort -> per-family model_kwargs ---------------------------
# litellm exposes a unified `reasoning_effort` parameter for OpenAI o-series,
# Gemini 2.x+, DeepSeek R1, and a few others. Anthropic, however, requires
# `thinking={type: enabled, budget_tokens: N}` directly (litellm has been
# inconsistent about translating reasoning_effort -> thinking for Claude;
# aysm-ca's overlay comments warn it gets forwarded as extra_body and rejected).
# Qwen on OpenRouter only accepts a boolean `enable_thinking` knob with no level.
#
# Mapping table (effort -> per-family knob value):
#
#   effort   | Anthropic budget_tokens | OpenAI/Gemini/DeepSeek reasoning_effort | Qwen enable_thinking
#   ---------+-------------------------+-----------------------------------------+---------------------
#   none     | (omit)                  | "none" / (omit)                         | false
#   low      | 4096                    | "low"                                   | true
#   medium   | 8000                    | "medium"                                | true
#   high     | 16000                   | "high"                                  | true
#   xhigh    | 32000                   | "xhigh"                                 | true
#
# Budget choice for Anthropic medium: 8000 mirrors aysm-ca's haiku overlay
# (see aysm-ca/exp21c_swebenchpro_quantitative/swe_agent_configs/claude_haiku_overlay.yaml).
_ANTHROPIC_BUDGET_BY_EFFORT = {
    "none": None,
    "low": 4096,
    "medium": 8000,
    "high": 16000,
    "xhigh": 32000,
}


def _model_family(model_name: str) -> str:
    """Classify the model_name into one of:
       'anthropic', 'openai', 'gemini', 'qwen', 'deepseek', 'unknown'.
    Used only to pick the right reasoning-effort knob shape."""
    m = model_name.lower()
    if m.startswith("anthropic/") or m.startswith("openrouter/anthropic/"):
        return "anthropic"
    if m.startswith("openai/") or m.startswith("openrouter/openai/"):
        return "openai"
    if m.startswith("gemini/") or m.startswith("openrouter/google/"):
        return "gemini"
    if "/qwen/" in m or m.startswith("qwen/"):
        return "qwen"
    if "/deepseek/" in m or m.startswith("deepseek/"):
        return "deepseek"
    return "unknown"


def inject_reasoning_kwargs(model_name: str, effort: str, model_kwargs: dict) -> dict:
    """Mutate `model_kwargs` in place to enable `effort`-level reasoning for
    `model_name`. Returns the mutated dict for convenience.

    The shape of the knob depends on the model family — see the table at the
    top of this module. Unknown families log a warning and are left unchanged
    (with `drop_params: true` already in the config, an unknown model that
    doesn't accept the standard reasoning_effort param would silently drop it,
    so explicit family detection is safer than blindly setting it).
    """
    if effort == "none":
        return model_kwargs
    family = _model_family(model_name)
    if family == "anthropic":
        budget = _ANTHROPIC_BUDGET_BY_EFFORT.get(effort)
        if budget is None:
            logger.warning(f"Unknown reasoning effort {effort!r}; leaving Anthropic thinking unset.")
            return model_kwargs
        model_kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        # Anthropic's extended-thinking docs require temperature=1.0 when thinking
        # is enabled; otherwise the API returns 400. Override silently — the
        # intervention runs already use temperature=0.0 by default, which would
        # break here.
        model_kwargs["temperature"] = 0.0
        # max_tokens must be > budget_tokens (thinking + completion). Bump if the
        # current setting is too low. Default mini config doesn't set max_tokens
        # so this is usually a no-op, but cheap to enforce.
        existing_max = model_kwargs.get("max_tokens")
        min_max = budget + 8000
        if existing_max is None or existing_max < min_max:
            model_kwargs["max_tokens"] = min_max
        logger.info(f"[reasoning] Anthropic: thinking.budget_tokens={budget}, temperature=1.0")
    elif family in ("openai", "gemini", "deepseek"):
        model_kwargs["reasoning_effort"] = effort
        logger.info(f"[reasoning] {family}: reasoning_effort={effort!r}")
    elif family == "qwen":
        # Qwen has no effort levels — just enable_thinking (boolean). For any
        # non-"none" effort we turn it on.
        eb = dict(model_kwargs.get("extra_body") or {})
        eb["enable_thinking"] = True
        model_kwargs["extra_body"] = eb
        logger.info(f"[reasoning] qwen: extra_body.enable_thinking=true (no level support; effort={effort!r} ignored)")
    else:
        logger.warning(
            f"[reasoning] Unknown model family for {model_name!r}; can't infer "
            f"reasoning-effort knob shape. Set it manually in the yaml's "
            f"model.model_kwargs if needed."
        )
    return model_kwargs


def _build_environment(
    config: dict,
    instance: dict,
    intervention_cfg: dict,
    *,
    reuse_container_id: str | None = None,
):
    """Build a DockerEnvironmentWithAbstain for a Pro instance and, if
    intervention id != 0 and we're starting fresh, install the
    intervention tools into the container.

    `reuse_container_id` activates the resume path: skip `docker run`,
    reattach to an existing container, and skip tool install (the tools
    were installed by the previous (interrupted) run).

    Returns the env. We always use DockerEnvironmentWithAbstain (it's a
    superset of DockerEnvironment, so it's safe even for the vanilla case).
    """
    env_cfg = dict(config.get("environment", {}))
    env_cfg.pop("environment_class", None)  # we instantiate the class directly
    env_cfg["image"] = instance["image_name"]

    intv = int(intervention_cfg.get("id", 0))

    # Bake CA_* environment vars into the container so the tool scripts can
    # see them (rubric values, prompt config, intervention id).
    extra_env = dict(env_cfg.get("env", {}))
    if intv != 0:
        extra_env.update({
            "CA_INTERVENTION": str(intv),
            "CA_PROMPT_CONFIG": str(intervention_cfg.get("prompt_config", "none")),
            "CA_RC": str(intervention_cfg.get("rubric_correct", "")),
            "CA_RI": str(intervention_cfg.get("rubric_incorrect", "")),
            "CA_RA": str(intervention_cfg.get("rubric_abstain", "")),
        })
    env_cfg["env"] = extra_env

    env = DockerEnvironmentWithAbstain(
        use_intervention_markers=(intv != 0),
        reuse_container_id=reuse_container_id,
        **env_cfg,
    )

    if intv != 0 and not reuse_container_id:
        reveal_text = build_reveal_text(
            intervention=intv,
            prompt_config=intervention_cfg.get("prompt_config", "none"),
            rubric_correct=intervention_cfg.get("rubric_correct"),
            rubric_incorrect=intervention_cfg.get("rubric_incorrect"),
            rubric_abstain=intervention_cfg.get("rubric_abstain"),
        )
        installer = render_install_script(
            intervention=intv,
            reveal_text=reveal_text,
            rubric_correct=intervention_cfg.get("rubric_correct"),
            rubric_incorrect=intervention_cfg.get("rubric_incorrect"),
            rubric_abstain=intervention_cfg.get("rubric_abstain"),
            prompt_config=intervention_cfg.get("prompt_config", "none"),
            qual_text=intervention_cfg.get("qual_text", ""),
        )
        out = env.execute({"command": installer}, timeout=60)
        if out.get("returncode") != 0:
            raise RuntimeError(
                f"Failed to install intervention tools (rc={out.get('returncode')}): "
                f"{out.get('output', '')[-500:]}"
            )
    return env


def _container_alive(container_id: str | None) -> bool:
    """Return True iff `container_id` names a currently-running container."""
    if not container_id:
        return False
    try:
        res = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"id={container_id}"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except Exception:
        return False
    return bool(res.stdout.strip())


def _read_partial_trajectory(traj_path: Path) -> dict | None:
    """If `traj_path` exists and contains an unfinished trajectory
    (last message role != 'exit'), return its parsed contents; else
    return None.

    Also returns None for malformed JSON (treated as 'no useful state'),
    and for trajectories whose last message IS 'exit' (those are
    finished — but they should already be in preds.json and never reach
    `process_instance`)."""
    if not traj_path.exists():
        return None
    try:
        traj = json.loads(traj_path.read_text())
    except Exception:
        return None
    msgs = traj.get("messages") or []
    if not msgs or msgs[-1].get("role") == "exit":
        return None
    return traj


def _archive_partial(traj_path: Path) -> Path | None:
    """Move a stale partial trajectory aside so we can start fresh
    without losing the prior data. Returns the new path (for logging)
    or None if the file didn't exist."""
    if not traj_path.exists():
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archived = traj_path.with_suffix(f".partial.{ts}.json")
    traj_path.rename(archived)
    return archived


def process_instance(instance, model_name, config, output_path, progress_manager):
    instance_id = instance["instance_id"]
    instance_dir = output_path / instance_id
    instance_dir.mkdir(exist_ok=True, parents=True)
    traj_path = instance_dir / f"{instance_id}.traj.json"

    # ---- Decide: fresh start, or resume from partial trajectory? ------
    # An instance reaches process_instance only if it's NOT in preds.json
    # (the batch-level filter in main() already skipped completed ones).
    # So if a `.traj.json` exists here, it must be a partial from a
    # previous interrupted run.
    partial = _read_partial_trajectory(traj_path)
    resume_cid: str | None = None
    if partial is not None:
        cid = (((partial.get("info") or {}).get("runtime") or {})
               .get("container_id"))
        if _container_alive(cid):
            resume_cid = cid
            logger.info(
                f"[{instance_id}] resuming from partial trajectory "
                f"({len(partial.get('messages') or [])} msgs, container={cid[:12]})"
            )
        else:
            archived = _archive_partial(traj_path)
            logger.info(
                f"[{instance_id}] partial trajectory's container is dead; "
                f"archived prior trajectory to {archived} and starting fresh"
            )

    # Override model_name in config so get_model picks our flag value.
    model_config = dict(config.get("model", {}))
    model_config["model_name"] = model_name
    model = get_model(config=model_config)

    task = instance["problem_statement"]
    progress_manager.on_instance_start(instance_id)
    progress_manager.update_instance_status(
        instance_id, "Resuming" if resume_cid else "Starting environment"
    )

    intervention_cfg = config.get("intervention", {"id": 0, "prompt_config": "none"})

    agent = None
    env = None
    exit_status = None
    result = ""
    extra_info: dict = {}
    try:
        env = _build_environment(
            config, instance, intervention_cfg,
            reuse_container_id=resume_cid,
        )
        agent_kwargs = dict(config.get("agent", {}))
        # Force per-step trajectory writes by setting output_path on the
        # agent's config. mini-swe-agent's run() loop writes after every
        # step in a `finally:` block.
        agent_kwargs["output_path"] = traj_path
        agent = ResumableProgressAgent(
            model, env,
            progress_manager=progress_manager,
            instance_id=instance_id,
            extra_save_info={
                "intervention": intervention_cfg,
                "instance_id": instance_id,
            },
            **agent_kwargs,
        )

        if resume_cid is not None:
            prior_msgs = partial.get("messages") or []
            stats = (partial.get("info") or {}).get("model_stats") or {}
            info = agent.resume(
                task,
                prior_msgs,
                n_calls=int(stats.get("api_calls") or 0),
                cost=float(stats.get("instance_cost") or 0.0),
            )
        else:
            info = agent.run(task)

        exit_status = info.get("exit_status")
        result = info.get("submission") or ""

        # For intervention runs, copy the in-container confidence log into the
        # trajectory so post-hoc rescorers (intervention 4) don't need the
        # container to still exist.
        if int(intervention_cfg.get("id", 0)) != 0:
            try:
                conf_out = env.execute(
                    {"command": "cat /tmp/ca_state/confidence.jsonl 2>/dev/null || true"},
                    timeout=30,
                )
                conf_lines = [
                    json.loads(ln)
                    for ln in conf_out.get("output", "").splitlines()
                    if ln.strip()
                ]
                extra_info["confidence_log"] = conf_lines
            except Exception:
                extra_info["confidence_log"] = []
    except Exception as e:
        logger.error(f"Error processing instance {instance_id}: {e}", exc_info=True)
        exit_status, result = type(e).__name__, ""
        import traceback
        extra_info = {"traceback": traceback.format_exc(), "exception_str": str(e)}
    finally:
        try:
            if agent is not None:
                # Final enriched save (overwrites the last per-step save with
                # exit_status, submission, confidence_log).
                agent.save(
                    traj_path,
                    {
                        "info": {
                            "exit_status": exit_status,
                            "submission": result,
                            **extra_info,
                        },
                    },
                )
        except Exception:
            pass
        # Only tear down the container on a *clean* finish — that way an
        # interrupted instance leaves its container running for resume.
        if env is not None and exit_status is not None and exit_status not in (
            None, "KeyboardInterrupt",
        ):
            try:
                env.cleanup()
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
    ap.add_argument("--intervention", type=int, default=0,
                    choices=[0, 1, 2, 3],
                    help="0 = vanilla (no consequence framing). "
                         "1 = single-turn-multi-step (rubric in system prompt + "
                         "submit_confidence + finalize_submission). "
                         "2 = multi-turn (rubric revealed by submit_preliminary_patch). "
                         "3 = multi-turn no-confidence (ablation of 2). "
                         "Intervention 4 reuses intervention 1 trajectories — "
                         "use scripts/apply_intervention4.py post-hoc.")
    ap.add_argument("--prompt-config", default="none",
                    choices=["none", "quant", "qp6", "qp7"],
                    help="Consequence rubric type. 'none' is only valid with "
                         "--intervention 0. Use 'quant' with --rubric-* flags, "
                         "or 'qp6' / 'qp7' for the qualitative paragraphs.")
    ap.add_argument("--rubric-correct",   type=float, default=None,
                    help="Quantitative rubric: score for a correct submission.")
    ap.add_argument("--rubric-incorrect", type=float, default=None,
                    help="Quantitative rubric: score for an incorrect submission.")
    ap.add_argument("--rubric-abstain",   type=float, default=None,
                    help="Quantitative rubric: score for abstaining.")
    ap.add_argument("--api-timeout", type=float, default=600.0,
                    help="Per-request timeout (seconds) passed to litellm via "
                         "model_kwargs.timeout. Default 600s. Some models "
                         "(e.g. gpt-5-nano with reasoning) occasionally hang "
                         "on a single request; this bounds the wait so the "
                         "agent loop can retry / give up.")
    ap.add_argument("--reasoning-effort", default="medium",
                    choices=["none", "low", "medium", "high", "xhigh"],
                    help="Reasoning effort for the model. Translated to a "
                         "per-family model_kwargs knob (reasoning_effort for "
                         "OpenAI/Gemini/DeepSeek; thinking.budget_tokens for "
                         "Anthropic; extra_body.enable_thinking for Qwen). "
                         "Default 'medium' to match aysm-ca's working setup. "
                         "Pass 'none' to disable.")
    args = ap.parse_args()

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    add_file_handler(output_path / "minisweagent.log")

    import yaml
    config = yaml.safe_load(open(args.config))

    # ---- Inject per-request litellm timeout + reasoning effort ----------
    # Goes into model_kwargs which mini's LitellmModel splats straight
    # into litellm.completion(**kwargs). litellm honours `timeout` and
    # the per-family reasoning knobs (see inject_reasoning_kwargs above).
    config.setdefault("model", {})
    mk = dict(config["model"].get("model_kwargs") or {})
    mk["timeout"] = float(args.api_timeout)
    inject_reasoning_kwargs(args.model, args.reasoning_effort, mk)
    config["model"]["model_kwargs"] = mk
    logger.info(
        f"Final model_kwargs (reasoning_effort={args.reasoning_effort}): "
        f"{ {k: v for k, v in mk.items() if k != 'api_key'} }"
    )

    # ---- Inject intervention spec + system/instance templates ----------
    # The yaml acts as the base scaffold (model, environment, instance_template
    # body, etc). We override agent.system_template and agent.instance_template
    # based on the (intervention, prompt_config) cell so the same yaml file
    # can be used for vanilla and any intervention combination.
    if args.intervention != 0 and args.prompt_config == "none":
        ap.error("--intervention 1|2|3 requires --prompt-config quant|qp6|qp7")
    if args.intervention == 0 and args.prompt_config != "none":
        ap.error("--prompt-config != 'none' requires --intervention 1|2|3")
    if args.prompt_config == "quant" and (
        args.rubric_correct is None
        or args.rubric_incorrect is None
        or args.rubric_abstain is None
    ):
        ap.error("--prompt-config quant requires --rubric-correct, --rubric-incorrect, --rubric-abstain")

    intervention_cfg = {
        "id": args.intervention,
        "prompt_config": args.prompt_config,
        "rubric_correct": args.rubric_correct,
        "rubric_incorrect": args.rubric_incorrect,
        "rubric_abstain": args.rubric_abstain,
    }
    config.setdefault("agent", {})
    if args.intervention != 0:
        config["agent"]["system_template"] = build_system_template(
            intervention=args.intervention,
            prompt_config=args.prompt_config,
            rubric_correct=args.rubric_correct,
            rubric_incorrect=args.rubric_incorrect,
            rubric_abstain=args.rubric_abstain,
        )
        config["agent"]["instance_template"] = build_instance_template(
            intervention=args.intervention,
            prompt_config=args.prompt_config,
        )
        # The vanilla format_error_template references the vanilla submit
        # marker, which we no longer recognise in intervention mode. Replace
        # the hint so format-recovery messages don't mislead the model.
        config.setdefault("model", {})
        if args.intervention in (1, 4):
            hint = (
                "If you have completed your work, run "
                "`submit_confidence --value <0..1>` and then "
                "`finalize_submission` (or `exit_abstain` to abstain)."
            )
        elif args.intervention == 2:
            hint = (
                "If you have completed your work, run "
                "`submit_preliminary_patch`, then `submit_confidence --value <0..1>`, "
                "then `finalize_submission` (or `exit_abstain` to abstain)."
            )
        else:  # intervention == 3
            hint = (
                "If you have completed your work, run "
                "`submit_preliminary_patch`, then `finalize_submission` "
                "(or `exit_abstain` to abstain)."
            )
        config["model"]["format_error_template"] = (
            "Tool call error:\n<error>{{error}}</error>\n\n"
            "Every response needs to use the 'bash' tool at least once.\n"
            f"{hint}\n"
        )
    config["intervention"] = intervention_cfg
    logger.info(
        f"Intervention: id={args.intervention} prompt_config={args.prompt_config} "
        f"rubric=({args.rubric_correct},{args.rubric_incorrect},{args.rubric_abstain})"
    )

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
