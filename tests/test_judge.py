"""Tests for ai-code-judge.

These exercise the judge's own correctness: rubric math, the static heuristics,
the sandboxed runner (including timeout and load-failure paths), and the
end-to-end ranking on the bundled examples. Run with: pytest -q
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from judge.evaluator import Candidate, rank
from judge.heuristics import (
    assess_readability,
    assess_security,
    score_complexity,
)
from judge.rubrics.rubric import (
    DEFAULT_WEIGHTS,
    Dimension,
    DimensionScore,
    Problem,
    Rubric,
)
from judge.runners.python_runner import run_solution

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


# --- Rubric ----------------------------------------------------------------

def test_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_composite_all_fives_is_100():
    rubric = Rubric()
    scores = [DimensionScore(d, 5.0, "x") for d in Dimension]
    assert rubric.composite(scores) == 100.0


def test_composite_all_zeros_is_0():
    rubric = Rubric()
    scores = [DimensionScore(d, 0.0, "x") for d in Dimension]
    assert rubric.composite(scores) == 0.0


def test_composite_weighting_is_applied():
    # Perfect except correctness=0. Correctness weight is 0.40, so we lose
    # 40% of the scale -> 60.0.
    rubric = Rubric()
    scores = [
        DimensionScore(Dimension.CORRECTNESS, 0.0, "x"),
        DimensionScore(Dimension.COMPLEXITY, 5.0, "x"),
        DimensionScore(Dimension.READABILITY, 5.0, "x"),
        DimensionScore(Dimension.EDGE_CASES, 5.0, "x"),
        DimensionScore(Dimension.SECURITY, 5.0, "x"),
    ]
    assert rubric.composite(scores) == 60.0


def test_rubric_rejects_bad_weights():
    with pytest.raises(ValueError):
        Rubric(weights={Dimension.CORRECTNESS: 0.5})


def test_dimension_score_rejects_out_of_range():
    with pytest.raises(ValueError):
        DimensionScore(Dimension.SECURITY, 9.0, "too high")


# --- Heuristics ------------------------------------------------------------

def test_readability_rewards_docstrings():
    good = textwrap.dedent('''
        """Module docstring."""
        def f(value):
            """Doc."""
            return value + 1
    ''')
    assert assess_readability(good).score >= 4.5


def test_readability_penalizes_no_docs():
    bad = "def f(x):\n    return x+1\n"
    assert assess_readability(bad).score < 5.0


def test_security_flags_eval():
    src = "def f(s):\n    return eval(s)\n"
    h = assess_security(src)
    assert h.score < 5.0
    assert "eval" in h.rationale


def test_security_flags_sql_fstring_with_inner_quotes():
    # The tricky case: an f-string containing single quotes around the field.
    src = (
        "def q(u):\n"
        "    sql = f\"SELECT * FROM users WHERE name = '{u}'\"\n"
        "    return sql\n"
    )
    h = assess_security(src)
    assert h.score < 5.0
    assert "injection" in h.rationale.lower()


def test_security_clean_code_scores_full():
    src = 'def add(a, b):\n    """Add."""\n    return a + b\n'
    assert assess_security(src).score == 5.0


def test_complexity_matches_optimal():
    assert score_complexity("O(n)", "O(n)").score == 5.0


def test_complexity_worse_is_penalized():
    worse = score_complexity("O(n^2)", "O(n)")
    assert worse.score < 5.0


def test_complexity_better_than_optimal_still_full():
    assert score_complexity("O(log n)", "O(n)").score == 5.0


# --- Runner ----------------------------------------------------------------

def test_runner_passes_correct_solution(tmp_path):
    sol = tmp_path / "s.py"
    sol.write_text("def f(a, b):\n    return a + b\n")
    cases = [
        {"name": "c1", "input": [1, 2], "expected": 3},
        {"name": "c2", "input": [0, 0], "expected": 0},
    ]
    result = run_solution(sol, "f", cases)
    assert result.passed == 2
    assert result.pass_rate == 1.0


def test_runner_detects_wrong_answer(tmp_path):
    sol = tmp_path / "s.py"
    sol.write_text("def f(a, b):\n    return a - b\n")
    cases = [{"name": "c1", "input": [1, 2], "expected": 3}]
    result = run_solution(sol, "f", cases)
    assert result.passed == 0


def test_runner_handles_missing_entrypoint(tmp_path):
    sol = tmp_path / "s.py"
    sol.write_text("def other():\n    return 1\n")
    result = run_solution(sol, "f", [{"name": "c", "input": [], "expected": 1}])
    assert result.load_error is not None
    assert result.passed == 0


def test_runner_enforces_timeout(tmp_path):
    sol = tmp_path / "s.py"
    sol.write_text("def f():\n    while True:\n        pass\n")
    cases = [{"name": "c", "input": [], "expected": 1}]
    result = run_solution(sol, "f", cases, timeout_s=1.0)
    assert result.passed == 0
    assert "timeout" in result.cases[0].error.lower()


def test_runner_treats_tuple_and_list_as_equal(tmp_path):
    sol = tmp_path / "s.py"
    sol.write_text("def f():\n    return (1, 2)\n")
    cases = [{"name": "c", "input": [], "expected": [1, 2]}]
    result = run_solution(sol, "f", cases)
    assert result.passed == 1


# --- End-to-end on bundled examples ---------------------------------------

@pytest.mark.parametrize(
    "slug,expected_winner",
    [
        ("two-sum", "model-b-hashmap"),
        ("rate-limiter", "model-b-sliding-log"),
        ("sql-injection-fix", "model-b-parameterized"),
    ],
)
def test_examples_rank_expected_winner(slug, expected_winner):
    import json

    problem_dir = EXAMPLES / slug
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
        Candidate(c["label"], problem_dir / "solutions" / c["file"], c["measured_complexity"])
        for c in meta["candidates"]
    ]
    verdict = rank(problem, candidates, cases)
    assert verdict.winner.candidate.label == expected_winner
