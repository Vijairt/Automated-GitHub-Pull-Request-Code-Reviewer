from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Category(str, Enum):
    DOCUMENTATION = "documentation"
    BUG = "bug"
    SECURITY = "security"
    STYLE = "style"


class ReviewComment(BaseModel):
    path: str = Field(description="File path exactly as shown in the diff")
    line: int = Field(description="Line number in the NEW version of the file", ge=1)
    category: Category
    severity: Severity
    message: str = Field(description="Concise explanation of the issue")
    suggestion: Optional[str] = Field(default=None, description="Suggested fix")


class ReviewResult(BaseModel):
    summary: str = Field(description="2-3 sentence overall assessment")
    comments: List[ReviewComment] = Field(default_factory=list)
