"""
Summarizer Agent
================
The Summarizer Agent generates the final Markdown report of the test run.

WHY DO WE NEED A SUMMARIZER AGENT?
After executing 10-20 tests (some passing, some failing, some healed), we need a 
cohesive, readable executive summary. The Summarizer Agent:
1. Gathers all test case run statuses and details.
2. Groups results by outcome (Passed, Failed, Blocked).
3. Documents any self-healing attempts and details why they succeeded or failed.
4. Formats everything into a beautiful Markdown report with tables and diagnostics.

HOW IT FITS IN THE PIPELINE:
  TestPlan + TestResults + HealingHistory -> [Summarizer Agent] -> final_summary (Markdown)
"""

from langchain_core.prompts import ChatPromptTemplate  # Prompt templates
from app.models.factory import model_factory            # Our model factory
from app.schemas.test_case import TestPlan              # TestPlan schema
from app.schemas.test_result import TestResult          # TestResult schema
from app.schemas.workflow import HealingAttempt         # HealingAttempt schema


SUMMARIZER_SYSTEM_PROMPT = """
You are the Principal QA Lead & Executive Release Summarizer of an autonomous web testing system.

Your job is to generate a comprehensive, executive-ready Test Run Summary in clean, standard Markdown.

Structure the Markdown report as follows:
# 🧪 Executive QA Test Execution Report

## 📊 Overview & Key Metrics
- **Target URL**: `<URL>`
- **Run ID**: `<Run ID>`
- **Total Test Cases**: `<Count>`
- **Passed**: `<Count>` | **Failed**: `<Count>` | **Blocked**: `<Count>`
- **Overall Pass Rate**: `<Percentage>%`

## 📋 Test Execution Breakdown
Create a Markdown table with columns:
| Test ID | Title | Status | Duration / Detail | Outcome & Evidence |

## 🔍 Failure Diagnostics & Root Causes (if any failed/blocked)
For any failed or blocked test case, explain:
- **Failure Classification**: (Application Bug, Selector Issue, Environment, Timeout)
- **Root Cause**: Specific error explanation
- **Observed Behavior**: What actually happened during execution

## 🩹 Self-Healing Audit Trail
Document any automated self-healing attempts, modified locators, and whether recovery succeeded.

## 💡 Recommendations for Engineering
Provide 2-3 actionable next steps for the engineering or QA team based on these findings.

Ensure formatting is crisp, professional, and visually clear.
"""


class SummarizerAgent:
    """
    Consolidates run data and writes a detailed Markdown test execution report.
    """

    def __init__(self):
        # Retrieve the LLM configured for summarizing
        self.model = model_factory.get("summary")

    def generate_summary(
        self,
        run_id: str,
        target_url: str,
        test_plan: TestPlan,
        results: list[TestResult],
        healing_attempts: list[HealingAttempt] = None
    ) -> str:
        """
        Creates the Markdown test report.

        Args:
            run_id: The UUID of the test run.
            target_url: The URL tested.
            test_plan: The generated test plan.
            results: List of execution results for the test cases.
            healing_attempts: List of self-healing actions attempted.

        Returns:
            A clean Markdown string.
        """
        healing_attempts = healing_attempts or []
        total = len(test_plan.test_cases)
        passed = sum(1 for r in results if r.status.value == "passed")
        failed = sum(1 for r in results if r.status.value == "failed")
        blocked = sum(1 for r in results if r.status.value == "blocked")
        pass_rate = (passed / total * 100) if total > 0 else 0.0

        # Prepare test results text for prompt input
        results_text = ""
        for res in results:
            tc = next((t for t in test_plan.test_cases if t.id == res.test_case_id), None)
            title = tc.title if tc else "Unknown Test"
            
            results_text += (
                f"- Case ID: {res.test_case_id}\n"
                f"  Title: {title}\n"
                f"  Status: {res.status.value.upper()}\n"
                f"  Actual Result: {res.actual_result}\n"
            )
            if res.failure:
                results_text += (
                    f"  Failure Type: {res.failure.failure_type.value}\n"
                    f"  Failure Message: {res.failure.message}\n"
                    f"  Root Cause: {res.failure.root_cause}\n"
                )
            results_text += "\n"

        # Prepare healing attempts text for prompt input
        healing_text = ""
        for heal in healing_attempts:
            healing_text += (
                f"- Attempt {heal.attempt_number}: Reason: {heal.reason}\n"
                f"  Action taken: {heal.action}\n"
                f"  Successful: {heal.successful}\n\n"
            )

        prompt = ChatPromptTemplate.from_messages([
            ("system", SUMMARIZER_SYSTEM_PROMPT),
            ("user", """
Run ID: {run_id}
Target URL: {target_url}

Total Test Cases: {test_count}
Passed: {passed_count} | Failed: {failed_count} | Blocked: {blocked_count}
Pass Rate: {pass_rate:.1f}%

Test Execution Results:
{results_text}

Self-Healing Attempts:
{healing_text}

Please generate the comprehensive Markdown report.
""")
        ])

        formatted_prompt = prompt.format_messages(
            run_id=run_id,
            target_url=target_url,
            test_count=total,
            passed_count=passed,
            failed_count=failed,
            blocked_count=blocked,
            pass_rate=pass_rate,
            results_text=results_text,
            healing_text=healing_text if healing_text else "No self-healing attempts were made."
        )

        try:
            response = self.model.invoke(formatted_prompt)
            if response and response.content:
                return response.content
        except Exception as e:
            print(f"[SummarizerAgent Warning] LLM summary generation failed: {e}. Building deterministic summary.")

        # Fallback deterministic markdown generator
        table_rows = []
        for tc in test_plan.test_cases:
            res = next((r for r in results if r.test_case_id == tc.id), None)
            st = res.status.value.upper() if res else "PENDING"
            act = res.actual_result if res else "Not executed"
            table_rows.append(f"| `{tc.id}` | **{tc.title}** | `{st}` | {act} |")

        table_md = "\n".join(table_rows)

        heal_md = "\n".join([
            f"- **Attempt #{h.attempt_number}**: {h.action} (Status: {'✅ Healed' if h.successful else '❌ Failed'})"
            for h in healing_attempts
        ]) if healing_attempts else "_No self-healing attempts were required for this run._"

        return f"""# 🧪 Executive QA Test Execution Report

## 📊 Overview & Key Metrics
- **Target URL**: [{target_url}]({target_url})
- **Run ID**: `{run_id}`
- **Total Test Cases**: **{total}**
- **Passed**: `{passed}` | **Failed**: `{failed}` | **Blocked**: `{blocked}`
- **Overall Pass Rate**: **{pass_rate:.1f}%**

## 📋 Test Execution Breakdown
| Test ID | Title | Status | Outcome & Findings |
| :--- | :--- | :--- | :--- |
{table_md}

## 🩹 Self-Healing Audit Trail
{heal_md}

## 💡 Recommendations for Engineering
- Review any failed or blocked test steps and verify DOM selector stability.
- Ensure authentication gates and responsive layout breakpoints match the expected test plan assertions.
"""


# Singleton instance
summarizer_agent = SummarizerAgent()
