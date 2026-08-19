import pytest
from app.services.run_manager import run_manager
from app.schemas.website import WebsiteMap
from app.schemas.test_case import TestPlan, TestCase, TestStep
from app.schemas.test_result import TestResult, TestCaseStatus
from app.agents.planner import planner_agent
from app.agents.test_writer import test_writer_agent
from app.agents.summarizer import summarizer_agent


def test_run_manager_lifecycle():
    run_id = "test_run_lifecycle_001"
    target_url = "https://example.com"
    
    # 1. Init
    data = run_manager.init_run(run_id, target_url, "staging")
    assert data["run_id"] == run_id
    assert data["status"] == "created"
    assert len(data["logs"]) >= 1

    # 2. Stage update
    run_manager.update_stage(run_id, "planning", "Designing Tests", 45)
    run = run_manager.get_run(run_id)
    assert run["status"] == "planning"
    assert run["progress_percent"] == 45
    assert run["current_stage"] == "Designing Tests"

    # 3. Discovered map update
    mock_map = {
        "url": target_url,
        "title": "Example Domain",
        "description": "Example website for testing",
        "links": [{"href": "https://iana.org", "text": "More information"}],
        "buttons": [{"selector": "button#submit", "text": "Submit"}],
        "inputs": [{"name": "q", "type": "text"}],
        "forms": [],
    }
    run_manager.update_website_map(run_id, mock_map)
    run = run_manager.get_run(run_id)
    assert run["website_map"]["title"] == "Example Domain"

    # 4. Plan update
    mock_plan = {
        "objective": "Verify Example Domain functionality",
        "strategy": "Automated smoke tests",
        "test_cases": [
            {
                "id": "TC-001",
                "title": "Verify Homepage Loads",
                "description": "Ensure 200 OK",
                "priority": "critical",
                "category": "smoke",
                "preconditions": [],
                "expected_result": "Page loaded",
                "steps": [
                    {"step_number": 1, "action": "navigate", "target": target_url, "expected_result": "Loaded"}
                ]
            }
        ]
    }
    run_manager.update_test_plan(run_id, mock_plan)
    run = run_manager.get_run(run_id)
    assert len(run["test_plan"]["test_cases"]) == 1
    assert run["stats"]["total"] == 1

    # 5. Case progress
    mock_res = {
        "test_case_id": "TC-001",
        "status": "passed",
        "actual_result": "Successfully navigated to homepage",
        "evidence": [{"type": "screenshot", "location": "/evidence/screenshot_TC-001.png"}]
    }
    run_manager.update_case_progress(run_id, "TC-001", "passed", mock_res, 1, 1)
    run = run_manager.get_run(run_id)
    assert len(run["test_results"]) == 1
    assert run["stats"]["passed"] == 1
    assert run["stats"]["pass_rate"] == 100.0

    # 6. Complete
    summary_md = "# Executive Summary\nAll tests passed."
    run_manager.complete_run(run_id, summary_md)
    run = run_manager.get_run(run_id)
    assert run["status"] == "completed"
    assert run["progress_percent"] == 100
    assert run["final_summary"] == summary_md


def test_summarizer_deterministic_report():
    test_plan = TestPlan(
        objective="Verify Store Portal",
        strategy="Smoke & Functional",
        test_cases=[
            TestCase(
                id="TC-001",
                title="Verify Storefront",
                description="Check storefront",
                priority="high",
                category="smoke",
                expected_result="Loaded",
                steps=[TestStep(step_number=1, action="navigate", target="https://store.example.com")]
            )
        ]
    )
    results = [
        TestResult(
            test_case_id="TC-001",
            status=TestCaseStatus.PASSED,
            actual_result="Storefront rendered 12 products successfully."
        )
    ]

    report = summarizer_agent.generate_summary(
        run_id="run_sum_001",
        target_url="https://store.example.com",
        test_plan=test_plan,
        results=results
    )

    assert "TC-001" in report
    assert "Storefront rendered 12 products successfully." in report
    assert "Pass Rate" in report or "100.0%" in report
