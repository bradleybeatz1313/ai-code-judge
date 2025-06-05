# ai-code-judge

A structured toolkit for **evaluating and ranking AI-generated code**. Given
two or more candidate solutions to the same programming problem, it runs them
against a test harness, scores each on a weighted rubric, and produces a ranked
verdict with a written justification for *why* one solution beats another.

It is built around the same task a human code reviewer performs when comparing
model outputs: judge correctness, weigh engineering quality, and articulate the
reasoning behind the ranking.

```
$ python -m judge.cli examples/two-sum

================================================================
  Two Sum  [python]
================================================================

#1  model-b-hashmap     composite=100.00  tests=6/6
      correctness    5.0/5.0  Passes 6/6 cases (100%).
      complexity     5.0/5.0  Matches or beats optimal O(n).
      readability    5.0/5.0  Clean and well-documented.
      edge_cases     5.0/5.0  Handles 3/3 edge cases.
      security       5.0/5.0  No obvious dangerous patterns detected.

#2  model-a-bruteforce  composite= 85.00  tests=6/6
      correctness    5.0/5.0  Passes 6/6 cases (100%).
      complexity     2.0/5.0  O(n^2) is 2 tier(s) worse than optimal O(n).
      readability    4.0/5.0  no module or function docstrings.
      edge_cases     5.0/5.0  Handles 3/3 edge cases.
      security       5.0/5.0  No obvious dangerous patterns detected.

----------------------------------------------------------------
Winner: model-b-hashmap (composite 100.00) over model-a-bruteforce (85.00).

Deciding dimensions:
  - complexity: model-b-hashmap leads by 3.0 (5.0 vs 2.0) — Matches or beats optimal O(n).
  - readability: model-b-hashmap leads by 1.0 (5.0 vs 4.0) — Clean and well-documented.
----------------------------------------------------------------
```

## Why this exists

When two AI-generated solutions both "look right," the interesting work is
deciding which is *actually* better and being able to defend that call. Both
solutions to Two Sum above are correct — they pass every test — so correctness
alone can't separate them. The judge surfaces the real differentiators
(complexity, documentation) and ranks accordingly. That is the core competency
this project demonstrates: turning a fuzzy "which is better?" into a defensible,
dimension-by-dimension verdict.

## The rubric

Each solution is scored 0–5 on five dimensions, combined into a 0–100 composite
with these default weights:

| Dimension     | Weight | How it's scored |
|---------------|--------|-----------------|
| Correctness   | 40%    | Pass rate against the test cases (executed in a sandboxed subprocess). |
| Complexity    | 20%    | Measured time-complexity class vs. the problem's known optimal. |
| Readability   | 15%    | Static heuristics: docstrings, line length, naming, structure. |
| Edge cases    | 15%    | Pass rate on cases explicitly tagged `edge-*`. |
| Security      | 10%    | Static detection of dangerous patterns (`eval`, `shell=True`, SQL string interpolation). |

Weights are configurable — a security-sensitive problem can up-weight the
security axis. Correctness dominates by design, but the other four break ties
between solutions that all pass.

Every score carries a one-line rationale, because a number without a reason is
useless to a reviewer. The judge is a **first-pass assistant, not an oracle**:
the heuristics are deliberately transparent so a human can override any score
they disagree with.

## Worked examples

Three example problems, each chosen to isolate a different kind of judgment:

| Example | What it tests | The interesting call |
|---------|---------------|----------------------|
| [`two-sum`](examples/two-sum) | Two correct solutions | Both pass all tests; the optimal + documented one wins on complexity and readability. |
| [`rate-limiter`](examples/rate-limiter) | A subtle correctness bug | A fixed-window limiter looks fine but wrongly allows a burst straddling a bucket boundary; the sliding-window solution catches it. |
| [`sql-injection-fix`](examples/sql-injection-fix) | A security trap | An f-string query is rejected on correctness *and* security; the parameterized version wins decisively. |

The rate-limiter case is the most instructive: the buggy solution passes 4 of 5
tests and only fails the one edge case that exposes the flawed approach —
exactly the kind of near-miss a careful evaluator has to catch.

## Usage

```bash
# Human-readable verdict
python -m judge.cli examples/rate-limiter

# Machine-readable JSON (for piping into a larger pipeline)
python -m judge.cli examples/rate-limiter --json
```

### Evaluating your own problem

Create a directory with this layout:

```
my-problem/
├── problem.json      # Problem metadata + candidate list
├── cases.json        # Test cases: [{name, input, expected}, ...]
└── solutions/
    ├── model_a.py    # Each defines the problem's entrypoint function
    └── model_b.py
```

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full schema and scoring details.

## Programmatic API

```python
from pathlib import Path
from judge import Problem, Candidate, rank

problem = Problem(
    slug="two-sum", title="Two Sum", language="python",
    entrypoint="two_sum", description="...", reference_complexity="O(n)",
)
candidates = [
    Candidate("model-a", Path("solutions/model_a.py"), measured_complexity="O(n^2)"),
    Candidate("model-b", Path("solutions/model_b.py"), measured_complexity="O(n)"),
]
cases = [{"name": "basic-1", "input": [[2, 7, 11, 15], 9], "expected": [0, 1]}]

verdict = rank(problem, candidates, cases)
print(verdict.winner.candidate.label)   # -> "model-b"
print(verdict.justification)
```

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The suite (22 tests) covers the rubric math, each static heuristic, the
sandboxed runner's timeout and load-failure paths, and end-to-end ranking on all
three bundled examples.

## Design notes

- **Execution is sandboxed.** Candidate code runs in a separate process with a
  wall-clock timeout, so an infinite loop or crash in a candidate can't take
  down the judge.
- **JSON has no tuples.** The runner compares results structurally, treating
  tuples and lists as equivalent, so a correct solution isn't penalized for a
  serialization artifact.
- **Heuristics use the AST, not just regexes**, where it matters — e.g. SQL
  f-string detection works even when the string itself contains quote
  characters.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the reasoning behind the rubric
weights and the limits of the static heuristics.

## License

MIT — see [LICENSE](LICENSE).
