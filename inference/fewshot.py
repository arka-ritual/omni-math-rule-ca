"""Few-shot scaffolding for base (non-instruction-tuned) models.

Provides a 4-shot preamble in 6 different configurations to test how models
react to seeing consequences and abstain-decisions demonstrated in-context.

Each Q/A pair follows this format:

    Q: [optional consequence framing] <problem>
    Thoughts:
    1. ...
    2. ...
    3. ...
    [Answer/Abstain decision: ANSWER|ABSTAIN]   <- only for variants 3-6
    Final Answer: \\boxed{...}

The final query (the actual problem) is rendered identically but truncated
just after "Thoughts:" so the model continues from "1. ...". A stop sequence
of "\\nQ:" prevents the model from running into a hallucinated next question.
"""

from typing import Literal


# ── 4 short worked examples (correct + incorrect versions per problem) ─────
EXAMPLES = [
    {
        "problem": r"What is the sum $1 + 2 + 3 + \cdots + 50$?",
        "correct_answer": "1275",
        "wrong_answer": "1225",
        "correct_thoughts": [
            r"Use Gauss's formula: $\sum_{k=1}^{n} k = n(n+1)/2$.",
            r"Substitute $n = 50$: $50 \cdot 51 / 2$.",
            r"Compute: $2550 / 2 = 1275$.",
        ],
        "wrong_thoughts": [
            r"Use the formula $\sum_{k=1}^{n} k = n(n-1)/2$.",
            r"Substitute $n = 50$: $50 \cdot 49 / 2$.",
            r"Compute: $2450 / 2 = 1225$.",
        ],
    },
    {
        "problem": r"How many positive divisors does $360$ have?",
        "correct_answer": "24",
        "wrong_answer": "7",
        "correct_thoughts": [
            r"Factorize: $360 = 2^3 \cdot 3^2 \cdot 5$.",
            r"Divisor count formula: $(a+1)(b+1)(c+1)$.",
            r"Compute: $(3+1)(2+1)(1+1) = 4 \cdot 3 \cdot 2 = 24$.",
        ],
        "wrong_thoughts": [
            r"Factorize: $360 = 2^3 \cdot 3^2 \cdot 5$.",
            r"Sum the exponents and add 1: $3 + 2 + 1 + 1 = 7$.",
            r"So $360$ has $7$ divisors.",
        ],
    },
    {
        "problem": r"Find the last digit of $7^{100}$.",
        "correct_answer": "1",
        "wrong_answer": "7",
        "correct_thoughts": [
            r"Compute small powers: $7^1=7,\ 7^2=49,\ 7^3=343,\ 7^4=2401$.",
            r"Last digits cycle with period 4: $7, 9, 3, 1$.",
            r"$100 \equiv 0 \pmod 4$, which corresponds to position 4: digit $1$.",
        ],
        "wrong_thoughts": [
            r"Last digits of $7^k$ cycle as $7, 9, 3, 1$ with period 4.",
            r"$100 \bmod 4 = 0$, which is the start of a new cycle: digit $7$.",
            r"So the last digit is $7$.",
        ],
    },
    {
        "problem": r"A right triangle has legs of length $5$ and $12$. What is the length of the hypotenuse?",
        "correct_answer": "13",
        "wrong_answer": "17",
        "correct_thoughts": [
            r"By the Pythagorean theorem: $h^2 = 5^2 + 12^2$.",
            r"Compute: $25 + 144 = 169$.",
            r"So $h = \sqrt{169} = 13$.",
        ],
        "wrong_thoughts": [
            r"For a right triangle, the hypotenuse equals the sum of the legs.",
            r"So $h = 5 + 12 = 17$.",
            r"The hypotenuse has length $17$.",
        ],
    },
]


Variant = Literal[
    "normal",                  # 1. plain Q&A, no conseq, no abstain
    "conseq_no_abstain",       # 2. conseq in Q, A is just normal soln
    "conseq_random_abstain",   # 3. conseq in Q, abstain decisions random (mismatched)
    "conseq_correct_abstain",  # 4. conseq in Q, correct→ANSWER, wrong→ABSTAIN
    "conseq_always_submit",    # 5. conseq in Q, mixed correctness, always ANSWER
    "conseq_always_abstain",   # 6. conseq in Q, always ABSTAIN
]


