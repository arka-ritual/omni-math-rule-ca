"""Core sequential adaptive environment."""

import json
import os
import random
import sys

_repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, _repo_root)
sys.path.insert(0, os.path.join(_repo_root, "evaluation"))

from evaluation.grader import math_equal
from evaluation.parser import extract_answer, strip_string
from evaluation.math_eval_cautious import extract_all_boxed

from inference.sequential.state import StepRecord, ScoringRubric, EnvironmentState
from inference.sequential.formatter import format_system_prompt, format_history


class SequentialEnvironment:
    """Adaptive sequential math environment.

    Questions are presented one at a time. The model sees its history
    of past answers, outcomes, and cumulative score. It can answer
    (via \\boxed{}) or skip (no \\boxed{}).

    Deterministic given a seed. Supports save/resume.
    """

    def __init__(
        self,
        dataset_path: str = "omni_math_rule.jsonl",
        num_questions: int = 100,
        seed: int = 42,
        rubric: ScoringRubric | None = None,
        context_mode: str = "summary",
        max_history_chars: int = 0,
    ):
        self.rubric = rubric or ScoringRubric()
        self.context_mode = context_mode
        self.max_history_chars = max_history_chars
        self._seed = seed
        self._num_questions = num_questions

        # Load dataset
        dataset = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if line:
                    item = json.loads(line)
                    item.setdefault("idx", i)
                    dataset.append(item)

        # Sample and shuffle deterministically
        rng = random.Random(seed)
        indices = list(range(len(dataset)))
        if 0 < num_questions < len(indices):
            indices = rng.sample(indices, num_questions)
        rng.shuffle(indices)

        self._dataset = dataset
        self._question_order = indices
        self._history: list[StepRecord] = []
        self._current_step = 0
        self._cumulative_score = 0

    # -- Properties --

    @property
    def done(self) -> bool:
        return self._current_step >= len(self._question_order)

    @property
    def current_step(self) -> int:
        return self._current_step

    @property
    def total_steps(self) -> int:
        return len(self._question_order)

    @property
    def cumulative_score(self) -> int:
        return self._cumulative_score

    @property
    def history(self) -> list[StepRecord]:
        return list(self._history)

    # -- Core API --

    def get_prompts(self) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the current step."""
        if self.done:
            raise StopIteration("No more questions")

        item = self._current_item()

        system_prompt = format_system_prompt(
            rubric=self.rubric,
            total_steps=self.total_steps,
        )

        user_prompt = format_history(
            history=self._history,
            current_problem=item.get("problem") or item.get("question", ""),
            current_step=self._current_step + 1,
            total_steps=self.total_steps,
            cumulative_score=self._cumulative_score,
            context_mode=self.context_mode,
            max_chars=self.max_history_chars,
            rubric=self.rubric,
        )

        return system_prompt, user_prompt

    def step(self, model_generation: str, outcome_override: str | None = None) -> StepRecord:
        """Process the model's response. Returns the completed StepRecord.

        If outcome_override is set (e.g. "timed_out"), skip normal grading
        and use that outcome with 0 score delta.
        """
        if self.done:
            raise StopIteration("No more questions")

        item = self._current_item()

        if outcome_override:
            outcome = outcome_override
            parsed_answer = None
            score_delta = self.rubric.score(outcome)
        else:
            gt_answer = strip_string(item["answer"])

            # Parse response
            all_boxed = extract_all_boxed(model_generation or "")

            if not all_boxed:
                outcome = "skipped"
                parsed_answer = None
            else:
                parsed_answer = strip_string(extract_answer(model_generation, "omni-math"))
                outcome = "correct" if math_equal(parsed_answer, gt_answer) else "incorrect"

            score_delta = self.rubric.score(outcome)
        self._cumulative_score += score_delta

        record = StepRecord(
            step_number=self._current_step + 1,
            idx=item["idx"],
            problem=item.get("problem") or item.get("question", ""),
            domain=item.get("domain", []),
            difficulty=item.get("difficulty", 0.0),
            source=item.get("source", ""),
            answer_gt=item["answer"],
            model_generation=model_generation,
            parsed_answer=parsed_answer,
            outcome=outcome,
            score_delta=score_delta,
            cumulative_score=self._cumulative_score,
        )

        self._history.append(record)
        self._current_step += 1
        return record

    # -- Save / Resume --

    def save_state(self, path: str):
        """Serialize full state for resume."""
        state = EnvironmentState(
            seed=self._seed,
            num_questions=self._num_questions,
            rubric={"correct": self.rubric.correct, "incorrect": self.rubric.incorrect, "skip": self.rubric.skip},
            context_mode=self.context_mode,
            question_order=self._question_order,
            history=[r.to_dict() for r in self._history],
            current_step=self._current_step,
            cumulative_score=self._cumulative_score,
            max_history_chars=self.max_history_chars,
        )
        state.save(path)

    @classmethod
    def from_state(cls, state_path: str, dataset_path: str = "omni_math_rule.jsonl") -> "SequentialEnvironment":
        """Resume from a saved state."""
        state = EnvironmentState.load(state_path)
        env = cls.__new__(cls)
        env.rubric = ScoringRubric(**state.rubric)
        env.context_mode = state.context_mode
        env.max_history_chars = state.max_history_chars
        env._seed = state.seed
        env._num_questions = state.num_questions

        dataset = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if line:
                    item = json.loads(line)
                    item.setdefault("idx", i)
                    dataset.append(item)

        env._dataset = dataset
        env._question_order = state.question_order
        env._history = [StepRecord.from_dict(d) for d in state.history]
        env._current_step = state.current_step
        env._cumulative_score = state.cumulative_score
        return env

    # -- Internals --

    def _current_item(self) -> dict:
        return self._dataset[self._question_order[self._current_step]]
