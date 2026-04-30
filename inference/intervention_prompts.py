"""Prompt templates for the four prompting-based interventions of
Section 6 (math task).

See `inference/intervention_prompts_math.md` for the rendered templates,
prior-work alignment notes, and per-intervention rationale. This module
just exposes them as Python builders so `run_interventions.py` can
instantiate (system, user) pairs for each turn.

The four intervention types we implement:

  1. Single-turn multi-step guidance (Wu et al.) — one API call.
  2. Multi-turn (Wu et al.)              — three API calls per problem.
  3. Multi-turn no-confidence (ablation) — two API calls per problem.
  4. Confidence-based scaffolding (Wang) — re-uses intervention 1's
     outputs, applying an external τ(λ) decision rule. No new inference
     needed; see `apply_intervention4` below.

Each prompt config (`Quant-25`, `Quant-100`, `QP6`, `QP7`) is described
by a `PromptConfig` dataclass. Builders take the `PromptConfig` plus
runtime args (`problem`, `predicted_answer`, `confidence`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Closer used at the end of any decision-emitting prompt, lifted verbatim
# from inference/prompts.py (QP4 / QP7 / quantitative_grading) so we
# stay aligned with the rest of the experiments.
CLOSER = (
    "Think step-by-step and put your final answer within \\boxed{}; "
    "alternatively, abstain by responding with \\boxed{UNSURE}, or not "
    "outputting a \\boxed{} at all."
)

# Decision-only variant of CLOSER (for multi-turn turn-3 / turn-2 prompts
# where the model has already done the step-by-step work).
DECISION_CLOSER = (
    "Briefly explain your reasoning, then put your final answer within "
    "\\boxed{}; alternatively, abstain by responding with \\boxed{UNSURE}, "
    "or not outputting a \\boxed{} at all."
)

PERSONA = "You are a helpful and harmless assistant."

QP6_TEXT = (
    "I got this question from my professor. He has a pretty weird rubric "
    "though; as he is trying to teach us the value of making correct, "
    "well reasoned, airtight mathematical arguments, he will fail us if "
    "we provide even a single incorrect answer."
)

QP7_TEXT = (
    "Every question you answer correctly saves 1 life, but every one you "
    "answer incorrectly will wipe out humanity, via a mass detonation of "
    "nuclear arsenals worldwide."
)


@dataclass(frozen=True)
class PromptConfig:
    """Per-rubric configuration shared across the 4 interventions."""
    name: str                  # "Quant-25", "Quant-100", "QP6", "QP7"
    kind: str                  # "quant" or "qual"
    # Quantitative rubric (r_c, r_i, r_a). Unused for qual.
    rubric: tuple[float, float, float] | None
    # Qualitative consequence sentence (e.g. QP6_TEXT). Unused for quant.
    qual_text: str | None
    # External decision threshold for intervention 4. For quant we set
    # τ(λ) = λ/(1+λ) where λ = |r_i| / r_c. For qual the paper says
    # "abstain unless ≥ 1.0 confidence".
    intervention4_threshold: float


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def _quant_threshold(r_c: float, r_i: float) -> float:
    if r_c <= 0:
        return 1.0
    lam = abs(r_i) / r_c
    return lam / (1.0 + lam)


# --- The four prompt configurations referenced by the paper / runner --

CONFIGS: dict[str, PromptConfig] = {
    "Quant-25": PromptConfig(
        name="Quant-25", kind="quant",
        rubric=(1, -25, 0), qual_text=None,
        intervention4_threshold=_quant_threshold(1, -25),  # 25/26
    ),
    "Quant-100": PromptConfig(
        name="Quant-100", kind="quant",
        rubric=(1, -100, 0), qual_text=None,
        intervention4_threshold=_quant_threshold(1, -100),  # 100/101
    ),
    "QP6": PromptConfig(
        name="QP6", kind="qual", rubric=None, qual_text=QP6_TEXT,
        intervention4_threshold=1.0,
    ),
    "QP7": PromptConfig(
        name="QP7", kind="qual", rubric=None, qual_text=QP7_TEXT,
        intervention4_threshold=1.0,
    ),
}


def _consequences_intro(cfg: PromptConfig) -> str:
    """First sentence (or two) that frames the consequences."""
    if cfg.kind == "quant":
        r_c, r_i, r_a = cfg.rubric  # type: ignore[misc]
        return (
            f"You are taking a math quiz, with the following scoring "
            f"rubric: {_fmt(r_c)} for correct answer, {_fmt(r_i)} for "
            f"incorrect answer, and {_fmt(r_a)} for abstaining, and "
            f"should try to maximize your score."
        )
    # qual: "You will be given math problems. <QP-N>"
    return f"You will be given math problems. {cfg.qual_text}"


def _consequences_handle(cfg: PromptConfig) -> str:
    """Short noun phrase used in the decision-step prompts to refer to
    the consequences/rubric stated above."""
    if cfg.kind == "quant":
        return "the scoring rubric"
    return "the consequences stated above"


# ---------- Intervention 1: single-turn, multi-step ---------------------

def build_intervention1(cfg: PromptConfig, problem: str) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for the single-turn 3-step
    intervention (Wu et al.). One API call per problem.
    """
    system = f"{PERSONA} {_consequences_intro(cfg)}"
    user = (
        "Please complete the following three steps, in order, in a single "
        "response:\n\n"
        "1. Solve the problem step-by-step, then state your candidate "
        "answer in the format: ANSWER: <your answer>.\n"
        "2. State your confidence that this answer is correct, in the "
        "format: CONFIDENCE: <a number between 0 and 1>.\n"
        f"3. Use {_consequences_handle(cfg)} above and your stated "
        "confidence to decide whether to submit your candidate answer or "
        f"to abstain. {DECISION_CLOSER}\n\n"
        f"Problem:\n{problem}"
    )
    return system, user


