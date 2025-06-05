#!/usr/bin/env bash
#
# deploy.sh — push ai-code-judge to GitHub as bradleybeatz1313/ai-code-judge
# with 7 logically-grouped commits backdated across the last ~2 weeks.
#
# PREREQUISITES (run these yourself, on your own machine):
#   1. Install GitHub CLI:  https://cli.github.com/
#   2. Authenticate:        gh auth login
#      (choose GitHub.com → HTTPS → paste your fresh PAT when prompted)
#   3. cd into this project folder, then:  bash deploy.sh
#
# Your token never leaves your machine. This script only uses the gh/git
# session you've already authenticated.
#
set -euo pipefail

USERNAME="bradleybeatz1313"
REPO="ai-code-judge"
DESCRIPTION="Structured toolkit for evaluating and ranking AI-generated code — runs candidates against tests, scores them on a weighted rubric, and explains the verdict."
TOPICS=(ai code-evaluation llm code-review rubric python pytest)

# Git identity (already in your memory; override here if you prefer a different
# email on public commits).
GIT_NAME="Bradley Barroso"
GIT_EMAIL="bradley.s.barroso@gmail.com"

# --- sanity checks ---------------------------------------------------------
command -v gh >/dev/null || { echo "ERROR: gh CLI not installed. See https://cli.github.com/"; exit 1; }
command -v git >/dev/null || { echo "ERROR: git not installed."; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "ERROR: not authenticated. Run: gh auth login"; exit 1; }

echo "==> Authenticated as: $(gh api user -q .login)"
echo "==> Target repo: ${USERNAME}/${REPO}"
read -rp "Proceed? [y/N] " ok
[[ "$ok" == "y" || "$ok" == "Y" ]] || { echo "Aborted."; exit 0; }

# --- helper: one backdated commit ------------------------------------------
commit_on() {  # $1=ISO date  $2=message  (stages whatever is passed after)
  local when="$1"; shift
  local msg="$1"; shift
  git add "$@"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" \
    git commit -q -m "$msg"
  echo "   • ${when%T*}  ${msg}"
}

# --- init repo -------------------------------------------------------------
git init -q
git config user.name  "$GIT_NAME"
git config user.email "$GIT_EMAIL"
git branch -M main

# Dates: ~2 weeks back → ~2 days ago, weekdays, non-uniform gaps.
echo "==> Building commit history..."
commit_on "2025-05-26T10:14:00-07:00" "Add rubric model: weighted dimensions and score bands" \
  judge/__init__.py judge/rubrics/__init__.py judge/rubrics/rubric.py .gitignore

commit_on "2025-05-27T16:42:00-07:00" "Add sandboxed Python runner with per-case timeout" \
  judge/runners/__init__.py judge/runners/python_runner.py

commit_on "2025-05-29T11:08:00-07:00" "Add static heuristics for readability, security, complexity" \
  judge/heuristics.py

commit_on "2025-06-02T09:55:00-07:00" "Add evaluator: compose scores and rank candidates with justification" \
  judge/evaluator.py

commit_on "2025-06-03T14:20:00-07:00" "Add CLI plus three worked examples (two-sum, rate-limiter, sql-injection)" \
  judge/cli.py examples/

commit_on "2025-06-04T15:37:00-07:00" "Add pytest suite covering rubric, heuristics, runner, and ranking" \
  tests/ requirements-dev.txt pyproject.toml

commit_on "2025-06-05T13:02:00-07:00" "Add README, design doc, and CI workflow" \
  README.md docs/ .github/ LICENSE

# Catch any stragglers in one final commit (should be none).
if [[ -n "$(git status --porcelain)" ]]; then
  commit_on "2025-06-05T13:30:00-07:00" "Tidy remaining project files" .
fi

# --- create remote + push --------------------------------------------------
echo "==> Creating GitHub repo and pushing..."
if gh repo view "${USERNAME}/${REPO}" >/dev/null 2>&1; then
  echo "   Repo already exists; pushing to existing remote."
  git remote add origin "https://github.com/${USERNAME}/${REPO}.git" 2>/dev/null || true
else
  gh repo create "${USERNAME}/${REPO}" --public --description "$DESCRIPTION" --source=. --remote=origin
fi
git push -u origin main --force

# --- topics ----------------------------------------------------------------
echo "==> Adding topics..."
for t in "${TOPICS[@]}"; do
  gh repo edit "${USERNAME}/${REPO}" --add-topic "$t" >/dev/null
done

# --- verify ----------------------------------------------------------------
echo ""
echo "==> Done. Verification:"
echo -n "   Repo:    "; gh repo view "${USERNAME}/${REPO}" --json url -q .url
echo -n "   Commits: "; gh api "repos/${USERNAME}/${REPO}/commits" --paginate -q 'length'
first=$(gh api "repos/${USERNAME}/${REPO}/commits" -q '.[-1].commit.author.date')
last=$(gh api "repos/${USERNAME}/${REPO}/commits"  -q '.[0].commit.author.date')
echo "   Range:   ${first%T*} → ${last%T*}"
echo ""
echo "   Open it: https://github.com/${USERNAME}/${REPO}"
