"""Run SWE-Bench Pro instances in Modal Sandboxes instead of local Docker.

Why this exists
---------------
The driver gives every SWE-Bench Pro instance its own container: mini-swe-agent
shells out to `docker run` / `docker exec` for the agent loop, and the official
grader starts another container per instance to run the test suites. On a
laptop that is untenable — each Pro image is multi-GB and a 100-instance sweep
pulls hundreds of GB.

This module moves only the *containers* to Modal; the driver, the agent loop,
the trajectory files and the resume logic all keep running locally. That keeps
the change small and leaves the docker path untouched and still the default.

The grading half needs nothing from this file: the upstream evaluator
(`scaleapi/SWE-bench_Pro-os`) already supports Modal natively — it is the
recommended mode — so `scripts/run_eval.sh --modal` just stops passing
`--use_local_docker`.

Design
------
`ModalSandboxEnvironmentWithAbstain` subclasses the existing
`DockerEnvironmentWithAbstain` and overrides exactly three methods:
`_start_container`, `execute` and `cleanup`. Everything else — the config
dataclass, and critically `_check_finished` with its submit/abstain marker
protocol — is inherited unchanged, so the two runtimes cannot drift apart in
how a submission or an abstention is recognised.

Command timeouts
----------------
When a command exceeds `config.timeout`, both runtimes report `returncode: -1`
and both preserve whatever the command printed before it was killed. Docker gets
the partial output from `subprocess.TimeoutExpired.output`; Modal's exec timeout
sets the return code to -1 without raising, and the stream still yields what was
already produced (verified directly: a command printing three lines then
sleeping past its timeout returns all three lines with rc=-1).

So a timed-out command that reports empty output really did produce nothing —
typically `grep ... | head` on a large repo, where grep's stdout to a pipe is
block-buffered and never flushes before the kill. That is not a runtime
artifact and Docker behaves the same way; raise `environment.timeout` in the
yaml if it matters.

Cost containment
----------------
Modal bills for sandbox wall-clock, so a leaked sandbox bills until something
kills it. Three independent guards:

1. Every sandbox is created with `timeout` (a hard lifetime cap Modal enforces
   server-side) and `idle_timeout`. Even if this process is SIGKILLed, the
   sandbox dies on its own.
2. `cleanup()` terminates the sandbox on the normal path, and the inherited
   `__del__` calls it.
3. Every sandbox is created inside one named App, so `terminate_all()` (and
   `scripts/modal_teardown.py`, which wraps it) can enumerate and kill
   *everything* regardless of which process created it.
"""

from __future__ import annotations

import os
import re

from swebench_pro.interventions.env import DockerEnvironmentWithAbstain

# All sandboxes created by *this* driver live in this App so teardown can
# enumerate them. Overridable so a parallel experiment can be isolated and torn
# down independently.
APP_NAME = os.environ.get("MODAL_SWE_APP_NAME", "swebench-pro-ca")

# The official grader (`external/SWE-bench_Pro-os/swe_bench_pro_eval.py`) does
# NOT use our App — it hardcodes `modal.App.lookup(name="swe-bench-pro-eval")`
# and creates one sandbox per instance there (cpu=(1,4), memory=(5,30) GiB,
# 1 h timeout). A killed grading run therefore leaks sandboxes that a sweep of
# our App alone would report as "clean". Teardown covers both.
EVAL_APP_NAME = os.environ.get("MODAL_SWE_EVAL_APP_NAME", "swe-bench-pro-eval")

# The base-model experiment (modal_apps/vllm_sandbox.py) serves vLLM from its
# own App. A leaked *GPU* sandbox is the most expensive thing this project can
# strand, so teardown must cover it too.
VLLM_APP_NAME = os.environ.get("MODAL_VLLM_APP_NAME", "omni-math-vllm")

# Every App this project can leave sandboxes in.
ALL_APP_NAMES = [APP_NAME, EVAL_APP_NAME, VLLM_APP_NAME]

# Defaults sized for a Pro repo checkout + test run.
#
# 1 CPU is deliberate. Modal bills sandbox wall-clock, and a measured smoke run
# came to $0.19/hour at 2 CPU + 4 GiB, of which CPU was 81% ($0.116 vs $0.027).
# But the sandbox spends nearly all of that wall-clock *idle*, blocked on the
# model API between commands — so the second core is bought and not used.
# Halving CPU takes roughly 40% off the bill for an experiment whose total
# budget is tens of dollars. Memory stays at 4 GiB because that is what the
# agent actually consumes when it runs a repo's test suite.
#
# Raise via MODAL_SWE_CPU if a repo turns out to be genuinely compute-bound.
DEFAULT_CPU = float(os.environ.get("MODAL_SWE_CPU", "1"))
DEFAULT_MEMORY_MB = int(os.environ.get("MODAL_SWE_MEMORY_MB", "4096"))

