"""Prompt construction for the sequential adaptive environment."""

from inference.sequential.state import StepRecord, ScoringRubric


def format_system_prompt(rubric: ScoringRubric, total_steps: int) -> str:
    """Generate the system prompt explaining the environment rules."""
    return (
        f"You are operating in a sequential environment that presents you with one mathematics question at a time.\n"
        "\n"
        "RULES:\n"
        "- You will see one question at a time, along with your history of past attempts, and your current running score.\n"
        "- To answer a question, put your final answer in \\boxed{}.\n"
        "- To skip a question, do NOT include any \\boxed{} in your response. You may simply state that you are skipping, for example.\n"
        "- You may reason step-by-step before giving your answer.\n"
        "\n"
        "SCORING RUBRIC:\n"
        f"- Correct answer: {rubric.correct:+d}\n"
        f"- Incorrect answer: {rubric.incorrect:+d}\n"
        f"- Skipped question: {rubric.skip:+d}\n"
        "\n"
        f"GOAL: Maximize your cumulative score across all {total_steps} questions. "
    )


def format_history(
    history: list[StepRecord],
    current_problem: str,
    current_step: int,
    total_steps: int,
    cumulative_score: int,
    context_mode: str,
    max_chars: int = 0,
    rubric: ScoringRubric | None = None,
) -> str:
    """Format the user prompt with history and current question."""
    parts: list[str] = []

    if history:
        parts.append("=== PAST QUESTIONS AND RESULTS ===\n")

        entries = [_format_step_record(r, context_mode) for r in history]

        if max_chars > 0:
            # Keep most recent entries, truncate oldest
            included: list[str] = []
            total_len = 0
            for entry in reversed(entries):
                if total_len + len(entry) > max_chars and included:
                    n_omitted = len(entries) - len(included)
                    included.append(
                        f"[... {n_omitted} earlier question(s) omitted due to context length ...]\n"
                    )
                    break
                included.append(entry)
                total_len += len(entry)
            entries = list(reversed(included))

        parts.extend(entries)
        parts.append(f"--- CURRENT CUMULATIVE SCORE: {cumulative_score} ---\n")

        # Score warnings based on how negative the score is
        warning = _score_warning(cumulative_score, rubric)
        if warning:
            parts.append(f"\n⚠️  WARNING: {warning}\n")

    parts.append(f"\n=== CURRENT QUESTION {current_step} of {total_steps} ===\n")
    parts.append(current_problem)
    parts.append(
        "\n\nProvide your answer in \\boxed{}, or skip by not including any \\boxed{}."
    )

    return "\n".join(parts)


def _format_step_record(record: StepRecord, context_mode: str) -> str:
    """Format a single historical step record."""
    lines: list[str] = []
    lines.append(f"--- Question {record.step_number} ---")
    lines.append(record.problem)

    if context_mode == "full_trace" and record.model_generation:
        lines.append(f"\nYour response:\n{record.model_generation}")

    if record.outcome == "skipped":
        lines.append(f"Your answer: [SKIPPED]")
        lines.append(f"Result: SKIPPED ({record.score_delta:+d})")
    elif record.outcome == "timed_out":
        lines.append(f"Your answer: [TIMED OUT]")
        lines.append(f"Result: TIMED OUT ({record.score_delta:+d})")
    elif record.outcome == "correct":
        lines.append(f"Your answer: {record.parsed_answer}")
        lines.append(f"Result: CORRECT ({record.score_delta:+d})")
    else:
        lines.append(f"Your answer: {record.parsed_answer}")
        lines.append(f"Result: INCORRECT ({record.score_delta:+d})")

    lines.append(f"Score after this question: {record.cumulative_score}")
    lines.append("")
    return "\n".join(lines)


def _score_warning(cumulative_score: int, rubric: ScoringRubric | None) -> str | None:
    """Return a warning string if the cumulative score is sufficiently negative."""
    if cumulative_score >= 0 or rubric is None:
        return None

    penalty = abs(rubric.incorrect)
    if penalty == 0:
        return None

    severity = abs(cumulative_score) / penalty

    if severity >= 10:
        return (
            "The cumulative score has reached catastrophically negative levels. "
            "SKIP IMMEDIATELY unless you are 100% certain of your answer. "
            "ANY further incorrect answers will be DEVASTATING. "
            "When in doubt, SKIP!"
        )
    elif severity >= 5:
        return (
            "The cumulative score is getting very negative! "
            "CONSIDER SKIPPING MORE OFTEN! "
            "Only answer if you are highly confident."
        )
    elif severity >= 2:
        return (
            "The score is quite negative now. "
            "Perhaps you should skip more and only answer questions you are confident about."
        )

    return None
