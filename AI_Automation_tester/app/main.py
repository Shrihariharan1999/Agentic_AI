"""
Application Entry Point
=======================
Bootstraps the AI Automation Tester pipeline, handles execution, database setup,
and CLI terminal human-in-the-loop interactions.

HOW IT WORKS:
1. Configures LangSmith tracing if enabled.
2. Initializes SQL database tables if they do not exist.
3. Compiles the LangGraph workflow.
4. Starts execution with a unique thread ID.
5. If the graph pauses on `human_review` (interrupt):
   - Displays the generated Test Plan to the terminal.
   - Prompts the user in the console to Approve or Reject.
   - Resumes the graph with the user's action value.
6. Prints the final markdown report.
"""

import asyncio                                           # Asynchronous control flows
import sys                                               # Standard system variables
import uuid                                              # Generate unique identifiers
from langgraph.types import Command                     # LangGraph resume/control commands

from app.observability.langsmith import setup_langsmith  # Tracing configuration
from app.database.connection import create_tables       # Database setup
from app.graph.workflow import build_test_workflow      # Workflow compiler


async def main():
    """
    Main driver function for the CLI test execution.
    """
    print("=" * 60)
    print("         LAUNCHING AI WEB AUTOMATION TEST SYSTEM")
    print("=" * 60)

    # 1. Setup LangSmith Tracing
    setup_langsmith()

    # 2. Setup Database Tables
    try:
        print("[System] Checking and initializing database tables...")
        create_tables()
        print("[System] Database initialization complete.")
    except Exception as e:
        print(f"[Warning] Database initialization skipped/failed: {str(e)}")
        print("Workflow will run using local memory fallback.")

    # 3. Compile the Workflow Graph
    workflow = build_test_workflow()

    # Accept the target URL from the command line, or prompt when run interactively.
    target_url = sys.argv[1] if len(sys.argv) > 1 else input("Enter the target URL: ").strip()
    if not target_url:
        print("[System] A target URL is required.")
        return
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # Initial state payload
    initial_state = {
        "run_id": run_id,
        "target_url": target_url,
        "environment": "development",
        "status": "created",
        "errors": [],
        "test_results": [],
        "healing_attempts": []
    }

    # Thread ID is required by the checkpointer (MemorySaver) to save session state
    config = {
        "configurable": {
            "thread_id": f"thread_{uuid.uuid4().hex[:8]}"
        }
    }

    print(f"\n[System] Starting Test Run for target URL: {target_url}")
    print(f"[System] Run ID: {run_id}")
    print("-" * 60)

    # 4. Invoke the workflow asynchronously
    result = await workflow.ainvoke(initial_state, config=config)

    # 5. Check if the graph is currently suspended on a human review checkpoint
    state_snapshot = await workflow.aget_state(config)
    
    # If state_snapshot.next contains node names, it means the graph paused
    # before running those nodes (e.g. paused at human_review_node interrupt)
    if state_snapshot.next and "human_review" in state_snapshot.next:
        print("\n" + "=" * 50)
        print("          HUMAN INTERVENTION REQUIRED")
        print("=" * 50)
        
        # Display the generated plan to the user in the console
        plan = state_snapshot.values.get("test_plan")
        if plan:
            print("\nGenerated Test Objective:")
            print(f"  {plan.objective}")
            print("\nGenerated Test Strategy:")
            print(f"  {plan.strategy}")
            print("\nTest Cases mapped:")
            for tc in plan.test_cases:
                print(f"- [{tc.priority.upper()}] {tc.id}: {tc.title}")
                for step in tc.steps:
                    print(f"   Step {step.step_number}: {step.action} on '{step.target}' (value: '{step.value}')")
        
        # Prompt user for console input
        print("\nWould you like to approve this test plan for execution? (y/n): ", end="")
        sys.stdout.flush() # Ensure print buffer displays before input block
        choice = sys.stdin.readline().strip().lower()

        if choice in ("y", "yes"):
            print("\n[System] Plan Approved. Resuming execution...")
            # Resume graph execution by invoking with a Command containing the resume payload
            result = await workflow.ainvoke(Command(resume="Approved by CLI developer"), config=config)
        else:
            print("\n[System] Plan Rejected. Aborting execution...")
            # Resume graph with a rejection command (will cause execution to skip/abort gracefully)
            await workflow.ainvoke(Command(resume="Rejected by CLI developer"), config=config)
            return

    # 6. Display final execution summary report
    print("\n" + "=" * 60)
    print("               TEST RUN COMPLETE")
    print("=" * 60)
    
    final_summary = result.get("final_summary", "No summary report was generated.")
    print(final_summary)


if __name__ == "__main__":
    asyncio.run(main())