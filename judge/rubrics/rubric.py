"""Rubric definitions for evaluating AI-generated code.

A rubric is a weighted set of dimensions. Each dimension produces a score in
[0, 5]. The weighted sum, normalized to [0, 100], is the solution's composite
score. Dimensions are deliberately separated so that a solution can be strong
on one axis (e.g. correctness) and weak on another (e.g. readability), which is
the situation a human evaluator most often has to adjudicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class Dimension(str, Enum):
    """The axes along which a solution is judged."""

    CORRECTNESS = "correctness"
    COMPLEXITY = "complexity"
    READABILITY = "readability"
    EDGE_CASES = "edge_cases"
    SECURITY = "security"


# Default weights. They sum to 1.0. Correctness dominates because a wrong
# answer that reads beautifully is still wrong, but the other axes break ties
# between solutions that all pass the tests.
DEFAULT_WEIGHTS: dict[Dimension, float] = {
    Dimension.CORRECTNESS: 0.40,
    Dimension.COMPLEXITY: 0.20,
    Dimension.READABILITY: 0.15,
    Dimension.EDGE_CASES: 0.15,
    Dimension.SECURITY: 0.10,
}

MAX_DIMENSION_SCORE = 5.0


@dataclass
class DimensionScore:
    """A single dimension's score plus the reasoning behind it."""

    dimension: Dimension
    score: float  # 0..5
    rationale: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= MAX_DIMENSION_SCORE:
            raise ValueError(
                f"{self.dimension} score {self.score} out of range [0, {MAX_DIMENSION_SCORE}]"
            )


@dataclass
class Rubric:
    """A weighted collection of dimensions."""

    weights: dict[Dimension, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def __post_init__(self) -> None:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Rubric weights must sum to 1.0, got {total:.4f}")

    def composite(self, scores: list[DimensionScore]) -> float:
        """Return the weighted composite score on a 0..100 scale."""
        by_dim = {s.dimension: s.score for s in scores}
        missing = set(self.weights) - set(by_dim)
        if missing:
            raise ValueError(f"Missing dimension scores: {sorted(d.value for d in missing)}")
        weighted = sum(self.weights[d] * by_dim[d] for d in self.weights)
        return round(weighted / MAX_DIMENSION_SCORE * 100, 2)


@dataclass
class Problem:
    """A coding problem under evaluation.

    `entrypoint` is the function name the candidate solutions must define.
    `reference_complexity` is the optimal known time complexity, used to grade
    the complexity dimension objectively rather than by vibe.
    """

    slug: str
    title: str
    language: str
    entrypoint: str
    description: str
    reference_complexity: str
    security_sensitive: bool = False


# A registry mapping a qualitative band to a numeric anchor keeps human-written
# rationales aligned with the numbers. Evaluators reference these bands so that
# "a 4" means the same thing across problems.
SCORE_BANDS: dict[int, str] = {
    5: "Exemplary — no meaningful improvement available.",
    4: "Strong — minor nits only.",
    3: "Acceptable — works but has clear room to improve.",
    2: "Weak — notable defects that a reviewer would block on.",
    1: "Poor — fundamentally flawed approach.",
    0: "Failing — does not function or is dangerous as written.",
}
