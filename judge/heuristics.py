"""Lightweight static heuristics for the non-correctness rubric dimensions.

These are intentionally transparent rules of thumb, not a pretense at deep
program analysis. The point of the project is to show *structured judgment*:
every number a heuristic emits comes with a human-readable rationale, and a
human evaluator is expected to override the heuristic when they disagree. The
heuristics exist to make the first pass fast and consistent, not to be the
final word.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass
class Heuristic:
    score: float  # 0..5
    rationale: str


# --- Readability -----------------------------------------------------------

_MAX_LINE = 99
_MAGIC_NUMBER = re.compile(r"(?<![\w.])-?\d{2,}(?![\w.])")


def assess_readability(source: str) -> Heuristic:
    lines = source.splitlines()
    long_lines = [i + 1 for i, ln in enumerate(lines) if len(ln) > _MAX_LINE]
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return Heuristic(0.0, f"Source does not parse: {exc}.")

    has_docstring = ast.get_docstring(tree) is not None
    func_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    documented = sum(1 for f in func_defs if ast.get_docstring(f) is not None)
    doc_ratio = documented / len(func_defs) if func_defs else 0.0

    notes: list[str] = []
    score = 5.0
    if long_lines:
        score -= min(1.5, 0.25 * len(long_lines))
        notes.append(f"{len(long_lines)} line(s) exceed {_MAX_LINE} chars")
    if not has_docstring and not documented:
        score -= 1.0
        notes.append("no module or function docstrings")
    elif doc_ratio < 0.5 and func_defs:
        score -= 0.5
        notes.append(f"only {documented}/{len(func_defs)} functions documented")

    single_char = _count_single_char_names(tree)
    if single_char > 3:
        score -= 0.5
        notes.append(f"{single_char} single-character identifiers")

    score = max(0.0, round(score, 1))
    rationale = "Clean and well-documented." if not notes else "; ".join(notes) + "."
    return Heuristic(score, rationale)


def _count_single_char_names(tree: ast.AST) -> int:
    count = 0
    common_iterators = {"i", "j", "k", "n", "x", "y", "_"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if len(node.id) == 1 and node.id not in common_iterators:
                count += 1
    return count


# --- Security --------------------------------------------------------------

_DANGER_CALLS = {"eval", "exec", "compile", "__import__"}
_SHELL_TRUE = re.compile(r"subprocess\.\w+\([^)]*shell\s*=\s*True")
_SQL_EXEC_FSTRING = re.compile(r"(execute|executemany)\s*\(\s*f[\"']", re.IGNORECASE)
_SQL_CONCAT = re.compile(r"(SELECT|INSERT|UPDATE|DELETE)[^\n]*[\"']\s*\+", re.IGNORECASE)


def _has_sql_fstring(tree: ast.AST) -> bool:
    """Detect an f-string literal that contains a SQL keyword and an
    interpolated value. Using the AST (rather than a regex) correctly handles
    f-strings that themselves contain quote characters, e.g.
    f"... WHERE username = '{username}'".
    """
    sql_kw = ("select", "insert", "update", "delete", "where", "from")
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        literal = " ".join(
            v.value for v in node.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
        ).lower()
        has_interp = any(isinstance(v, ast.FormattedValue) for v in node.values)
        if has_interp and any(kw in literal for kw in sql_kw):
            return True
    return False


def assess_security(source: str) -> Heuristic:
    findings: list[str] = []
    tree: ast.AST | None = None

    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in _DANGER_CALLS:
                    findings.append(f"use of `{node.func.id}`")
    except SyntaxError:
        tree = None

    if _SHELL_TRUE.search(source):
        findings.append("subprocess called with shell=True")

    sql_injection = bool(_SQL_EXEC_FSTRING.search(source) or _SQL_CONCAT.search(source))
    if tree is not None and _has_sql_fstring(tree):
        sql_injection = True
    if sql_injection:
        findings.append("SQL built via string interpolation (injection risk)")

    if not findings:
        return Heuristic(5.0, "No obvious dangerous patterns detected.")

    # Each distinct finding is a serious deduction; injection or eval alone
    # should pull the score below the "blocking" threshold.
    score = max(0.0, 5.0 - 2.5 * len(set(findings)))
    return Heuristic(round(score, 1), "; ".join(sorted(set(findings))) + ".")


# --- Complexity ------------------------------------------------------------

# Maps a measured complexity class to a 0..5 score, given the problem's known
# optimal. Being worse than optimal is penalized; matching or beating it scores
# full marks.
_COMPLEXITY_ORDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"]


def score_complexity(measured: str, optimal: str) -> Heuristic:
    try:
        m_idx = _COMPLEXITY_ORDER.index(measured)
        o_idx = _COMPLEXITY_ORDER.index(optimal)
    except ValueError:
        return Heuristic(3.0, f"Unrecognized complexity class ({measured} vs {optimal}).")

    gap = m_idx - o_idx
    if gap <= 0:
        return Heuristic(5.0, f"Matches or beats optimal {optimal}.")
    score = max(0.0, 5.0 - 1.5 * gap)
    return Heuristic(
        round(score, 1),
        f"{measured} is {gap} tier(s) worse than optimal {optimal}.",
    )
