"""Execute Python candidate solutions against a set of test cases.

Solutions are run in a separate subprocess with a wall-clock timeout so that an
infinite loop in a candidate solution cannot hang the judge. The candidate file
must define the problem's `entrypoint` function; the runner imports it by path,
calls it on each test input, and compares against the expected output.
"""

from __future__ import annotations

import importlib.util
import json
import multiprocessing as mp
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CaseResult:
    name: str
    passed: bool
    expected: Any
    got: Any
    error: str | None
    duration_ms: float


@dataclass
class RunResult:
    total: int
    passed: int
    cases: list[CaseResult]
    load_error: str | None = None

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def _load_entrypoint(solution_path: Path, entrypoint: str):
    spec = importlib.util.spec_from_file_location("candidate", solution_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec for {solution_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    if not hasattr(module, entrypoint):
        raise AttributeError(f"solution does not define '{entrypoint}'")
    return getattr(module, entrypoint)


def _worker(solution_path: str, entrypoint: str, args: list, q: mp.Queue) -> None:
    """Run a single call in a child process and put (ok, value_or_error)."""
    try:
        fn = _load_entrypoint(Path(solution_path), entrypoint)
        result = fn(*args)
        q.put((True, result))
    except Exception:  # noqa: BLE001 - we want every failure mode reported
        q.put((False, traceback.format_exc()))


def _call_with_timeout(
    solution_path: Path, entrypoint: str, args: list, timeout_s: float
) -> tuple[bool, Any]:
    q: mp.Queue = mp.Queue()
    proc = mp.Process(target=_worker, args=(str(solution_path), entrypoint, args, q))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        return False, f"timeout after {timeout_s}s"
    if q.empty():
        return False, "process exited without returning a result"
    return q.get()


def run_solution(
    solution_path: Path,
    entrypoint: str,
    cases: list[dict],
    timeout_s: float = 5.0,
) -> RunResult:
    """Run all test cases against a candidate solution.

    Each case is a dict: {"name": str, "input": [...args], "expected": value}.
    """
    # Fail fast if the file can't even be loaded — that is itself a 0 on
    # correctness, reported cleanly rather than as a crash.
    try:
        _load_entrypoint(solution_path, entrypoint)
    except Exception:  # noqa: BLE001
        return RunResult(
            total=len(cases),
            passed=0,
            cases=[],
            load_error=traceback.format_exc(),
        )

    results: list[CaseResult] = []
    for case in cases:
        args = case["input"]
        expected = case["expected"]
        start = time.perf_counter()
        ok, value = _call_with_timeout(solution_path, entrypoint, args, timeout_s)
        duration_ms = (time.perf_counter() - start) * 1000
        if ok:
            passed = _structurally_equal(value, expected)
            results.append(
                CaseResult(case["name"], passed, expected, value, None, duration_ms)
            )
        else:
            results.append(
                CaseResult(case["name"], False, expected, None, str(value), duration_ms)
            )

    passed = sum(1 for r in results if r.passed)
    return RunResult(total=len(results), passed=passed, cases=results)


def load_cases(cases_path: Path) -> list[dict]:
    return json.loads(cases_path.read_text())


def _structurally_equal(a: object, b: object) -> bool:
    """Compare values while treating tuples and lists as equivalent.

    Candidate solutions often return tuples where the JSON-encoded `expected`
    can only be a list (JSON has no tuple type). Normalizing both sides to
    lists before comparison avoids penalizing a correct solution for a
    serialization artifact rather than a real behavioral difference.
    """
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_structurally_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(
            _structurally_equal(a[k], b[k]) for k in a
        )
    return a == b
