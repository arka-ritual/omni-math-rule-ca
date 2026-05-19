"""ResumableProgressAgent — drop-in replacement for ProgressTrackingAgent
with two extra capabilities the swebench_pro driver needs:

1. **Always-on save metadata.** mini-swe-agent's stock `agent.save()` is
   called with no `extra_dicts` from inside its `run()` loop's `finally`
   block, so the per-step real-time trajectory file is missing the
   intervention spec, instance id, and runtime info we need for post-hoc
   analysis (intervention 4 in particular). We override `serialize()`
   to merge a configurable `extra_save_info` dict + a `runtime` block
   (container_id, image) into every save, including the per-step ones.

2. **Mid-instance resume.** `run()` always starts from scratch with the
   system+instance prompt seeding. We add `resume(prior_messages, ...)`
   which skips the seeding and continues the agent loop with the
   restored message history, n_calls, and cost.

The container reattach side of resume is implemented in
`DockerEnvironmentWithAbstain` (see env.py): if the env is built with
`reuse_container_id=<cid>`, it skips `docker run` and validates the
existing container is alive.

Together, these two pieces let the driver crash mid-instance (because
the model is hung in litellm, OOMs, the host reboots, etc.) and pick up
exactly where it left off on the next invocation, without re-paying for
all the prior model calls.
"""

from __future__ import annotations

import logging
from typing import Any

from minisweagent.exceptions import InterruptAgentFlow, LimitsExceeded
from minisweagent.run.benchmarks.swebench import ProgressTrackingAgent

logger = logging.getLogger("minisweagent")


class ResumableProgressAgent(ProgressTrackingAgent):
    def __init__(
        self,
        *args,
        extra_save_info: dict[str, Any] | None = None,
        loop_threshold: int = 10,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._extra_save_info: dict[str, Any] = dict(extra_save_info or {})
        # Loop detector: if the last `loop_threshold` assistant turns issued
        # the exact same action sequence (commands compared as stripped
        # strings), abort with exit_status='LoopDetected'. Set to 0 to
        # disable. Cheap weak models (e.g. gemini-3.1-flash-lite-preview)
        # routinely burn 200+ steps repeating the same `cat <<EOF > foo`
        # or `sed -n '...'` call; without this they hit step_limit and
        # waste compute / API spend. See the looping-trajectories analysis
        # in the May 2026 swebench_pro investigation.
        self._loop_threshold: int = int(loop_threshold)

    def set_extra_save_info(self, info: dict[str, Any]) -> None:
        """Merge `info` into the dict that gets written into every save.
        Use this from the driver to push live state (e.g. confidence_log)
        into the on-disk trajectory mid-run."""
        self._extra_save_info.update(info)

    def _last_n_action_seqs_identical(self, n: int) -> tuple[bool, tuple[str, ...] | None]:
        """Walk back through `self.messages` collecting the last `n` assistant
        turns that produced at least one action. Return (True, seq) if all
        `n` of them issued the exact same action sequence (stripped command
        strings); (False, None) otherwise.

        Skips assistant turns that produced zero actions (e.g. format-error
        retries) so an interleaved stutter doesn't reset the streak; but
        returns False if there aren't `n` action-bearing assistant turns yet.
        """
        if n <= 0:
            return False, None
        seqs: list[tuple[str, ...]] = []
        for msg in reversed(self.messages):
            if msg.get("role") != "assistant":
                continue
            actions = (msg.get("extra") or {}).get("actions") or []
            if not actions:
                continue
            seq = tuple((a.get("command") or "").strip() for a in actions)
            seqs.append(seq)
            if len(seqs) == n:
                break
        if len(seqs) < n:
            return False, None
        first = seqs[0]
        if all(s == first for s in seqs):
            return True, first
        return False, None

    def query(self) -> dict:
        """Pre-check for action-loop, then defer to the upstream cost/step
        limit check + actual model call."""
        if self._loop_threshold > 0:
            looped, seq = self._last_n_action_seqs_identical(self._loop_threshold)
            if looped:
                preview = (seq[0] if seq else "")[:120].replace("\n", "\\n")
                logger.warning(
                    f"[loop_detector] Same action repeated "
                    f"{self._loop_threshold} times in a row; aborting. "
                    f"Repeated cmd preview: {preview!r}"
                )
                raise LimitsExceeded(
                    {
                        "role": "exit",
                        "content": (
                            f"LoopDetected: identical action issued "
                            f"{self._loop_threshold} consecutive turns; "
                            f"aborting before step_limit."
                        ),
                        "extra": {
                            "exit_status": "LoopDetected",
                            "submission": "",
                            "loop_repeat_count": self._loop_threshold,
                            "loop_action_preview": (seq[0] if seq else "")[:500],
                        },
                    }
                )
        return super().query()

    def serialize(self, *extra_dicts) -> dict:
        runtime = {
            "container_id": getattr(self.env, "container_id", None),
            "container_image": getattr(getattr(self.env, "config", None), "image", None),
        }
        own: dict[str, Any] = {
            "info": {
                **self._extra_save_info,
                "runtime": runtime,
            },
        }
        if getattr(self, "instance_id", None):
            own["instance_id"] = self.instance_id
        return super().serialize(own, *extra_dicts)

    def resume(
        self,
        task: str,
        prior_messages: list[dict],
        *,
        n_calls: int,
        cost: float,
        **kwargs,
    ) -> dict:
        """Continue from a saved trajectory.

        Skips the system+instance prompt seeding (those messages are
        expected to already be in `prior_messages`) and restores the
        agent's call/cost counters before re-entering the step loop.

        If `prior_messages[-1]` is already an `exit` message we just
        return its `extra` dict (defensive: caller should normally check
        this before deciding to resume).
        """
        self.extra_template_vars |= {"task": task, **kwargs}
        self.messages = list(prior_messages)
        self.n_calls = int(n_calls)
        self.cost = float(cost)
        logger.info(
            f"Resuming agent: {len(self.messages)} prior messages, "
            f"n_calls={self.n_calls}, cost=${self.cost:.4f}"
        )

        if self.messages and self.messages[-1].get("role") == "exit":
            return self.messages[-1].get("extra", {})

        while True:
            try:
                self.step()
            except InterruptAgentFlow as e:
                self.add_messages(*e.messages)
            except Exception as e:
                self.handle_uncaught_exception(e)
                raise
            finally:
                self.save(self.config.output_path)
            if self.messages[-1].get("role") == "exit":
                break
        return self.messages[-1].get("extra", {})