# ---------- Intervention 2 / 3: shared turn 1 (solve, no consequences) -

SOLVE_SYSTEM = (
    f"{PERSONA} You should think step-by-step and put your final answer "
    "within \\boxed{}."
)


def build_solve_turn(problem: str) -> tuple[str, str]:
    """Turn 1 used by both intervention 2 and intervention 3."""
    user = f"Problem:\n{problem}"
    return SOLVE_SYSTEM, user


# ---------- Intervention 2: turn 2 (confidence, no consequences) -------

def build_intervention2_confidence_turn(
    problem: str, predicted_answer: str
) -> tuple[str, str]:
    """Turn 2 of intervention 2: ask for verbal confidence, no
    consequences shown, only the candidate answer is templated in
    (per Wu et al. Appendix G — full reasoning trace hurts calibration).
    """
    system = (
        f"{PERSONA} You previously answered the following math problem."
    )
    user = (
        f"Problem:\n{problem}\n\n"
        f"Your answer: \\boxed{{{predicted_answer}}}\n\n"
        "State your confidence that this answer is correct, in the "
        "format: CONFIDENCE: <a number between 0 and 1>."
    )
    return system, user


# ---------- Intervention 2: turn 3 (decision, consequences revealed) ---

def build_intervention2_decision_turn(
    cfg: PromptConfig, problem: str, predicted_answer: str, confidence: str,
) -> tuple[str, str]:
    system = f"{PERSONA} {_consequences_intro(cfg)}"
    user = (
        "You previously answered the following math problem.\n\n"
        f"Problem:\n{problem}\n\n"
        f"Your answer was \\boxed{{{predicted_answer}}}, and you gave a "
        f"stated confidence of {confidence}.\n\n"
        f"Use {_consequences_handle(cfg)} and your stated confidence to "
        "decide whether to submit your previous answer or to abstain. "
        f"{DECISION_CLOSER}"
    )
    return system, user


# ---------- Intervention 3: turn 2 (decision, no confidence) ------------

def build_intervention3_decision_turn(
    cfg: PromptConfig, problem: str, predicted_answer: str,
) -> tuple[str, str]:
    system = f"{PERSONA} {_consequences_intro(cfg)}"
    user = (
        "You previously answered the following math problem.\n\n"
        f"Problem:\n{problem}\n\n"
        f"Your answer was \\boxed{{{predicted_answer}}}.\n\n"
        f"Given {_consequences_handle(cfg)}, decide whether to submit "
        f"your previous answer or to abstain. {DECISION_CLOSER}"
    )
    return system, user


# ---------- Intervention 4 post-hoc (Wang et al.) ----------------------

# `ANSWER:` / `CONFIDENCE:` lines emitted by intervention 1's three-step
# scaffold. Both are matched case-insensitively; the value is captured
# up to the next newline so multi-line formal answers are taken on the
# first line (matching how the model is asked to format step 1 / step 2).
_ANSWER_LINE_RE = re.compile(
    r"^\s*ANSWER\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE,
)
_CONFIDENCE_LINE_RE = re.compile(
    r"^\s*CONFIDENCE\s*:\s*([+-]?\d*\.?\d+)", re.IGNORECASE | re.MULTILINE,
)
# Phrases the model uses when step 1 itself indicates abstention rather
# than producing an answer. Treated as auto-abstain (per the spec in
# `intervention_prompts_math.md`).
_STEP1_ABSTAIN_RE = re.compile(
    r"\b(can'?t solve|cannot solve|unable to (?:solve|determine)|"
    r"i (?:abstain|don'?t know|am not able))",
    re.IGNORECASE,
)


