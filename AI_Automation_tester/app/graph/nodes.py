"""
LangGraph Nodes
===============
This module defines the processing nodes for our LangGraph state machine.

HOW LANGGRAPH NODES WORK:
Each node is a Python function that:
1. Receives the current state (a TestRunState TypedDict).
2. Performs a specific operation (e.g. validates input, calls an agent, runs a service).
3. Returns a dictionary containing updates to the state.

LangGraph automatically merges these updates back into the central state.

OPTIONAL DB PERSISTENCE:
All database operations are wrapped in try/except blocks. If the database is not 
configured (or offline), the workflow continues running in-memory without crashing.
"""

from typing import Any                                  # For flexible dictionary indexing
from datetime import datetime                           # Timestamps
from langgraph.types import interrupt                   # LangGraph native HITL pause

from app.graph.state import TestRunState                 # Schema representing central state
from app.guardrails.input import validate_target_url, InputGuardrailError  # Guardrails
from app.mcp.manager import mcp_manager                 # MCP Session manager
from app.agents.discovery import create_discovery_agent  # Discovery agent factory
from app.services.discovery_extractor import DiscoveryExtractor  # Extract elements
from app.rag.retriever import rag_retriever             # RAG retriever
from app.agents.planner import planner_agent            # Planner agent
from app.agents.test_writer import test_writer_agent    # Test writer agent
from app.services.test_runner import TestRunner         # Execution loop
from app.agents.summarizer import summarizer_agent      # Summary reporter
from app.services.reports import reports_service        # Report generator
from app.database.connection import SessionLocal        # SQLAlchemy sessions
from app.database.repositories.test_runs import TestRunRepository  # DB repo


from app.services.run_manager import run_manager         # Live state & event manager


def validate_target_node(state: TestRunState) -> dict:
    """
    Validates the target URL. If invalid, logs error and marks run as failed.
    """
    run_id = state.get("run_id", "")
    url = state.get("target_url")
    print(f"[Node: validate_target] Checking URL: {url}")
    run_manager.update_stage(run_id, "discovering", "Validating Target URL", 10)

    try:
        validated_url = validate_target_url(url)
        run_manager.add_log(run_id, f"Target URL verified: {validated_url}", level="success", stage="Validation")
        return {
            "target_url": validated_url,
            "status": "discovering",
            "errors": state.get("errors", [])
        }
    except InputGuardrailError as e:
        print(f"[Node: validate_target] Blocked by Guardrails: {str(e)}")
        error_info = {"component": "input_guardrail", "message": str(e), "recoverable": False}
        run_manager.fail_run(run_id, str(e))
        return {
            "status": "failed",
            "errors": state.get("errors", []) + [error_info]
        }


