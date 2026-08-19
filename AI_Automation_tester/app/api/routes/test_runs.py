"""
FastAPI Routes for Test Runs
============================
Defines the REST API endpoints to trigger, monitor, and approve test runs.

WHY DO WE NEED API ROUTES?
While running tests via CLI (main.py) is great for development, a production system 
needs to trigger test runs via HTTP (e.g. from CI/CD webhooks or a frontend UI dashboard).

FastAPI routes map HTTP requests to database queries and LangGraph workflows.

BACKGROUND TASKS:
Executing browser tests can take minutes. HTTP requests will timeout if we wait.
Therefore, we start the workflow execution in a FastAPI BackgroundTask so the API 
returns a '202 Accepted' response immediately with the run_id, letting the client 
poll the GET endpoint for status updates.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import AnyHttpUrl, BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.graph.workflow import build_test_workflow
from app.schemas.enums import HumanAction
from app.services.run_manager import run_manager
from langgraph.types import Command


# Create the router instance
router = APIRouter(prefix="/api/test-runs", tags=["Test Runs"])


class TestRunRequest(BaseModel):
    """Request payload for starting a test run."""
    target_url: AnyHttpUrl
    environment: str = "development"


# Cache compiled workflow
workflow = build_test_workflow()


async def run_workflow_async(run_id: str, target_url: str, environment: str):
    """
    Background worker function that invokes the LangGraph pipeline.
    """
    initial_state = {
        "run_id": run_id,
        "target_url": target_url,
        "environment": environment,
        "status": "created",
        "errors": [],
        "test_results": [],
        "healing_attempts": []
    }

    config = {
        "configurable": {
            "thread_id": f"thread_{run_id}"
        }
    }

    try:
        # Stream the graph step updates
        async for _ in workflow.astream(initial_state, config=config, stream_mode="values"):
            pass

        # Check if the graph paused at human_review interrupt
        snapshot = await workflow.aget_state(config)
        if snapshot.next and "human_review" in snapshot.next:
            run_manager.update_stage(run_id, "human_review", "Human Review Required - Awaiting Approval", 75)

    except Exception as e:
        print(f"[API Background Error] Run {run_id} failed: {str(e)}")
        run_manager.fail_run(run_id, str(e))


@router.post("", status_code=202)
async def create_test_run(
    request: TestRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Triggers a new test run session for the target URL.
    """
    target_url = str(request.target_url)
    environment = request.environment
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # Initialize in run manager
    run_data = run_manager.init_run(run_id=run_id, target_url=target_url, environment=environment)

    # Queue the workflow in background worker
    if background_tasks:
        background_tasks.add_task(
            run_workflow_async,
            run_id=run_id,
            target_url=target_url,
            environment=environment
        )

    return {
        "run_id": run_id,
        "status": "created",
        "message": "Test run initiated in the background.",
        "details": run_data
    }


@router.get("")
def list_test_runs(limit: int = 50, db: Session = Depends(get_db)):
    """
    Returns recent test runs.
    """
    return run_manager.list_runs(limit=limit)


@router.get("/{run_id}")
def get_test_run(run_id: str, db: Session = Depends(get_db)):
    """
    Fetches detailed progress, plan, logs, and outcomes of a specific test run.
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found.")
    return run


@router.post("/{run_id}/approve", status_code=200)
async def approve_test_plan(
    run_id: str,
    approved: bool,
    feedback: str = "",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Resumes a paused human-in-the-loop checkpoint.
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found.")

    config = {
        "configurable": {
            "thread_id": f"thread_{run_id}"
        }
    }

    # Ensure the graph is actually paused and awaiting input
    state_snapshot = await workflow.aget_state(config)
    if not state_snapshot.next or "human_review" not in state_snapshot.next:
        raise HTTPException(
            status_code=400,
            detail="This test run is not currently awaiting manual human review."
        )

    action = HumanAction.APPROVE if approved else HumanAction.REJECT
    resume_payload = f"Action: {action.value}. Feedback: {feedback}"

    async def resume_task():
        try:
            if approved:
                run_manager.update_stage(run_id, "executing", "Plan Approved - Launching Execution Loop", 78)
                run_manager.add_log(run_id, f"Plan approved by user. Feedback: {feedback or 'None'}", level="success", stage="Review")
                async for _ in workflow.astream(Command(resume=resume_payload), config=config, stream_mode="values"):
                    pass
            else:
                run_manager.update_stage(run_id, "cancelled", "Plan Rejected by User", 100)
                run_manager.add_log(run_id, f"Plan rejected by user. Feedback: {feedback or 'None'}", level="warning", stage="Review")
                await workflow.ainvoke(Command(resume=resume_payload), config=config)
        except Exception as e:
            print(f"[API Resume Error] Run {run_id} execution failed: {str(e)}")
            run_manager.fail_run(run_id, str(e))

    if background_tasks:
        background_tasks.add_task(resume_task)

    return {
        "run_id": run_id,
        "status": "resuming" if approved else "cancelled",
        "message": f"Resume command sent with action: {action.value}"
    }
