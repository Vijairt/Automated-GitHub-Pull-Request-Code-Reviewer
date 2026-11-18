import re
from typing import Dict, List, Set

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .models import ReviewResult

SYSTEM_PROMPT = """You are a senior engineer reviewing a pull request.
Only comment on lines ADDED in the diff. Look for:
1. Missing or outdated documentation (docstrings, README/API docs for new public behavior).
2. Potential bugs (off-by-one, None handling, unhandled errors, race conditions, resource leaks).
3. Security anti-patterns (hardcoded secrets, SQL/command injection, unsafe deserialization,
   weak crypto, missing input validation, disabled TLS verification).
Be specific and avoid nitpicks. Use line numbers of the NEW file. If nothing is wrong, return no comments."""

HUMAN_PROMPT = "Review this diff. Each line is prefixed with its new-file line number.\n\n{diff}"

MAX_DIFF_CHARS = 60_000
SKIP_SUFFIXES = (".lock", ".png", ".jpg", ".svg", ".min.js", ".json")


def annotate_patch(patch: str) -> (str, Set[int]):
    """Prefix added/context lines with new-file line numbers; return valid commentable lines."""
    out, valid, new_line = [], set(), 0
    for raw in patch.splitlines():
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
        if m:
            new_line = int(m.group(1))
            out.append(raw)
        elif raw.startswith("+"):
            out.append(f"{new_line}: {raw}")
            valid.add(new_line)
            new_line += 1
        elif raw.startswith("-"):
            out.append(f"   {raw}")
        else:
            out.append(f"{new_line}: {raw}")
            new_line += 1
    return "\n".join(out), valid


def build_diff(files: List[Dict]) -> (str, Dict[str, Set[int]]):
    parts, valid_lines, size = [], {}, 0
    for f in files:
        patch = f.get("patch")
        if not patch or f["filename"].endswith(SKIP_SUFFIXES):
            continue
        annotated, valid = annotate_patch(patch)
        chunk = f"### FILE: {f['filename']}\n{annotated}\n"
        if size + len(chunk) > MAX_DIFF_CHARS:
            break
        parts.append(chunk)
        valid_lines[f["filename"]] = valid
        size += len(chunk)
    return "\n".join(parts), valid_lines


def review_diff(diff: str, model: str = "gpt-4o-mini") -> ReviewResult:
    llm = ChatOpenAI(model=model, temperature=0)
    chain = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)]
    ) | llm.with_structured_output(ReviewResult)
    return chain.invoke({"diff": diff})
