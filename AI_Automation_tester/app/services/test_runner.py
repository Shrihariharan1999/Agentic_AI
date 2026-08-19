"""
Test Runner Service
===================
Coordinates the sequential execution of test cases, failure analysis, and self-healing retries.

WHY DO WE NEED A TEST RUNNER SERVICE?
Running tests is more than just executing tools: we need to run tests in order, capture
evidence, analyze failures immediately, try to self-heal selectors when possible, 
and persist results to the database.

The TestRunner wraps the entire execution lifecycle for a test suite.

HOW IT FITS IN THE PIPELINE:
  Refined TestPlan -> [Test Runner Service] -> Runs each test case ->
  If Fails -> FailureAnalyzer -> SelfHealing -> Retries -> TestResults list
"""

import asyncio                                          # For async control flows
from app.config.settings import settings                 # Settings
from app.schemas.test_case import TestCase, TestPlan     # Schemas
from app.schemas.test_result import TestResult, TestCaseStatus  # Result schemas
from app.schemas.enums import FailureType               # Failure type enum
from app.agents.executor import ExecutorAgent            # Executor Agent
from app.agents.failure_analyzer import failure_analyzer_agent  # Failure analyzer singleton
from app.agents.self_healing import self_healing_agent  # Self healing agent singleton
from app.services.evidence import evidence_collector    # Evidence collector
from app.rag.retriever import rag_retriever             # Retrieval for self-healing context
from app.schemas.website import WebsiteMap              # Schema representing site elements
from app.schemas.workflow import HealingAttempt         # Workflow healing schemas


class TestRunner:
    """
    Orchestrates the lifecycle of test case execution, diagnostics, and recovery.
    """

    def __init__(self, tools: list, website_map: WebsiteMap, progress_callback=None):
        """
        Initializes the runner with browser tools and the site map.

        Args:
            tools: Active MCP browser tools.
            website_map: The discovered WebsiteMap.
            progress_callback: Optional callable(case_id, status, result, current_index, total_count)
        """
        self.tools = tools
        self.website_map = website_map
        self.executor = ExecutorAgent(tools)
        self.progress_callback = progress_callback

    async def run_test_case(
        self,
        test_case: TestCase,
        run_id: str,
        healing_attempts_log: list[HealingAttempt]
    ) -> TestResult:
        """
        Runs a single test case with built-in retry and self-healing capabilities.

        Args:
            test_case: The TestCase to run.
            run_id: The active test run ID.
            healing_attempts_log: A shared list where healing attempts are recorded.

        Returns:
            The final TestResult.
        """
        attempts = 0
        max_healing = settings.max_healing_attempts
        current_case = test_case.model_copy(deep=True)

        while True:
            print(f"[TestRunner] Executing test case {current_case.id} (Attempt {attempts + 1})...")
            
            # Execute the case using browser tools
            result = await self.executor.execute(current_case)

            # Capture a screenshot as evidence at the end of the run
            screenshot_evidence = await evidence_collector.capture_screenshot(
                self.tools, current_case.id, step_number=len(current_case.steps)
            )
            if screenshot_evidence:
                result.evidence.append(screenshot_evidence)

            # If the test passed, return the result immediately
            if result.status == TestCaseStatus.PASSED:
                print(f"[TestRunner] Test case {current_case.id} PASSED.")
                return result

            # If the test failed, run Failure Analysis
            print(f"[TestRunner] Test case {current_case.id} failed. Analyzing failure...")
            failure_details = failure_analyzer_agent.analyze_failure(current_case, result)
            result.failure = failure_details

            # Check if self-healing is possible
            if (
                failure_details.failure_type == FailureType.TEST
                and failure_details.recoverable
                and attempts < max_healing
            ):
                attempts += 1
                print(f"[TestRunner] Self-healing triggered (Healing Attempt {attempts}/{max_healing})...")

                past_healing = str(rag_retriever.retrieve_healing_history(failure_details.message))

                try:
                    failed_step_number = len(current_case.steps)
                    for step in current_case.steps:
                        if step.target and step.target in failure_details.message:
                            failed_step_number = step.step_number
                            break

                    healed_suggestion = self_healing_agent.heal_step(
                        test_case=current_case,
                        failed_step_number=failed_step_number,
                        error_message=failure_details.message,
                        website_map=self.website_map,
                        past_healing_examples=past_healing
                    )

                    for step in current_case.steps:
                        if step.step_number == healed_suggestion.step_number:
                            print(
                                f"[TestRunner] Healing step {step.step_number}: "
                                f"Replacing '{step.target}' with '{healed_suggestion.healed_target}'"
                            )
                            step.target = healed_suggestion.healed_target
                            break

                    healing_attempts_log.append(
                        HealingAttempt(
                            attempt_number=len(healing_attempts_log) + 1,
                            reason=failure_details.message,
                            action=f"Changed Step {healed_suggestion.step_number} selector to '{healed_suggestion.healed_target}'",
                            successful=True
                        )
                    )
                    continue

                except Exception as ex:
                    print(f"[TestRunner] Self-healing failed to apply correction: {str(ex)}")
                    healing_attempts_log.append(
                        HealingAttempt(
                            attempt_number=len(healing_attempts_log) + 1,
                            reason=failure_details.message,
                            action=f"Self healing attempt failed: {str(ex)}",
                            successful=False
                        )
                    )

            # If not recoverable or out of retries, return the failed result
            print(f"[TestRunner] Test case {current_case.id} permanently concluded with status: {result.status.value.upper()}")
            return result

    async def run_plan(
        self,
        test_plan: TestPlan,
        run_id: str,
        healing_attempts_log: list[HealingAttempt]
    ) -> list[TestResult]:
        """
        Runs all test cases defined in the test plan sequentially.

        Args:
            test_plan: The TestPlan containing the list of TestCases.
            run_id: The UUID of the current run.
            healing_attempts_log: List to record healing attempts.

        Returns:
            A list of TestResults.
        """
        results = []
        total_cases = len(test_plan.test_cases)
        for idx, case in enumerate(test_plan.test_cases, start=1):
            if self.progress_callback:
                try:
                    self.progress_callback(case.id, "running", None, idx, total_cases)
                except Exception as cb_err:
                    print(f"[TestRunner Warning] Progress callback error: {cb_err}")

            result = await self.run_test_case(case, run_id, healing_attempts_log)
            results.append(result)

            if self.progress_callback:
                try:
                    self.progress_callback(case.id, result.status.value, result, idx, total_cases)
                except Exception as cb_err:
                    print(f"[TestRunner Warning] Progress callback error: {cb_err}")

        return results