# Fallback lifetime cap when the yaml's `container_timeout` can't be parsed.
DEFAULT_TIMEOUT_S = int(os.environ.get("MODAL_SWE_TIMEOUT_S", "7200"))

# Kill a sandbox that has had no exec for this long. Bounds the damage from a
# driver that dies between `_start_container` and the first `execute`.
DEFAULT_IDLE_TIMEOUT_S = int(os.environ.get("MODAL_SWE_IDLE_TIMEOUT_S", "1800"))

_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}

_app = None


def _import_modal():
    """Import modal lazily so the docker path never pays for it."""
    try:
        import modal  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "The modal runtime was requested but the `modal` package is not "
            "installed. Run `pip install modal` and `modal setup`."
        ) from e
    return modal


def get_app():
    """The shared App every sandbox is attached to (created on first use)."""
    global _app
    if _app is None:
        modal = _import_modal()
        _app = modal.App.lookup(APP_NAME, create_if_missing=True)
    return _app


def parse_duration(value, default: int = DEFAULT_TIMEOUT_S) -> int:
    """Turn mini's `container_timeout` ("2h", "900s", 3600) into seconds."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    m = _DURATION_RE.match(str(value))
    if not m:
        return default
    return int(float(m.group(1)) * _UNIT_SECONDS[m.group(2).lower()])


def sandbox_is_alive(sandbox_id: str | None) -> bool:
    """True iff `sandbox_id` names a Modal Sandbox that is still running.

    The Modal counterpart of `run_mini_on_pro._container_alive`; used by the
    per-instance resume path to decide whether a partial trajectory can be
    picked back up or has to be restarted from scratch.
    """
    if not sandbox_id:
        return False
    try:
        modal = _import_modal()
        sb = modal.Sandbox.from_id(sandbox_id)
        return sb.poll() is None
    except Exception:
        return False


def list_sandboxes(app_name: str = APP_NAME) -> list:
    """Every live sandbox in the App, newest first."""
    modal = _import_modal()
    app = modal.App.lookup(app_name, create_if_missing=True)
    return [sb for sb in modal.Sandbox.list(app_id=app.app_id) if sb.poll() is None]


def terminate_all(app_name: str = APP_NAME, dry_run: bool = False) -> list[str]:
    """Terminate every live sandbox in the App. Returns the ids acted on.

    The backstop for cost control: safe to run at any time, and the only thing
    that reliably cleans up after a hard kill.
    """
    ids = []
    for sb in list_sandboxes(app_name):
        ids.append(sb.object_id)
        if not dry_run:
            try:
                sb.terminate()
            except Exception as e:  # pragma: no cover - best effort
                print(f"  ! failed to terminate {sb.object_id}: {e}")
    return ids


class ModalSandboxEnvironmentWithAbstain(DockerEnvironmentWithAbstain):
    """`DockerEnvironmentWithAbstain`, but the container is a Modal Sandbox.

    Inherits the submit/abstain marker protocol (`_check_finished`) verbatim —
    only the container lifecycle and command execution are replaced.
    """

    def __init__(
        self,
        *,
        sandbox_cpu: float = DEFAULT_CPU,
        sandbox_memory_mb: int = DEFAULT_MEMORY_MB,
        sandbox_idle_timeout: int = DEFAULT_IDLE_TIMEOUT_S,
        **kwargs,
    ):
        # Set before super().__init__(), which calls _start_container().
        self._sandbox = None
        self._sandbox_cpu = sandbox_cpu
        self._sandbox_memory_mb = sandbox_memory_mb
        self._sandbox_idle_timeout = sandbox_idle_timeout
        super().__init__(**kwargs)

    # ---- container lifecycle ------------------------------------------

    def _start_container(self):
        modal = _import_modal()

        if self._reuse_container_id:
            sb = modal.Sandbox.from_id(self._reuse_container_id)
            if sb.poll() is not None:
                raise RuntimeError(
                    f"reuse_container_id={self._reuse_container_id!r} is not a running "
                    "sandbox; cannot reattach. Caller should fall back to a fresh start."
                )
            self._sandbox = sb
            self.container_id = sb.object_id
            self.logger.info(f"Reattached to existing Modal sandbox {sb.object_id}")
            return

        # `.entrypoint([])` is the Modal analogue of the docker config's
        # `--entrypoint ""`: Pro images default-run their test harness on
        # start, which would exit the sandbox immediately.
        image = modal.Image.from_registry(self.config.image).entrypoint([])

        lifetime = parse_duration(self.config.container_timeout)
        forwarded = {k: v for k in self.config.forward_env if (v := os.getenv(k)) is not None}
        env = {**forwarded, **self.config.env}

        self._sandbox = modal.Sandbox.create(
            "sleep", "infinity",
            image=image,
            app=get_app(),
            workdir=self.config.cwd,
            timeout=lifetime,
            idle_timeout=self._sandbox_idle_timeout,
            cpu=self._sandbox_cpu,
            memory=self._sandbox_memory_mb,
            env=env or None,
        )
        self.container_id = self._sandbox.object_id
        self.logger.info(
            f"Started Modal sandbox {self.container_id} from {self.config.image} "
            f"(cpu={self._sandbox_cpu}, mem={self._sandbox_memory_mb}MiB, "
            f"timeout={lifetime}s)"
        )

    def cleanup(self):
        sb, self._sandbox = self._sandbox, None
        if sb is None:
            return
        try:
            sb.terminate()
        except Exception as e:  # pragma: no cover - best effort on teardown
            print(f"warning: failed to terminate sandbox {getattr(sb, 'object_id', '?')}: {e}")

    # ---- command execution --------------------------------------------

    def execute(self, action: dict, cwd: str = "", *, timeout: int | None = None) -> dict:
        """Run one agent action in the sandbox.

        Matches `DockerEnvironment.execute`'s contract: returns
        `{"output", "returncode"}` with **stderr merged into stdout**, then
        hands the result to `_check_finished` so a submit/abstain marker ends
        the episode.

        Docker merges the streams with `stderr=subprocess.STDOUT`. Modal
        exposes stdout and stderr as separate readers, which would lose the
        interleaving, so we merge inside the container instead: a leading
        `exec 2>&1` redirects stderr for the remainder of the shell. That
        applies to the whole action regardless of how it is structured —
        unlike a trailing `2>&1`, which would bind only to the last command of
        a compound statement.
        """
        if self._sandbox is None:
            raise RuntimeError("Modal sandbox is not running (already cleaned up?)")

        command = action.get("command", "")
        workdir = cwd or self.config.cwd
        env = dict(self.config.env)
        # `env` wins over `forward_env` on conflict, matching DockerEnvironment.
        forwarded = {k: v for k in self.config.forward_env if (v := os.getenv(k)) is not None}
        env = {**forwarded, **env}

        try:
            proc = self._sandbox.exec(
                *self.config.interpreter,
                f"exec 2>&1\n{command}",
                workdir=workdir,
                env=env or None,
                timeout=int(timeout or self.config.timeout),
            )
            output = {
                "output": proc.stdout.read(),
                "returncode": proc.wait(),
                "exception_info": "",
            }
        except Exception as e:
            # Mirror DockerEnvironment: a failed or timed-out command is an
            # observation the agent gets to react to, not an exception that
            # kills the instance. Command timeouts are routine here — the agent
            # runs a repo's full test suite and gets cut off.
            raw_output = getattr(e, "output", None)
            raw_output = (
                raw_output.decode("utf-8", errors="replace")
                if isinstance(raw_output, bytes)
                else (raw_output or "")
            )
            output = {
                "output": raw_output,
                "returncode": -1,
                "exception_info": f"An error occurred while executing the command: {e}",
                "extra": {"exception_type": type(e).__name__, "exception": str(e)},
            }
        self._check_finished(output)
        return output

    # ---- introspection -------------------------------------------------

    def __repr__(self):  # pragma: no cover - debugging aid
        return (
            f"<ModalSandboxEnvironmentWithAbstain image={self.config.image!r} "
            f"sandbox={self.container_id!r}>"
        )


__all__ = [
    "APP_NAME",
    "ModalSandboxEnvironmentWithAbstain",
    "get_app",
    "list_sandboxes",
    "parse_duration",
    "sandbox_is_alive",
    "terminate_all",
]
