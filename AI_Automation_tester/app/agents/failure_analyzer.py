"""
Failure Analyzer Agent
======================
The Failure Analyzer Agent diagnoses test failures to understand their root cause.

WHY DO WE NEED A FAILURE ANALYZER AGENT?
When a browser test fails, a simple "test failed" message doesn't help developers 
much. We need to distinguish between:
  1. Application Bugs (e.g. 500 error page, broken signup button).
  2. Test Script Flakes (e.g. wrong CSS selector, timing issue).
  3. Environment issues (e.g. site is offline, database down).

The Failure Analyzer reads the test case steps, the actual execution logs, and classifies 
the failure type, giving developers high-confidence diagnostics and deciding if self-healing
should be attempted.

HOW IT FITS IN THE PIPELINE:
  Failed TestResult -> [Failure Analyzer Agent] -> TestFailure (with FailureType & root cause)
"""

from langchain_core.prompts import ChatPromptTemplate  # Prompt templates
from app.models.factory import model_factory            # Our model factory
from app.schemas.test_case import TestCase              # Schema for test cases
from app.schemas.test_result import TestFailure, TestResult  # Schemas for failure results


FAILURE_ANALYZER_SYSTEM_PROMPT = """
You are the Failure Analyzer Agent of an autonomous web testing system.

Your job is to analyze the failure of a test case and produce a structured diagnosis.

Choose the most appropriate FailureType:
- 'application': The website has an actual bug (e.g. form submission failed, error page shown).
- 'test': The test case itself is incorrect or using outdated selectors.
- 'environment': Network timeouts, server offline, database connection errors.
- 'browser': Playwright/Browser crashed or failed to render.
- 'mcp': MCP server communication issues.
- 'unknown': If root cause cannot be clearly determined.

Suggest if the error is `recoverable` (e.g. can we try a different selector or retry after a wait?).
"""


class FailureAnalyzerAgent:
    """
    Diagnoses failures from test case runs using structured LLM analysis.
    """

    def __init__(self):
        # Retrieve the LLM configured for failure analysis
        self.model = model_factory.get("failure_analyzer")

    def analyze_failure(self, test_case: TestCase, test_result: TestResult) -> TestFailure:
        """
        Analyzes why the test case failed and determines the root cause.

        Args:
            test_case: The test case definition containing the steps and expected result.
            test_result: The result containing the logs and actual outcome.

        Returns:
            A TestFailure Pydantic object detailing type, message, root cause, and recoverability.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", FAILURE_ANALYZER_SYSTEM_PROMPT),
            ("user", """
Test Case Title: {title}
Expected Outcome: {expected_result}

Steps:
{steps_text}

Execution Actual Result:
{actual_result}

Please analyze this failure and output the structured failure details.
""")
        ])

        # Format steps for the LLM prompt
        steps_text = "\n".join(
            f"Step {step.step_number}: {step.action} on '{step.target}'"
            for step in test_case.steps
        )

        formatted_prompt = prompt.format_messages(
            title=test_case.title,
            expected_result=test_case.expected_result,
            steps_text=steps_text,
            actual_result=test_result.actual_result
        )

        # Bind structured output to the model for TestFailure
        structured_llm = self.model.with_structured_output(TestFailure)

        # Invoke the LLM to get structured diagnostics
        failure_details = structured_llm.invoke(formatted_prompt)

        return failure_details


# Singleton instance
failure_analyzer_agent = FailureAnalyzerAgent()
