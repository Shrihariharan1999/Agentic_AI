from typing import TypedDict

from app.schemas.test_case import TestPlan
from app.schemas.test_result import TestResult
from app.schemas.website import WebsiteMap
from app.schemas.workflow import HealingAttempt, HumanIntervention, WorkflowError


class TestRunState(TypedDict, total=False):
    run_id: str
    user_id: str
    target_url: str
    environment: str
    status: str

    website_map: WebsiteMap
    test_plan: TestPlan
    test_results: list[TestResult]

    current_test_case_id: str
    current_step_number: int

    human_intervention: HumanIntervention
    healing_attempts: list[HealingAttempt]

    errors: list[WorkflowError]

    final_summary: str