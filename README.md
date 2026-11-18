# Automated GitHub Pull Request & Code Reviewer

A GitHub Action that automatically reviews pull requests with an LLM. It fetches each PR's changed
files, filters out non-code, reviews every file separately against a strict rubric, validates the
model output with Pydantic, and posts high-severity findings as inline review comments.

**Stack:** Python 3.11, LangChain (`langchain-openai`), Pydantic v2, GitHub REST API, GitHub Actions.

## Features

- Runs automatically when a PR is opened, updated, or reopened.
- Reviews file-by-file to stay within LLM context limits.
- Skips lockfiles, images, binaries, minified files, source maps, and `.md`/`.txt` files.
- Truncates diffs over 400 lines and reviews at most 30 files per PR.
- Enforces a JSON schema via `with_structured_output`, so responses are always valid.
- Targets only logic bugs, unhandled exceptions, and security risks (e.g. hardcoded secrets).
- Ignores formatting and style nitpicks that linters already handle.
- Posts only findings at or above a severity threshold (default: `high`).
- Discards comments on lines that are not part of the diff to avoid GitHub API errors.

## Architecture & Flow

```
PR opened/updated
	  |
	  v
GitHub Actions workflow (.github/workflows/pr-review.yml)
	  |
	  v
GitHubClient.get_changed_files()   -> file metadata + per-file patch (REST API)
	  |
	  v
is_reviewable()                    -> drop lockfiles, images, binaries, removed files
	  |
	  v
annotate_patch()                   -> prefix lines with new-file numbers, truncate long diffs
	  |
	  v
LangChain chain (prompt + rubric)  -> ChatOpenAI.with_structured_output(FileReview)
	  |
	  v
Validate line numbers + severity filter
	  |
	  v
GitHubClient.post_review()         -> one review with inline comments
```

## Project Structure

```
.github/workflows/pr-review.yml        Workflow triggered on pull_request events
Automated GitHub Pull Request & Code Reviewer/
  requirements.txt                     Python dependencies
  pr_reviewer/
	models.py                          Pydantic schema: Finding, FileReview, Severity
	reviewer.py                        Filtering, diff annotation, LangChain chain
	github_client.py                   GitHub REST API wrapper
	main.py                            CLI entry point
```

## Output Schema

Each finding returned by the model is validated against:

| Field         | Type                       | Description                                  |
|---------------|----------------------------|----------------------------------------------|
| `file_path`   | string                     | File path as shown in the diff               |
| `line_number` | integer (>= 1)             | Line in the new version of the file          |
| `severity`    | `low` / `medium` / `high`  | high = bug, unhandled exception, security    |
| `issue`       | string                     | Description of the problem                   |
| `suggestion`  | string or null             | Suggested fix                                |

## Setup

1. Fork or clone this repository.
2. Create an OpenAI API key and add it as a repository secret named `OPENAI_API_KEY`
   (Settings > Secrets and variables > Actions).
3. Ensure `.github/workflows/pr-review.yml` is at the repository root.
4. Open a pull request. The review is posted automatically.

`GITHUB_TOKEN` is provided by Actions. The workflow grants it `pull-requests: write` and
`contents: read`, which is all the reviewer needs.

## Configuration

| Option / env var                  | Default        | Description                                      |
|-----------------------------------|----------------|--------------------------------------------------|
| `--repo` / `GITHUB_REPOSITORY`    | -              | Repository in `owner/name` form                  |
| `--pr` / `PR_NUMBER`              | -              | Pull request number                              |
| `--model` / `REVIEW_MODEL`        | `gpt-4o-mini`  | OpenAI chat model                                |
| `--min-severity`                  | `high`         | Minimum severity to post (`low`/`medium`/`high`) |
| `--dry-run`                       | off            | Print findings as JSON instead of posting        |
| `GITHUB_TOKEN`                    | -              | Token with PR read/write access (required)       |
| `OPENAI_API_KEY`                  | -              | OpenAI key (required)                            |

Tunable constants in `reviewer.py`: `MAX_DIFF_LINES`, `MAX_FILES`, `SKIP_NAMES`, `SKIP_SUFFIXES`,
and the review rubric in `SYSTEM_PROMPT`.

## Run Locally

```powershell
cd "Automated GitHub Pull Request & Code Reviewer"
pip install -r requirements.txt
$env:GITHUB_TOKEN = "<personal access token>"
$env:OPENAI_API_KEY = "<openai key>"
python -m pr_reviewer.main --repo Vijairt/Automated-GitHub-Pull-Request-Code-Reviewer --pr 1 --dry-run
```

Remove `--dry-run` to post the review to the PR.

## Design Decisions

- **Token overflow:** each file is a separate LLM call, and large diffs are truncated by line count.
  A failure on one file is logged and does not stop the rest.
- **Noisy feedback:** the rubric explicitly bans style, naming, and formatting comments, and tells the
  model to return nothing rather than guess. Only `high` severity is posted by default.
- **Reliable anchors:** the diff is annotated with new-file line numbers, and any finding on a line
  not added in the diff is dropped. If GitHub still rejects the inline positions (HTTP 422), the
  findings are posted in the review summary instead.
- **Determinism:** temperature is 0 to keep reviews consistent between runs.

## Limitations

- GitHub omits `patch` for very large or binary files; those files are not reviewed.
- Only the first 400 lines of each file's diff are analyzed.
- PRs from forks do not receive repository secrets, so the workflow will fail on them. Using
  `pull_request_target` is possible but must be done carefully, since it runs with elevated permissions.
- LLM output can be wrong; treat comments as suggestions, not a replacement for human review.
- Each push to a PR posts a new review; earlier reviews are not deduplicated.

## Roadmap

- Unit tests with a mocked LLM and sample patches.
- Skip lines already commented on in earlier reviews.
- Optional failing check when high-severity findings exist.
- Per-repo config file (`.reviewer.yml`) for ignore globs and rubric tweaks.
- Webhook (FastAPI) deployment mode.
