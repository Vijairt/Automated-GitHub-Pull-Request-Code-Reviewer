import argparse
import json
import os
import sys

from .github_client import GitHubClient
from .models import Severity
from .reviewer import Reviewer


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM pull request reviewer")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int, default=int(os.getenv("PR_NUMBER", "0")))
    parser.add_argument("--model", default=os.getenv("REVIEW_MODEL", "gpt-4o-mini"))
    parser.add_argument("--min-severity", default="high", choices=[s.value for s in Severity])
    parser.add_argument("--dry-run", action="store_true", help="Print findings instead of posting")
    args = parser.parse_args()

    if not args.repo or not args.pr:
        parser.error("--repo and --pr (or GITHUB_REPOSITORY / PR_NUMBER) are required")

    client = GitHubClient(os.environ["GITHUB_TOKEN"], args.repo)
    findings = Reviewer(args.model).review_all(client.get_changed_files(args.pr))
    threshold = Severity(args.min_severity).rank
    selected = [f for f in findings if f.severity.rank >= threshold]

    if args.dry_run:
        print(json.dumps([f.model_dump(mode="json") for f in selected], indent=2))
        return 0
    if not selected:
        print("No findings at or above threshold; nothing to post.")
        return 0

    comments = []
    for f in selected:
        body = f"**[{f.severity.value.upper()}]** {f.issue}"
        if f.suggestion:
            body += f"\n\n**Suggestion:** {f.suggestion}"
        comments.append({"path": f.file_path, "line": f.line_number, "side": "RIGHT", "body": body})

    summary = f"## 🤖 Automated Review\n\n{len(comments)} {args.min_severity}+ severity finding(s)."
    client.post_review(args.pr, client.get_head_sha(args.pr), summary, comments)
    return 0


if __name__ == "__main__":
    sys.exit(main())
