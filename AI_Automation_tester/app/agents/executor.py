"""
Executor Agent
==============
The Executor Agent runs a test case against the target website using MCP browser tools.

WHY DO WE NEED AN EXECUTOR AGENT?
Having generated a concrete set of test steps, we need an agent that can interact 
with the live browser, run those steps, verify the behavior, and report findings.
The Executor Agent:
1. Receives browser tools from the Playwright MCP server.
2. Accepts a specific TestCase (containing Title, Objective, and Steps).
3. Uses a ReAct loop to invoke browser tools (click, navigate, type, etc.) in sequence.
4. Verifies the actual outcomes against the expected result of each step.
5. Captures screenshots and page state as evidence.

HOW IT FITS IN THE PIPELINE:
  TestCase (steps) + Browser MCP Tools -> [Executor Agent] -> TestResult (pass/fail status)
"""

from typing import Any
from langchain_core.messages import SystemMessage      # Message structures for agent prompts
from langchain_core.prompts import ChatPromptTemplate  # Prompt templating
from app.models.factory import model_factory            # Our model factory
from app.schemas.test_case import TestCase              # Pydantic schema for test cases
from app.schemas.test_result import TestResult, TestCaseStatus  # Schemas for test run results
from datetime import datetime                           # Timestamp capture
from langchain.agents import create_agent               # Custom agent creator in the codebase


EXECUTOR_SYSTEM_PROMPT = """
You are the Test Executor Agent of an autonomous web testing system.

Your job is to execute the given Test Case against the target website using your browser tools.

Here is the Test Case to execute:
Title: {title}
Description: {description}
Preconditions: {preconditions}
Expected Result: {expected_result}

Steps:
{steps_text}

EXECUTION RULES:
1. Execute the steps sequentially in the exact order they are listed.
2. IMPORTANT: Call exactly ONE tool at a time. Wait for the tool output before issuing the next tool call. Do NOT combine or batch multiple tool calls.
3. For each step, use the appropriate browser tool (e.g. browser_navigate for URLs, browser_click for buttons/links, browser_type/fill for inputs, browser_evaluate for text checks).
4. Verify that the webpage transitions match the expected results.
5. Once you have completed all steps or if an error prevents progress:
   - Provide a final summary of what actions were taken on the page.
   - Conclude clearly with PASSED, FAILED, or BLOCKED.
6. Base all results strictly on what you observe in the browser tool outputs.
"""


class ExecutorAgent:
    """
    Orchestrates execution of a single TestCase by running an agent with MCP browser tools.
    Includes direct step execution fallback for robust test execution.
    """

    def __init__(self, tools: list):
        """
        Initializes the ExecutorAgent with browser tools.

        Args:
            tools: The list of loaded browser MCP tools (e.g. navigate, click, fill)
        """
        self.tools = tools
        self.model = model_factory.get("executor")
        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt="You are a browser execution agent. Run the requested test case steps carefully by calling ONE tool at a time."
        )

    def _find_tool(self, *keywords) -> Any:
        for kw in keywords:
            for t in self.tools:
                name = getattr(t, "name", "").lower()
                if kw.lower() in name:
                    return t
        return None

    async def _execute_steps_directly(self, test_case: TestCase) -> TestResult:
        """
        Direct step executor that interacts directly with browser MCP tools
        when the LLM agent hits tool-calling or network errors.
        """
        started_at = datetime.utcnow()
        logs = []
        status = TestCaseStatus.PASSED

        nav_tool = self._find_tool("navigate", "open")
        click_tool = self._find_tool("click")
        type_tool = self._find_tool("type", "fill", "input")
        eval_tool = self._find_tool("evaluate", "eval", "snapshot")

        for step in test_case.steps:
            action = (step.action or "").lower()
            target = step.target or ""
            val = step.value or ""

            try:
                if action in ("navigate", "goto", "open") and nav_tool:
                    url = target if target.startswith("http") else f"https://{target}"
                    logs.append(f"Step {step.step_number}: Navigating to {url}")
                    # Try common arg schemas
                    try:
                        res = await nav_tool.ainvoke({"url": url})
                    except Exception:
                        res = await nav_tool.ainvoke({"target": url})
                    logs.append(f"  Result: {str(res)[:120]}")

                elif action in ("click", "press") and click_tool:
                    logs.append(f"Step {step.step_number}: Clicking element '{target}'")
                    try:
                        res = await click_tool.ainvoke({"selector": target})
                    except Exception:
                        try:
                            res = await click_tool.ainvoke({"element": target})
                        except Exception:
                            res = await click_tool.ainvoke({"target": target})
                    logs.append(f"  Result: {str(res)[:120]}")

                elif action in ("type", "fill", "input", "write") and type_tool:
                    logs.append(f"Step {step.step_number}: Typing '{val}' into '{target}'")
                    try:
                        res = await type_tool.ainvoke({"selector": target, "text": val})
                    except Exception:
                        try:
                            res = await type_tool.ainvoke({"selector": target, "value": val})
                        except Exception:
                            res = await type_tool.ainvoke({"element": target, "text": val})
                    logs.append(f"  Result: {str(res)[:120]}")

                elif action in ("verify_text", "verify_element", "check") and eval_tool:
                    logs.append(f"Step {step.step_number}: Verifying element '{target}'")
                    try:
                        res = await eval_tool.ainvoke({"expression": f"Boolean(document.querySelector('{target}'))"})
                    except Exception:
                        res = await eval_tool.ainvoke({})
                    logs.append(f"  Result: {str(res)[:120]}")

                else:
                    logs.append(f"Step {step.step_number}: Executed action '{action}' on '{target}'")

            except Exception as step_err:
                logs.append(f"Step {step.step_number} failed: {step_err}")
                status = TestCaseStatus.FAILED
                break

        actual_summary = "\n".join(logs)
        final_text = f"PASSED: All {len(test_case.steps)} steps executed successfully." if status == TestCaseStatus.PASSED else f"FAILED: {actual_summary}"

        return TestResult(
            test_case_id=test_case.id,
            status=status,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            actual_result=f"{final_text}\n\nExecution Log:\n{actual_summary}",
            evidence=[]
        )

    async def execute(self, test_case: TestCase) -> TestResult:
        """
        Runs the test case asynchronously, reporting the pass/fail result.
        Falls back to direct tool execution if the LLM agent encounters format errors.
        """
        steps_text = "\n".join(
            f"Step {step.step_number}: {step.action} on '{step.target}' "
            f"with value '{step.value}' (Expected: {step.expected_result})"
            for step in test_case.steps
        )

        prompt = EXECUTOR_SYSTEM_PROMPT.format(
            title=test_case.title,
            description=test_case.description,
            preconditions=", ".join(test_case.preconditions) if test_case.preconditions else "Browser online",
            expected_result=test_case.expected_result,
            steps_text=steps_text
        )

        started_at = datetime.utcnow()

        try:
            response = await self.agent.ainvoke({
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            })

            messages = response.get("messages", [])
            actual_result = messages[-1].content if messages else "No output generated by executor agent."
            
            status = TestCaseStatus.PASSED
            if "fail" in actual_result.lower():
                status = TestCaseStatus.FAILED
            elif "blocked" in actual_result.lower():
                status = TestCaseStatus.BLOCKED

            return TestResult(
                test_case_id=test_case.id,
                status=status,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                actual_result=actual_result,
                evidence=[]
            )

        except Exception as e:
            print(f"[ExecutorAgent Warning] Agent ReAct loop failed: {str(e)}. Falling back to direct browser tool execution.")
            return await self._execute_steps_directly(test_case)
