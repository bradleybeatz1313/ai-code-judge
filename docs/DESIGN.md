# Design

This document explains the choices behind `ai-code-judge`: the schema, the
rubric weights, and — importantly — the limits of what the static heuristics
can and cannot tell you.

## Problem schema

`problem.json`:

```json
{
  "slug": "two-sum",
  "title": "Two Sum",
  "language": "python",
  "entrypoint": "two_sum",
  "description": "Human-readable statement of the problem.",
  "reference_complexity": "O(n)",
  "security_sensitive": false,
  "candidates": [
    {"label": "model-a", "file": "model_a.py", "measured_complexity": "O(n^2)"},
    {"label": "model-b", "file": "model_b.py", "measured_complexity": "O(n)"}
  ]
}
```

- `entrypoint` — the function name every candidate solution must define.
- `reference_complexity` — the known optimal time complexity. The complexity
  dimension is scored *relative* to this, so "good" is objective rather than a
  guess.
- `measured_complexity` (per candidate) — the complexity class assigned to that
  solution. In this toolkit it is supplied as an annotation; in a fuller system
  it could be inferred from profiling across input sizes. Keeping it explicit
  keeps the scoring honest and reviewable.

`cases.json`:

```json
[
  {"name": "basic-1", "input": [[2, 7, 11, 15], 9], "expected": [0, 1]},
  {"name": "edge-negatives", "input": [[-3, 4, 3, 90], 0], "expected": [0, 2]}
]
```

- `input` is the argument list spread into the entrypoint: `fn(*input)`.
- Any case whose `name` begins with `edge` counts toward the edge-case
  dimension as well as overall correctness. This lets a problem author flag the
  inputs that actually stress the approach.

## Why these weights

```
correctness 0.40   complexity 0.20   readability 0.15   edge_cases 0.15   security 0.10
```

The guiding principle: **correctness is necessary but not sufficient.** A wrong
answer that reads beautifully is still wrong, so correctness carries the most
weight (and, combined with edge cases, a majority at 0.55). But the whole reason
this tool exists is the case where multiple solutions are all correct — there,
the remaining 0.45 does the discriminating.

The weights are not sacred. `Rubric(weights={...})` accepts any set that sums to
1.0. For a cryptography or auth problem, raising security to 0.30 and lowering
complexity is the right move. The `security_sensitive` flag on a problem is the
hook a caller would use to decide that.

## What the heuristics are — and are not

The non-correctness dimensions are scored by **transparent static heuristics**,
not by a model or by deep analysis. This is a deliberate trade-off:

**What they do well**
- Catch the obvious: missing docstrings, over-long lines, `eval`/`exec`,
  `shell=True`, SQL built by string interpolation.
- Produce a consistent first pass, so a reviewer isn't re-deriving the same
  judgments on every solution.
- Explain themselves — every score has a rationale string.

**What they cannot do**
- Judge whether a docstring is *accurate*, only whether one exists.
- Understand semantics — readability heuristics measure form, not whether the
  abstraction is well-chosen.
- Replace a security review. Absence of a flagged pattern is not proof of
  safety; it only means none of the known-bad patterns matched.

This is why the README frames the judge as a **first-pass assistant**. The
intended workflow is: the tool ranks and explains, a human reads the rationales,
and the human overrides any dimension they disagree with. The value is in
making the human's job faster and more consistent, not in removing the human.

## Complexity ordering

Complexity classes are ranked on a fixed ladder:

```
O(1) < O(log n) < O(n) < O(n log n) < O(n^2) < O(n^3) < O(2^n)
```

A solution that matches or beats the optimal scores 5.0. Each tier worse costs
1.5 points. Matching the optimal is full marks even if a theoretically faster
class exists but isn't achievable for the problem — the *reference* complexity
is the bar, not an abstract ideal.

## Execution safety

Candidate solutions are untrusted code. The runner:

1. Loads and calls each solution in a separate `multiprocessing.Process`.
2. Enforces a wall-clock timeout (default 5s) per call; a hung candidate is
   terminated and scored as a failure on that case rather than hanging the run.
3. Reports load/parse failures as a clean 0 on correctness with the traceback
   captured, instead of crashing.

A production deployment would go further — a container or seccomp sandbox,
resource limits (memory, file descriptors), and no network — but process
isolation with a timeout covers the failure modes that actually occur when
running generated code: infinite loops, exceptions, and missing entrypoints.

## Extending to other languages

The rubric, evaluator, and CLI are language-agnostic; only the *runner* is
Python-specific. Adding JavaScript would mean writing a `node_runner` that
shells out to a Node process implementing the same contract (load entrypoint,
call on each input, compare structurally) and dispatching on `problem.language`.
The scoring layer would not change.