async def discovery_node(state: TestRunState) -> dict:
    """
    Runs the discovery agent in a browser session to map out interactive elements.
    """
    run_id = state.get("run_id", "")
    url = state.get("target_url")
    print(f"[Node: discovery] Navigating browser and discovering elements for: {url}")
    run_manager.update_stage(run_id, "discovering", "Discovering Page Elements & DOM", 25)
    run_manager.add_log(run_id, f"Launching Playwright Chromium browser to inspect {url}", level="info", stage="Discovery")

    async with mcp_manager.browser_session() as tools:
        browser_evidence = ""
        try:
            agent = create_discovery_agent(tools)
            agent_result = await agent.ainvoke({
                "messages": [
                    {
                        "role": "user",
                        "content": f"Discover the website {url}. Navigate to {url} and inspect the page title, links, and forms.",
                    }
                ]
            })
            browser_evidence = "\n".join(
                str(m.content) for m in agent_result.get("messages", []) if m.content
            )
        except Exception as e:
            print(f"[Discovery Warning] Agent invoke failed: {e}. Running direct browser DOM extraction fallback.")
            run_manager.add_log(run_id, f"Navigating directly to {url} via browser tools...", level="info", stage="Discovery")

            nav_tool = next((t for t in tools if any(k in getattr(t, "name", "").lower() for k in ("navigate", "open", "goto"))), None)
            eval_tool = next((t for t in tools if any(k in getattr(t, "name", "").lower() for k in ("eval", "snapshot", "html"))), None)

            if nav_tool:
                try:
                    await nav_tool.ainvoke({"url": url})
                except Exception:
                    try:
                        await nav_tool.ainvoke({"target": url})
                    except Exception as n_err:
                        print(f"[Discovery Tool Warning] Nav error: {n_err}")

            if eval_tool:
                try:
                    js_script = """
                    (() => {
                        const links = Array.from(document.querySelectorAll('a[href]'))
                            .slice(0, 30)
                            .map(a => ({ href: a.href, text: a.innerText.trim() }))
                            .filter(a => a.text && a.href.startsWith('http'));
                        const buttons = Array.from(document.querySelectorAll('button, input[type=button], input[type=submit]'))
                            .slice(0, 20)
                            .map(b => ({ text: b.innerText.trim() || b.value || 'button', selector: b.id ? '#' + b.id : (b.className ? '.' + b.className.split(' ')[0] : 'button') }));
                        const inputs = Array.from(document.querySelectorAll('input:not([type=hidden]), textarea, select'))
                            .slice(0, 15)
                            .map(i => ({ name: i.name || i.id || 'input', type: i.type || 'text', selector: i.id ? '#' + i.id : (i.name ? 'input[name=' + i.name + ']' : 'input') }));
                        return JSON.stringify({
                            url: window.location.href,
                            title: document.title || 'Target Website',
                            links: links,
                            buttons: buttons,
                            inputs: inputs,
                            forms: Array.from(document.querySelectorAll('form')).slice(0, 5).map(f => ({ action: f.action }))
                        });
                    })()
                    """
                    dom_json = await eval_tool.ainvoke({"expression": js_script})
                    browser_evidence = str(dom_json)
                except Exception as eval_err:
                    print(f"[Discovery Tool Warning] DOM eval error: {eval_err}")
                    browser_evidence = f"Page URL: {url}\nTitle: {url}"

        extractor = DiscoveryExtractor()
        discovery_result = extractor.extract(browser_evidence)
        website_map = discovery_result.website
        if not website_map.url:
            website_map.url = url

        run_manager.update_website_map(run_id, website_map)

        try:
            with SessionLocal() as db:
                repo = TestRunRepository(db)
                repo.update_website_map(run_id, website_map.model_dump())
        except Exception as db_err:
            print(f"[Warning] Database update skipped in discovery: {str(db_err)}")

        return {
            "website_map": website_map,
            "status": "planning"
        }


def planning_node(state: TestRunState) -> dict:
    """
    Generates a high-level test strategy and cases using Planner LLM and RAG.
    """
    run_id = state.get("run_id", "")
    website_map = state.get("website_map")
    title = getattr(website_map, "title", "") or "Target Site"
    print(f"[Node: planning] Generating test objective and case list for: {title}")
    run_manager.update_stage(run_id, "planning", "Designing QA Test Architecture & Strategy", 45)
    run_manager.add_log(run_id, "Analyzing discovered site map and consulting historical test patterns...", level="info", stage="Planning")

    # Query RAG database for similar site architectures
    description = getattr(website_map, "description", "") or title
    historical_plans = rag_retriever.retrieve_similar_test_plans(description)

    # Generate plan
    plan = planner_agent.generate_plan(website_map, historical_plans)
    run_manager.update_test_plan(run_id, plan)

    return {
        "test_plan": plan,
        "status": "test_generation"
    }


def test_generation_node(state: TestRunState) -> dict:
    """
    Instructs the Test Writer to map specific target selectors and input values to steps.
    """
    run_id = state.get("run_id", "")
    website_map = state.get("website_map")
    draft_plan = state.get("test_plan")
    print(f"[Node: test_generation] Generating selectors and inputs for test cases...")
    run_manager.update_stage(run_id, "test_generation", "Synthesizing Executable Steps & Selectors", 65)
    run_manager.add_log(run_id, "Mapping DOM selectors, interaction targets, and verification assertions...", level="info", stage="Check Writing")

    # Refine the draft plan with detailed steps
    refined_plan = test_writer_agent.refine_steps(website_map, draft_plan)
    run_manager.update_test_plan(run_id, refined_plan)

    # Save to database (optional)
    try:
        with SessionLocal() as db:
            repo = TestRunRepository(db)
            repo.update_test_plan(run_id, refined_plan.model_dump())
    except Exception as db_err:
        print(f"[Warning] Database update skipped in test generation: {str(db_err)}")

    return {
        "test_plan": refined_plan,
        "status": "human_review"
    }


