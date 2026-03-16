"""Data structures for the sequential adaptive environment."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class ScoringRubric:
    """Configurable scoring rubric."""
    correct: int = 1
    incorrect: int = -10
    skip: int = 0

    def score(self, outcome: str) -> int:
        return {"correct": self.correct, "incorrect": self.incorrect, "skipped": self.skip, "timed_out": 0}[outcome]


@dataclass
class StepRecord:
    """Record of a single step in the sequential environment."""
    step_number: int
    idx: int
    problem: str
    domain: list[str]
    difficulty: float
    source: str
    answer_gt: str
    model_generation: Optional[str] = None
    parsed_answer: Optional[str] = None
    outcome: Optional[str] = None
    score_delta: int = 0
    cumulative_score: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StepRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class EnvironmentState:
    """Full serializable state for resume."""
    seed: int
    num_questions: int
    rubric: dict
    context_mode: str
    question_order: list[int]
    history: list[dict]
    current_step: int
    cumulative_score: int
    max_history_chars: int = 0

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "EnvironmentState":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
