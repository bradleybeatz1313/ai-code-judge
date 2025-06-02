"""The evaluator: score candidate solutions and rank them.

This is the orchestration layer. Given a `Problem`, its test cases, and a set
of candidate solution files, it:

  1. runs each solution against the test cases (correctness + edge cases),
  2. applies static heuristics (readability + security),
  3. takes a complexity annotation per candidate (the optimal is known; the
     candidate's measured class is supplied by the harness or a human),
  4. composes a rubric score, and
  5. ranks the candidates, emitting a verdict with per-dimension rationale.

The output mirrors what a Project-Vox-style reviewer produces: a ranking plus
a written justification for *why* one solution beats another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .heuristics import assess_readability, assess_security, score_complexity
from .rubrics.rubric import (
    Dimension,
    DimensionScore,
    Problem,
    Rubric,
)
from .runners.python_runner import RunResult, run_solution


@dataclass
class Candidate:
    """A single AI-generated solution to evaluate.

    `measured_complexity` is the time-complexity class the harness (or a human)
    assigns to this solution, e.g. "O(n)". It is compared against the problem's
    known optimal to score the complexity dimension objectively.
    """

    label: str  # e.g. "model-a", "gpt-style", "claude-style"
    path: Path
    measured_complexity: str


@dataclass
class Evaluation:
    candidate: Candidate
    run: RunResult
    scores: list[DimensionScore]
    composite: float

    def summary_line(self) -> str:
        return (
            f"{self.candidate.label:<16} "
            f"composite={self.composite:6.2f}  "
            f"tests={self.run.passed}/{self.run.total}"
        )


@dataclass
class Verdict:
    problem: Problem
    ranked: list[Evaluation]  # best first
    justification: str = field(default="")

    @property
    def winner(self) -> Evaluation:
        return self.ranked[0]


def _correctness_score(run: RunResult) -> DimensionScore:
    if run.load_error:
        return DimensionScore(
            Dimension.CORRECTNESS, 0.0, "Solution failed to load/parse."
        )
    rate = run.pass_rate
    score = round(rate * 5.0, 1)
    rationale = f"Passes {run.passed}/{run.total} cases ({rate:.0%})."
    return DimensionScore(Dimension.CORRECTNESS, score, rationale)


def _edge_case_score(run: RunResult) -> DimensionScore:
    """Edge-case strength = pass rate on the cases explicitly tagged 'edge'.

    Cases are named; any case whose name starts with 'edge' counts toward this
    dimension. This rewards solutions that handle the gnarly inputs, not just
    the happy path.
    """
    if run.load_error or not run.cases:
        return DimensionScore(Dimension.EDGE_CASES, 0.0, "No runnable edge cases.")
    edge = [c for c in run.cases if c.name.lower().startswith("edge")]
    if not edge:
        return DimensionScore(
            Dimension.EDGE_CASES, 3.0, "No dedicated edge cases; assumed neutral."
        )
    passed = sum(1 for c in edge if c.passed)
    rate = passed / len(edge)
    return DimensionScore(
        Dimension.EDGE_CASES,
        round(rate * 5.0, 1),
        f"Handles {passed}/{len(edge)} edge cases.",
    )


def evaluate_candidate(
    problem: Problem,
    candidate: Candidate,
    cases: list[dict],
    rubric: Rubric,
) -> Evaluation:
    run = run_solution(candidate.path, problem.entrypoint, cases)
    source = candidate.path.read_text()

    readability = assess_readability(source)
    security = assess_security(source)
    complexity = score_complexity(candidate.measured_complexity, problem.reference_complexity)

    scores = [
        _correctness_score(run),
        DimensionScore(Dimension.COMPLEXITY, complexity.score, complexity.rationale),
        DimensionScore(Dimension.READABILITY, readability.score, readability.rationale),
        _edge_case_score(run),
        DimensionScore(Dimension.SECURITY, security.score, security.rationale),
    ]
    composite = rubric.composite(scores)
    return Evaluation(candidate=candidate, run=run, scores=scores, composite=composite)


def _build_justification(ranked: list[Evaluation]) -> str:
    if len(ranked) == 1:
        return f"Only one candidate evaluated: {ranked[0].candidate.label}."

    best, runner_up = ranked[0], ranked[1]
    lines = [
        f"Winner: {best.candidate.label} (composite {best.composite:.2f}) "
        f"over {runner_up.candidate.label} ({runner_up.composite:.2f}).",
        "",
        "Deciding dimensions:",
    ]
    best_by_dim = {s.dimension: s for s in best.scores}
    ru_by_dim = {s.dimension: s for s in runner_up.scores}
    for dim in Dimension:
        b, r = best_by_dim[dim], ru_by_dim[dim]
        if abs(b.score - r.score) >= 0.5:
            leader = best if b.score > r.score else runner_up
            delta = abs(b.score - r.score)
            lines.append(
                f"  - {dim.value}: {leader.candidate.label} leads by {delta:.1f} "
                f"({b.score:.1f} vs {r.score:.1f}) — {best_by_dim[dim].rationale}"
            )
    if len(lines) == 3:  # no dimension differed by >= 0.5
        lines.append("  - Margins are thin across all dimensions; near tie.")
    return "\n".join(lines)


def rank(
    problem: Problem,
    candidates: list[Candidate],
    cases: list[dict],
    rubric: Rubric | None = None,
) -> Verdict:
    rubric = rubric or Rubric()
    evals = [evaluate_candidate(problem, c, cases, rubric) for c in candidates]
    # Sort by composite desc, breaking ties by raw test pass count.
    evals.sort(key=lambda e: (e.composite, e.run.passed), reverse=True)
    return Verdict(problem=problem, ranked=evals, justification=_build_justification(evals))
