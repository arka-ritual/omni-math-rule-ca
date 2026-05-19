"""Bash sources for the four intervention tools that get installed into
the Pro test container at runtime.

`render_install_script(...)` returns a single bash script that, when
`env.execute()`d in the container, materialises:

  /usr/local/bin/submit_preliminary_patch    # interventions 2, 3
  /usr/local/bin/submit_confidence           # interventions 1, 2
  /usr/local/bin/finalize_submission         # interventions 1, 2, 3
  /usr/local/bin/exit_abstain                # interventions 1, 2, 3

…and a state directory `/tmp/ca_state/` holding:
  state.json                  -- {"phase": "solve" | "review" | "confidence" | "finalize"}
  confidence.jsonl            -- one JSON record per submit_confidence call
  patch.diff                  -- snapshot taken by submit_preliminary_patch
  reveal.txt                  -- the rubric-reveal observation text (rendered host-side)

The marker strings are the exit signals the host environment watches:
  COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT  -> raise Submitted (status=Submitted)
  COMPLETE_TASK_AND_ABSTAIN              -> raise Submitted (status=Abstained, empty submission)
"""

from __future__ import annotations

import base64
import textwrap
from typing import Optional


# -- exit markers (must match swebench_pro/interventions/env.py) ---------
# Intentionally distinct from the vanilla mini-swe-agent submit marker
# (`COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`) so the model can't sidestep the
# intervention protocol by emitting the vanilla incantation from memory.
SUBMIT_MARKER = "__CA_FINALIZE_PATCH_NOW__"
ABSTAIN_MARKER = "__CA_ABSTAIN_NOW__"

# Path on the container; chosen to avoid colliding with anything in the
# upstream Pro test images (they use /app for the repo and /workspace
# for eval workspace).
STATE_DIR = "/tmp/ca_state"


# -- tool body templates -------------------------------------------------
#
# All four tools are tiny bash scripts. They share the same conventions:
#  - state file at $STATE_DIR/state.json
#  - read scoring rubric from env vars CA_RC / CA_RI / CA_RA / CA_QUAL_TEXT /
#    CA_PROMPT_CONFIG / CA_INTERVENTION (set in the container's env via
#    DockerEnvironment.env in the yaml/runner)
#  - the ordering guard prints a clear error to stdout (which becomes the
#    next observation) and exits 1, so the model can correct itself
#  - finalize_submission and exit_abstain print the magic exit markers,
#    triggering the host environment's _check_finished

_SUBMIT_PRELIMINARY = r"""#!/bin/bash
# submit_preliminary_patch -- step 1 of intervention 2 / 3.
# Captures git diff, advances state, and prints next-step guidance.
#
# The rubric-reveal block (the "consequences" paragraph + finalize/abstain
# directive) is emitted differently per intervention:
#   - intervention 3: revealed here, immediately after the diff (model goes
#     straight from preliminary patch to finalize/abstain).
#   - intervention 2: NOT revealed here. The model is asked for confidence
#     first; the rubric is shown only as the observation of submit_confidence,
#     so the confidence value is elicited stake-independently.
set -e

state_dir="__STATE_DIR__"
state_file="${state_dir}/state.json"
patch_file="${state_dir}/patch.diff"
reveal_file="${state_dir}/reveal.txt"
mkdir -p "$state_dir"

phase=$(cat "$state_file" 2>/dev/null | sed -n 's/.*"phase":[[:space:]]*"\([^"]*\)".*/\1/p')
if [ "$phase" = "finalize" ] || [ "$phase" = "confidence" ]; then
    echo "Error: submit_preliminary_patch was already called this episode."
    echo "Next, call submit_confidence (if intervention 2) or finalize_submission / exit_abstain."
    exit 1
fi

# Capture the patch.
cd /app
git add -A 2>/dev/null || true
git diff --cached -- . ':(exclude)*.pyc' ':(exclude)patch.txt' > "$patch_file" || true

# State -> review (intervention 3 skips confidence, so we set "finalize"
# directly when CA_INTERVENTION=3; otherwise "confidence").
intv="${CA_INTERVENTION:-1}"
next_phase="confidence"
if [ "$intv" = "3" ]; then
    next_phase="finalize"
fi
printf '{"phase":"%s"}\n' "$next_phase" > "$state_file"

echo "[REVIEW -- preliminary submission recorded]"
echo
echo "<diff>"
cat "$patch_file"
echo "</diff>"
echo
if [ "$intv" = "3" ]; then
    if [ -f "$reveal_file" ]; then
        cat "$reveal_file"
    else
        # Fallback (host should have written reveal.txt at install time).
        echo "You have produced a candidate patch. Decide whether to finalize_submission or exit_abstain."
    fi
else
    # Intervention 2: stakes are revealed after submit_confidence, not here.
    echo "You have produced a candidate patch. Next, state your confidence"
    echo "that this patch is correct by running:"
    echo "  submit_confidence --value <number in [0, 1]>"
fi
"""


