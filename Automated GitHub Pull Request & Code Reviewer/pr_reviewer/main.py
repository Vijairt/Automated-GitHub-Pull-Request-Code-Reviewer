import argparse
import json
import os
import sys

from .github_client import GitHubClient
from .reviewer import build_diff, review_diff

ICONS = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM pull request reviewer")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int, default=int(os.getenv("PR_NUMBER", "0")))
    parser.add_argument("--model", default=os.getenv("REVIEW_MODEL", "gpt-4o-mini"))
    parser.add_argument("--dry-run", action="store_true", help="Print review instead of posting")
    args = parser.parse_args()

    if not args.repo or not args.pr:
        parser.error("--repo and --pr (or GITHUB_REPOSITORY / PR_NUMBER) are required")

    client = GitHubClient(os.environ["GITHUB_TOKEN"], args.repo)
    diff, valid_lines = build_diff(client.get_changed_files(args.pr))
    if not diff:
        print("No reviewable changes.")
        return 0

    result = review_diff(diff, args.model)
    comments = []
    for c in result.comments:
        if c.line not in valid_lines.get(c.path, set()):
            continue
        body = f"{ICONS[c.severity.value]} **{c.category.value.title()}** ({c.severity.value}): {c.message}"
        if c.suggestion:
            body += f"\n\n**Suggestion:** {c.suggestion}"
        comments.append({"path": c.path, "line": c.line, "side": "RIGHT", "body": body})

    summary = f"## 🤖 Automated Review\n\n{result.summary}\n\n{len(comments)} inline comment(s)."
    if args.dry_run:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return 0

    client.post_review(args.pr, client.get_head_sha(args.pr), summary, comments)
    return 0


if __name__ == "__main__":
    sys.exit(main())