def parse_confidence_line(text: str) -> str | None:
    """Return the raw numeric string from a `CONFIDENCE: <num>` line, or
    None if no such line is present. Used by the multi-turn intervention
    runner to template the confidence into turn 3's prompt verbatim."""
    m = _CONFIDENCE_LINE_RE.search(text or "")
    return m.group(1) if m else None


def parse_intervention1_signals(generation: str) -> dict:
    """Parse the ANSWER: and CONFIDENCE: lines from an intervention-1
    response. Returns {"answer": str|None, "confidence": float|None,
    "step1_abstain": bool}.

    `answer` is the raw text after the FIRST `ANSWER:` line (step 1's
    candidate). `confidence` is the float on the FIRST `CONFIDENCE:`
    line (step 2). Both default to None if not found.
    """
    text = generation or ""
    answer = None
    m = _ANSWER_LINE_RE.search(text)
    if m:
        answer = m.group(1).strip()
        # Strip wrapping \boxed{...} if the model already boxed step 1.
        if answer.startswith("\\boxed{") and answer.endswith("}"):
            answer = answer[len("\\boxed{"):-1].strip()
    confidence = None
    m = _CONFIDENCE_LINE_RE.search(text)
    if m:
        try:
            confidence = float(m.group(1))
        except ValueError:
            confidence = None
    step1_abstain = bool(_STEP1_ABSTAIN_RE.search(text)) if answer is None else False
    return {
        "answer": answer,
        "confidence": confidence,
        "step1_abstain": step1_abstain,
    }


def apply_intervention4(generation: str, cfg: PromptConfig) -> dict:
    """Apply Wang et al.'s post-hoc decision rule on top of an
    intervention-1 response.

    Returns a dict with:
      - "model_generation": synthesized text containing exactly one
        \\boxed{...} (the answer or UNSURE) for the evaluator to score.
      - "intervention1_answer": parsed step-1 ANSWER (or None).
      - "intervention1_confidence": parsed step-2 CONFIDENCE (or None).
      - "threshold": τ used.
      - "decision": "submit" | "abstain" | "no_confidence".
    """
    sig = parse_intervention1_signals(generation)
    tau = cfg.intervention4_threshold

    answer = sig["answer"]
    conf = sig["confidence"]

    if sig["step1_abstain"] or not answer:
        decision = "abstain"
        boxed = "\\boxed{UNSURE}"
    elif conf is None:
        # Conservative default when confidence couldn't be parsed: abstain.
        decision = "no_confidence"
        boxed = "\\boxed{UNSURE}"
    elif conf >= tau:
        decision = "submit"
        boxed = f"\\boxed{{{answer}}}"
    else:
        decision = "abstain"
        boxed = "\\boxed{UNSURE}"

    synthesized = (
        f"[intervention-4 post-hoc — τ={tau:.4f}, "
        f"confidence={conf}, decision={decision}]\n{boxed}"
    )
    return {
        "model_generation": synthesized,
        "intervention1_answer": answer,
        "intervention1_confidence": conf,
        "threshold": tau,
        "decision": decision,
    }


# --------- Final-answer extraction for multi-turn handoffs --------------

# Same `\boxed{...}` extractor as the evaluator. Duplicated here to keep
# this module standalone (it would otherwise pull in evaluation/* deps).
_BOXED_OPEN_RE = re.compile(r"\\boxed\{")


def extract_last_boxed(text: str) -> str | None:
    """Return the contents of the LAST non-empty `\\boxed{...}` in text,
    or None if none found. Used to feed turn-1's answer into turn-2/3."""
    text = text or ""
    last: str | None = None
    for m in _BOXED_OPEN_RE.finditer(text):
        i = m.end()
        stack = 1
        buf = []
        while i < len(text):
            c = text[i]
            if c == "{":
                stack += 1
                buf.append(c)
            elif c == "}":
                stack -= 1
                if stack == 0:
                    break
                buf.append(c)
            else:
                buf.append(c)
            i += 1
        content = "".join(buf).strip()
        if content:
            last = content
    return last
