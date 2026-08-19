from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.enums import FailureType, TestCaseStatus


class Evidence(BaseModel):
    type: str
    location: str
    description: str = ""


class TestFailure(BaseModel):
    failure_type: FailureType
    message: str
    root_cause: str = ""
    confidence: float = 0.0
    recoverable: bool = False


class TestResult(BaseModel):
    test_case_id: str
    status: TestCaseStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    actual_result: str = ""
    failure: TestFailure | None = None
    evidence: list[Evidence] = Field(default_factory=list)