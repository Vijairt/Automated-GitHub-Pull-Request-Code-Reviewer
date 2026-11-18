from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return ["low", "medium", "high"].index(self.value)


class Finding(BaseModel):
    file_path: str = Field(description="File path exactly as shown in the diff header")
    line_number: int = Field(description="Line number in the NEW version of the file", ge=1)
    severity: Severity = Field(
        description="high: logic bug, unhandled exception, or security risk; "
        "medium: likely problem; low: minor"
    )
    issue: str = Field(description="One or two sentences describing the problem")
    suggestion: Optional[str] = Field(default=None, description="Concrete fix")


class FileReview(BaseModel):
    findings: List[Finding] = Field(default_factory=list)