# Per-variant: list of (use_correct_solution, decision_or_None) for the 4 examples.
_VARIANT_CHOICES: dict[str, list[tuple[bool, str | None]]] = {
    "normal":                 [(True,  None),     (True,  None),     (True,  None),     (True,  None)],
    "conseq_no_abstain":      [(True,  None),     (True,  None),     (True,  None),     (True,  None)],
    "conseq_random_abstain":  [(True,  "ANSWER"), (False, "ANSWER"), (True,  "ABSTAIN"), (False, "ABSTAIN")],
    "conseq_correct_abstain": [(True,  "ANSWER"), (True,  "ANSWER"), (False, "ABSTAIN"), (False, "ABSTAIN")],
    "conseq_always_submit":   [(True,  "ANSWER"), (True, "ANSWER"), (True,  "ANSWER"), (True, "ANSWER")],
    "conseq_always_abstain":  [(False,  "ABSTAIN"), (False, "ABSTAIN"), (False,  "ABSTAIN"), (False, "ABSTAIN")],
}


def _format_q(problem: str, consequence_text: str | None) -> str:
    if consequence_text:
        return f"Q: {consequence_text}\n\n{problem}"
    return f"Q: {problem}"


def _format_a(thoughts: list[str], decision: str | None, answer: str) -> str:
    lines = ["Thoughts:"]
    for i, t in enumerate(thoughts, 1):
        lines.append(f"{i}. {t}")
    lines.append("")
    if decision is not None:
        lines.append(f"Answer/Abstain decision: {decision}")
        if decision == "ABSTAIN":
            lines.append(r"Final Answer: \boxed{UNSURE}")
        else:
            lines.append(rf"Final Answer: \boxed{{{answer}}}")
    else:
        lines.append(rf"Final Answer: \boxed{{{answer}}}")
    return "\n".join(lines)


def build_preamble(variant: Variant, consequence_text: str = "") -> str:
    """Render the 4-shot preamble for the given variant.

    `consequence_text` is the prompt text (e.g. PROMPTS["cautious"]) to embed
    inline before each Q. Ignored when variant == "normal".
    """
    if variant not in _VARIANT_CHOICES:
        raise ValueError(f"Unknown variant '{variant}'. Available: {list(_VARIANT_CHOICES.keys())}")

    embed_conseq = variant != "normal"
    choices = _VARIANT_CHOICES[variant]

    blocks = []
    for ex, (use_correct, decision) in zip(EXAMPLES, choices):
        thoughts = ex["correct_thoughts"] if use_correct else ex["wrong_thoughts"]
        answer = ex["correct_answer"] if use_correct else ex["wrong_answer"]
        q = _format_q(ex["problem"], consequence_text if embed_conseq else None)
        a = _format_a(thoughts, decision, answer)
        blocks.append(f"{q}\n{a}")

    return "\n\n".join(blocks)


def format_query(problem: str, variant: Variant, consequence_text: str = "") -> str:
    """Format the actual question to be answered, ending at 'Thoughts:'.

    The model is expected to continue from "1. ..." through to "Final Answer:".
    """
    embed_conseq = variant != "normal"
    q = _format_q(problem, consequence_text if embed_conseq else None)
    return f"{q}\nThoughts:"


def build_full_prompt(problem: str, variant: Variant, consequence_text: str = "") -> str:
    """Convenience: preamble + actual query, joined by a blank line."""
    return build_preamble(variant, consequence_text) + "\n\n" + format_query(problem, variant, consequence_text)


# Stop sequences for the completions endpoint — prevent the base model from
# hallucinating a follow-up "Q: ..." block after producing its answer.
STOP_SEQUENCES = ["\nQ:", "\n\nQ:"]


VARIANTS = list(_VARIANT_CHOICES.keys())
