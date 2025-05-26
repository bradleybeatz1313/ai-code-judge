"""ai-code-judge: a structured toolkit for evaluating and ranking AI-generated code."""

from .evaluator import Candidate, Evaluation, Verdict, evaluate_candidate, rank
from .rubrics.rubric import Dimension, DimensionScore, Problem, Rubric

__version__ = "0.3.0"

__all__ = [
    "Candidate",
    "Evaluation",
    "Verdict",
    "evaluate_candidate",
    "rank",
    "Dimension",
    "DimensionScore",
    "Problem",
    "Rubric",
]
