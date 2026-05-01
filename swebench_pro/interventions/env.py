"""DockerEnvironment subclass that recognises distinct exit markers per
run mode (vanilla vs. intervention).

Vanilla mini-swe-agent only knows one marker:

    COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
        -> Submitted, with submission = stdout[1:]

For the consequence-asymmetry interventions we use two **different**
markers, intentionally distinct from the vanilla one so that the model
can't bypass our protocol by reaching for the vanilla submission
incantation it has memorised from SWE-bench training data:

    __CA_FINALIZE_PATCH_NOW__   -> Submitted, exit_status=Submitted
    __CA_ABSTAIN_NOW__          -> Submitted, exit_status=Abstained, empty submission

Both markers come from the `finalize_submission` and `exit_abstain`
tools we install at runtime; their ordering checks (and the system
prompt + instance template) are the protocol, so swallowing the
vanilla marker for intervention runs forces the model through the
real funnel.

(We re-use the `Submitted` exception so the agent loop's
`while messages[-1].role != 'exit'` cleanly terminates the same way; we
just label the trajectory's `exit_status` differently so post-hoc
analysis knows to score the instance with the abstain rubric value.)
"""

from __future__ import annotations

import subprocess

from minisweagent.environments.docker import DockerEnvironment
from minisweagent.exceptions import Submitted

# Vanilla mini-swe-agent marker (used by the upstream swebench config).
# Recognised only when the env is in vanilla mode (use_intervention_markers=False).
VANILLA_SUBMIT_MARKER = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"

# Intervention markers (must match swebench_pro/interventions/tool_scripts.py).
SUBMIT_MARKER = "__CA_FINALIZE_PATCH_NOW__"
ABSTAIN_MARKER = "__CA_ABSTAIN_NOW__"


class DockerEnvironmentWithAbstain(DockerEnvironment):
    """DockerEnvironment whose `_check_finished` is mode-aware.

    use_intervention_markers (bool, default False)
        - False: only recognise the vanilla submit marker (current
          mini-swe-agent behaviour).
        - True:  only recognise __CA_FINALIZE_PATCH_NOW__ /
          __CA_ABSTAIN_NOW__. The vanilla marker is *ignored*, so the
          model cannot bypass the intervention's submit/abstain tools by
          echoing it manually.
    """

    def __init__(
        self,
        *,
        use_intervention_markers: bool = False,
        reuse_container_id: str | None = None,
        **kwargs,
    ):
        """If `reuse_container_id` is given, skip `docker run` and reattach
        to an already-running container created by a previous driver run.
        Used by the per-instance resume path (`run_mini_on_pro.py`).
        Raises RuntimeError if the named container is missing or stopped."""
        self._use_intervention_markers = use_intervention_markers
        self._reuse_container_id = reuse_container_id
        super().__init__(**kwargs)

    def _start_container(self):
        if self._reuse_container_id:
            cid = self._reuse_container_id
            res = subprocess.run(
                [self.config.executable, "ps", "-q", "--filter", f"id={cid}"],
                capture_output=True, text=True, check=False,
            )
            if not res.stdout.strip():
                raise RuntimeError(
                    f"reuse_container_id={cid!r} is not a running container; "
                    "cannot reattach. Caller should fall back to a fresh start."
                )
            self.container_id = cid
            self.logger.info(f"Reattached to existing container {cid}")
            return
        super()._start_container()

    def _check_finished(self, output: dict):
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if not lines or output.get("returncode") != 0:
            return
        first = lines[0].strip()
        if self._use_intervention_markers:
            if first == SUBMIT_MARKER:
                submission = "".join(lines[1:])
                raise Submitted(
                    {
                        "role": "exit",
                        "content": submission,
                        "extra": {"exit_status": "Submitted", "submission": submission},
                    }
                )
            if first == ABSTAIN_MARKER:
                raise Submitted(
                    {
                        "role": "exit",
                        "content": "",
                        "extra": {"exit_status": "Abstained", "submission": ""},
                    }
                )
        else:
            if first == VANILLA_SUBMIT_MARKER:
                submission = "".join(lines[1:])
                raise Submitted(
                    {
                        "role": "exit",
                        "content": submission,
                        "extra": {"exit_status": "Submitted", "submission": submission},
                    }
                )