_SUBMIT_CONFIDENCE = r"""#!/bin/bash
# submit_confidence --value <float in [0,1]>
# Records the model's stated confidence, advances state to "finalize".
#
# For intervention 2, this is also where the rubric-reveal block is
# emitted (the model stated its confidence stake-independently; only
# now does it learn the consequences and decide whether to submit).
# For intervention 1, the rubric is already in the system prompt, so
# we just acknowledge the confidence value.
set -e

state_dir="__STATE_DIR__"
state_file="${state_dir}/state.json"
log_file="${state_dir}/confidence.jsonl"
reveal_file="${state_dir}/reveal.txt"
mkdir -p "$state_dir"

value=""
while [ $# -gt 0 ]; do
    case "$1" in
        --value) value="$2"; shift 2 ;;
        --value=*) value="${1#--value=}"; shift ;;
        *) shift ;;
    esac
done

if [ -z "$value" ]; then
    echo "Error: submit_confidence requires --value <number in [0,1]>."
    exit 1
fi

# Validate float in [0, 1] using awk (no python dependency).
ok=$(awk -v v="$value" 'BEGIN{
    if (v ~ /^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$/ &&
        v+0 >= 0 && v+0 <= 1) { print 1 } else { print 0 }
}')
if [ "$ok" != "1" ]; then
    echo "Error: --value must be a number in [0, 1]; got '$value'."
    exit 1
fi

ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"ts":"%s","confidence":%s}\n' "$ts" "$value" >> "$log_file"

# Bump phase to finalize (only if currently in confidence; for intervention 1
# the model is allowed to call submit_confidence directly from "solve").
phase=$(cat "$state_file" 2>/dev/null | sed -n 's/.*"phase":[[:space:]]*"\([^"]*\)".*/\1/p')
if [ "$phase" = "confidence" ] || [ -z "$phase" ] || [ "$phase" = "solve" ]; then
    printf '{"phase":"finalize"}\n' > "$state_file"
fi

intv="${CA_INTERVENTION:-1}"
echo "Confidence ${value} recorded."
if [ "$intv" = "2" ] && [ -f "$reveal_file" ]; then
    echo
    cat "$reveal_file"
else
    echo "Call finalize_submission or exit_abstain next."
fi
"""


_FINALIZE_SUBMISSION = r"""#!/bin/bash
# finalize_submission -- emit the submit exit marker followed by the patch.
set -e

state_dir="__STATE_DIR__"
state_file="${state_dir}/state.json"
patch_file="${state_dir}/patch.diff"
log_file="${state_dir}/confidence.jsonl"
mkdir -p "$state_dir"

phase=$(cat "$state_file" 2>/dev/null | sed -n 's/.*"phase":[[:space:]]*"\([^"]*\)".*/\1/p')

# Intervention-specific ordering rules.
intv="${CA_INTERVENTION:-1}"
case "$intv" in
    1)
        if [ ! -s "$log_file" ]; then
            echo "Error: call submit_confidence --value <0..1> before finalize_submission."
            exit 1
        fi
        ;;
    2)
        if [ "$phase" != "finalize" ]; then
            echo "Error: in this protocol, you must run submit_preliminary_patch and submit_confidence before finalize_submission."
            exit 1
        fi
        ;;
    3)
        if [ "$phase" != "finalize" ]; then
            echo "Error: in this protocol, you must run submit_preliminary_patch before finalize_submission."
            exit 1
        fi
        ;;
esac

# Refresh the patch (the model may have edited files after submit_preliminary_patch).
cd /app
git add -A 2>/dev/null || true
git diff --cached -- . ':(exclude)*.pyc' ':(exclude)patch.txt' > "$patch_file" || true

echo "__SUBMIT_MARKER__"
cat "$patch_file"
"""


