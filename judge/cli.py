"""Command-line interface for ai-code-judge.

Usage:
    python -m judge.cli <problem_dir>

A problem directory contains:
    problem.json   - the Problem definition + a "candidates" list
    cases.json     - the test cases
    solutions/     - one .py file per candidate

Example:
    python -m judge.cli examples/two-sum
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluator import Candidate, rank
from .rubrics.rubric import Problem


def _load_problem(problem_dir: Path) -> tuple[Problem, list[Candidate], list[dict]]:
    meta = json.loads((problem_dir / "problem.json").read_text())
    cases = json.loads((problem_dir / "cases.json").read_text())

    problem = Problem(
        slug=meta["slug"],
        title=meta["title"],
        language=meta["language"],
        entrypoint=meta["entrypoint"],
        description=meta["description"],
        reference_complexity=meta["reference_complexity"],
        security_sensitive=meta.get("security_sensitive", False),
    )

    candidates = [
        Candidate(
            label=c["label"],
            path=problem_dir / "solutions" / c["file"],
            measured_complexity=c["measured_complexity"],
        )
        for c in meta["candidates"]
    ]
    return problem, candidates, cases


def _print_verdict(verdict, as_json: bool) -> None:
    if as_json:
        payload = {
            "problem": verdict.problem.slug,
            "ranking": [
                {
                    "rank": i + 1,
                    "label": e.candidate.label,
                    "composite": e.composite,
                    "tests_passed": e.run.passed,
                    "tests_total": e.run.total,
                    "dimensions": {
                        s.dimension.value: {"score": s.score, "rationale": s.rationale}
                        for s in e.scores
                    },
                }
                for i, e in enumerate(verdict.ranked)
            ],
            "justification": verdict.justification,
        }
        print(json.dumps(payload, indent=2))
        return

    print(f"\n{'=' * 64}")
    print(f"  {verdict.problem.title}  [{verdict.problem.language}]")
    print(f"{'=' * 64}\n")
    for i, e in enumerate(verdict.ranked):
        medal = ["#1", "#2", "#3"][i] if i < 3 else f"#{i + 1}"
        print(f"{medal}  {e.summary_line()}")
        for s in e.scores:
            print(f"      {s.dimension.value:<13} {s.score:>4.1f}/5.0  {s.rationale}")
        print()
    print("-" * 64)
    print(verdict.justification)
    print("-" * 64 + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate and rank AI-generated code.")
    parser.add_argument("problem_dir", type=Path, help="Path to a problem directory")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.problem_dir.is_dir():
        print(f"error: {args.problem_dir} is not a directory", file=sys.stderr)
        return 2

    problem, candidates, cases = _load_problem(args.problem_dir)
    verdict = rank(problem, candidates, cases)
    _print_verdict(verdict, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
