# Automated GitHub PR Reviewer

GitHub Action that reads PR diffs, asks an LLM (LangChain + OpenAI) for a review, validates the
output with Pydantic, and posts inline comments via the GitHub REST API.

Flags: missing documentation, potential bugs, security anti-patterns.

## Setup
1. Add the repo secret `OPENAI_API_KEY`.
2. Keep `.github/workflows/pr-review.yml` at the repository root.
3. Open a PR.

## Local dry run
```
pip install -r requirements.txt
set GITHUB_TOKEN=...; set OPENAI_API_KEY=...
python -m pr_reviewer.main --repo owner/name --pr 1 --dry-run
```

## Design
- `models.py`: Pydantic schema (`ReviewResult`, `ReviewComment`) enforcing structured output.
- `reviewer.py`: diff annotation with new-file line numbers, prompt, `with_structured_output` chain.
- `github_client.py`: fetch PR files, post a single review (falls back to summary on bad anchors).
- Comments on lines outside the diff are dropped to avoid API 422 errors.

## Ideas for extension
Unit tests with a mocked LLM, severity-based failing check, `.reviewer.yml` config, webhook (FastAPI) mode.

Note: PRs from forks don't receive secrets; use `pull_request_target` carefully if needed.