_EXIT_ABSTAIN = r"""#!/bin/bash
# exit_abstain -- the agent decides not to submit. Emits the abstain marker.
echo "__ABSTAIN_MARKER__"
"""


# -- installer ----------------------------------------------------------

def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def _render_tool(src: str) -> str:
    """Substitute placeholders in a tool body."""
    return (
        src.replace("__STATE_DIR__", STATE_DIR)
           .replace("__SUBMIT_MARKER__", SUBMIT_MARKER)
           .replace("__ABSTAIN_MARKER__", ABSTAIN_MARKER)
    )


def render_install_script(
    *,
    intervention: int,
    reveal_text: Optional[str] = None,
    rubric_correct: Optional[float] = None,
    rubric_incorrect: Optional[float] = None,
    rubric_abstain: Optional[float] = None,
    prompt_config: str = "none",
    qual_text: str = "",
) -> str:
    """Return a bash script that, when executed in the container, installs
    the intervention tools and writes the reveal block to disk.

    Which tools are installed depends on the intervention id:
      1: submit_confidence, finalize_submission, exit_abstain
      2: submit_preliminary_patch, submit_confidence, finalize_submission, exit_abstain
      3: submit_preliminary_patch, finalize_submission, exit_abstain
      4 (post-hoc): same as 1 — same tools, same trajectories, no separate run
      5: exit_abstain only (vanilla submit flow + abstain channel)
    """
    if intervention not in (1, 2, 3, 4, 5):
        raise ValueError(f"unknown intervention: {intervention}")

    bodies = {
        "submit_preliminary_patch": _render_tool(_SUBMIT_PRELIMINARY),
        "submit_confidence":        _render_tool(_SUBMIT_CONFIDENCE),
        "finalize_submission":      _render_tool(_FINALIZE_SUBMISSION),
        "exit_abstain":             _render_tool(_EXIT_ABSTAIN),
    }

    install_set = {
        1: ["submit_confidence", "finalize_submission", "exit_abstain"],
        2: ["submit_preliminary_patch", "submit_confidence", "finalize_submission", "exit_abstain"],
        3: ["submit_preliminary_patch", "finalize_submission", "exit_abstain"],
        4: ["submit_confidence", "finalize_submission", "exit_abstain"],
        5: ["exit_abstain"],
    }[intervention]

    install_lines: list[str] = []
    for name in install_set:
        encoded = _b64(bodies[name])
        install_lines.append(
            f'echo {encoded} | base64 -d > /usr/local/bin/{name}\n'
            f'chmod +x /usr/local/bin/{name}'
        )
    install_block = "\n".join(install_lines)

    reveal_b64 = _b64(reveal_text or "") if intervention in (2, 3) else ""
    reveal_write = (
        f'echo {reveal_b64} | base64 -d > {STATE_DIR}/reveal.txt'
        if reveal_b64
        else f'rm -f {STATE_DIR}/reveal.txt'
    )

    # Intervention 5 doesn't use a state machine (vanilla submit flow), but
    # we still write a benign "solve" phase so any tool that grep's the
    # state file finds something coherent.
    initial_phase = "review" if intervention in (2, 3) else "solve"

    script = f"""#!/bin/bash
set -e
mkdir -p {STATE_DIR}
printf '{{"phase":"{initial_phase}"}}\\n' > {STATE_DIR}/state.json
: > {STATE_DIR}/confidence.jsonl
: > {STATE_DIR}/patch.diff
{reveal_write}
{install_block}
echo CA_TOOLS_INSTALLED intervention={intervention} prompt_config={prompt_config}
"""
    return textwrap.dedent(script)
