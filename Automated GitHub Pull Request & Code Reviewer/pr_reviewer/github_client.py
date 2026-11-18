from typing import Dict, List

import requests

API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def get_changed_files(self, pr_number: int) -> List[Dict]:
        files, page = [], 1
        while True:
            r = self.session.get(
                f"{API}/repos/{self.repo}/pulls/{pr_number}/files",
                params={"per_page": 100, "page": page},
                timeout=30,
            )
            r.raise_for_status()
            batch = r.json()
            files.extend(batch)
            if len(batch) < 100:
                return files
            page += 1

    def get_head_sha(self, pr_number: int) -> str:
        r = self.session.get(f"{API}/repos/{self.repo}/pulls/{pr_number}", timeout=30)
        r.raise_for_status()
        return r.json()["head"]["sha"]

    def post_review(self, pr_number: int, commit_sha: str, body: str, comments: List[Dict]) -> None:
        payload = {"commit_id": commit_sha, "body": body, "event": "COMMENT", "comments": comments}
        r = self.session.post(
            f"{API}/repos/{self.repo}/pulls/{pr_number}/reviews", json=payload, timeout=30
        )
        if r.status_code == 422 and comments:
            # Invalid line anchors: fall back to a summary-only review.
            payload["comments"] = []
            payload["body"] += "\n\n" + "\n".join(
                f"- `{c['path']}:{c['line']}` {c['body']}" for c in comments
            )
            r = self.session.post(
                f"{API}/repos/{self.repo}/pulls/{pr_number}/reviews", json=payload, timeout=30
            )
        r.raise_for_status()
