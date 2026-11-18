import re
from typing import Dict, List, Set, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .models import FileReview, Finding

MAX_DIFF_LINES = 400
MAX_FILES = 30

SKIP_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "composer.lock", "Cargo.lock", "go.sum",
}
SKIP_SUFFIXES = (
    ".lock", ".min.js", ".min.css", ".map", ".svg", ".png", ".jpg", ".jpeg", ".gif",
    ".ico", ".pdf", ".zip", ".woff", ".woff2", ".ttf", ".exe", ".dll", ".md", ".txt",
)

SYSTEM_PROMPT = """You are a strict senior engineer reviewing ONE file of a pull request.

Rubric - report ONLY:
1. Logic bugs (wrong conditions, off-by-one, None/null misuse, race conditions, resource leaks).
2. Unhandled exceptions / missing error handling on I/O, network, parsing.
3. Security risks (hardcoded API keys or secrets, injection, unsafe deserialization,
   disabled TLS verification, weak crypto, missing input validation).

Do NOT report: formatting, naming, import order, line length, quote style, missing type hints,
or anything a linter handles. Do not comment on removed or unchanged lines.
Only comment on lines added in the diff, using the NEW-file line number shown as prefix.
Prefer returning no findings over speculative or pedantic ones."""

HUMAN_PROMPT = "File: {path}\n\n{diff}"


def is_reviewable(f: Dict) -> bool:
    name = f["filename"]
    base = name.rsplit("/", 1)[-1]
    return (
        bool(f.get("patch"))
        and f.get("status") != "removed"
        and base not in SKIP_NAMES
        and not name.lower().endswith(SKIP_SUFFIXES)
    )


def annotate_patch(patch: str, max_lines: int = MAX_DIFF_LINES) -> Tuple[str, Set[int], bool]:
    """Prefix lines with new-file numbers; truncate past max_lines. Returns (text, added_lines, truncated)."""
    out, valid, new_line = [], set(), 0
    raw_lines = patch.splitlines()
    truncated = len(raw_lines) > max_lines
    for raw in raw_lines[:max_lines]:
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
        if m:
            new_line = int(m.group(1))
            out.append(raw)
        elif raw.startswith("+"):
            out.append(f"{new_line}: {raw}")
            valid.add(new_line)
            new_line += 1
        elif raw.startswith("-"):
            out.append(f"     {raw}")
        else:
            out.append(f"{new_line}: {raw}")
            new_line += 1
    if truncated:
        out.append(f"... [diff truncated after {max_lines} lines]")
    return "\n".join(out), valid, truncated


class Reviewer:
    def __init__(self, model: str = "gpt-4o-mini"):
        llm = ChatOpenAI(model=model, temperature=0)
        prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])
        self.chain = prompt | llm.with_structured_output(FileReview)

    def review_file(self, f: Dict) -> List[Finding]:
        annotated, valid, _ = annotate_patch(f["patch"])
        result: FileReview = self.chain.invoke({"path": f["filename"], "diff": annotated})
        return [
            x.model_copy(update={"file_path": f["filename"]})
            for x in result.findings
            if x.line_number in valid
        ]

    def review_all(self, files: List[Dict]) -> List[Finding]:
        findings: List[Finding] = []
        for f in [f for f in files if is_reviewable(f)][:MAX_FILES]:
            try:
                findings.extend(self.review_file(f))
            except Exception as exc:
                print(f"Skipping {f['filename']}: {exc}")
        return findings