def human_review_node(state: TestRunState) -> dict:
    """
    Triggers an interrupt to wait for human review before execution (HITL).
    """
    run_id = state.get("run_id", "")
    print(f"[Node: human_review] Pausing graph for human check...")
    run_manager.update_stage(run_id, "human_review", "Human Review Required - Awaiting Approval", 75)
    run_manager.add_log(run_id, "Test Plan generated. Pausing pipeline for human sign-off before browser execution.", level="warning", stage="Review")
    
    review_prompt = "Please review the generated test plan and approve it to proceed."
    response = interrupt(review_prompt)
    print(f"[Node: human_review] Received response: {response}")
    run_manager.add_log(run_id, f"Human review decision received: {response}", level="info", stage="Review")

    return {
        "status": "executing"
    }


async def execution_node(state: TestRunState) -> dict:
    """
    Executes the generated test steps sequentially in a live browser session.
    """
    test_plan = state.get("test_plan")
    run_id = state.get("run_id", "")
    cases_cnt = len(test_plan.test_cases) if test_plan else 0
    print(f"[Node: execution] Launching execution loop for {cases_cnt} cases...")
    run_manager.update_stage(run_id, "executing", f"Executing Test Suite ({cases_cnt} cases)", 78)
    run_manager.add_log(run_id, f"Starting live Playwright test runner for {cases_cnt} test cases...", level="info", stage="Execution")

    healing_attempts = []

    def progress_callback(case_id, status, result, current_idx, total_cases):
        run_manager.update_case_progress(run_id, case_id, status, result, current_idx, total_cases)

    # Run browser execution session
    async with mcp_manager.browser_session() as tools:
        runner = TestRunner(tools, state["website_map"], progress_callback=progress_callback)
        results = await runner.run_plan(test_plan, run_id, healing_attempts)

    # Save individual case results to DB (optional)
    try:
        with SessionLocal() as db:
            repo = TestRunRepository(db)
            for res in results:
                repo.save_test_case_result(
                    run_id=run_id,
                    test_case_id=res.test_case_id,
                    status=res.status.value,
                    actual_result=res.actual_result,
                    failure_data=res.failure.model_dump() if res.failure else None
                )
    except Exception as db_err:
        print(f"[Warning] Database results logging skipped: {str(db_err)}")

    return {
        "test_results": results,
        "healing_attempts": healing_attempts,
        "status": "summary"
    }


def failure_analysis_node(state: TestRunState) -> dict:
    """
    Placeholder matching StateGraph node registry (analysis is run inline in TestRunner).
    """
    return {"status": state.get("status", "analyzing_failure")}


def self_healing_node(state: TestRunState) -> dict:
    """
    Placeholder matching StateGraph node registry (healing is run inline in TestRunner).
    """
    return {"status": state.get("status", "healing")}


def summary_node(state: TestRunState) -> dict:
    """
    Generates summary report and compiles JSON/HTML reports to files.
    """
    run_id = state.get("run_id", "")
    target_url = state.get("target_url", "")
    test_plan = state.get("test_plan")
    results = state.get("test_results", [])
    healing_attempts = state.get("healing_attempts", [])

    print(f"[Node: summary] Compilation started. Writing reports...")
    run_manager.update_stage(run_id, "summary", "Compiling Executive Summary & HTML Dashboard", 95)
    run_manager.add_log(run_id, "Generating Executive QA Report and static HTML test dashboard...", level="info", stage="Summary")

    # Write Markdown summary
    summary_markdown = summarizer_agent.generate_summary(
        run_id, target_url, test_plan, results, healing_attempts
    )

    # Write JSON and HTML dashboards
    reports_service.generate_json_report(run_id, target_url, test_plan, results)
    reports_service.generate_html_report(run_id, target_url, test_plan, results)

    # Complete run in run manager
    run_manager.complete_run(run_id, summary_markdown, healing_attempts)

    # Update database summary (optional)
    try:
        with SessionLocal() as db:
            repo = TestRunRepository(db)
            repo.update_summary(run_id, summary_markdown)
    except Exception as db_err:
        print(f"[Warning] Database final summary update skipped: {str(db_err)}")

    return {
        "final_summary": summary_markdown,
        "status": "completed"
    }