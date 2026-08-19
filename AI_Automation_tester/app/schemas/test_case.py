from pydantic import BaseModel, Field

from app.schemas.enums import TestCaseStatus


class TestStep(BaseModel):
    step_number: int
    action: str
    target: str = ""
    value: str = ""
    expected_result: str = ""


class TestCase(BaseModel):
    id: str
    title: str
    description: str
    priority: str = "medium"
    category: str = "functional"
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestStep] = Field(default_factory=list)
    expected_result: str
    status: TestCaseStatus = TestCaseStatus.DRAFT


class TestPlan(BaseModel):
    objective: str
    strategy: str
    test_cases: list[TestCase] = Field(default_factory=list)