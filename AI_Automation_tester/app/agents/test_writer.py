"""
Test Writer Agent
=================
The Test Writer Agent refines high-level test cases into concrete execution steps.

WHY DO WE NEED A TEST WRITER AGENT?
The Planner creates the strategy and list of test cases, but doesn't map exact HTML selectors 
or inputs to each step. The Test Writer bridges the gap:
1. It looks at the website map (available inputs, button text, selectors).
2. It takes each test case from the planner.
3. It generates the specific, sequence-by-sequence `TestStep` actions (e.g. click, input, wait).
4. It sets the exact target selectors and mock values needed for automation tools to execute.

HOW IT FITS IN THE PIPELINE:
  TestPlan (stubs) + WebsiteMap -> [Test Writer Agent] -> Refined TestPlan (executable steps)
"""

from langchain_core.prompts import ChatPromptTemplate  # For LLM prompt templates
from app.models.factory import model_factory            # Our model factory
from app.schemas.test_case import TestPlan              # Pydantic schema for test plan output
from app.schemas.website import WebsiteMap              # Schema representing the discovered site


TEST_WRITER_SYSTEM_PROMPT = """
You are the Test Writer Agent of an autonomous web testing system.

Your job is to take a draft Test Plan and the Website Map and refine the test cases. 
Specifically, you must populate the `steps` list for each TestCase in the Test Plan.

Each step in a TestCase must contain:
1. `step_number`: Sequential integer starting from 1.
2. `action`: The exact action type. Choose from: 'navigate', 'click', 'type', 'select', 'verify_text', 'verify_element', 'wait'.
3. `target`: The element selector or description to interact with (e.g. "input[name='username']", "#login-btn", "text=Submit"). Use selectors found in the Website Map.
4. `value`: The value to input if the action is 'type' or 'select' (e.g. "testuser", "securepass123").
5. `expected_result`: What should happen after this step completes.

Ensure the steps are logical, executable, and target actual elements present in the Website Map.
Maintain the exact IDs, Titles, and Objectives of the test cases from the input Test Plan.
"""


class TestWriterAgent:
    """
    Translates high-level test descriptions into specific step-by-step browser interactions.
    """

    def __init__(self):
        # Retrieve the configured LLM for test writing
        self.model = model_factory.get("test_writer")

    def refine_steps(self, website_map: WebsiteMap, draft_plan: TestPlan) -> TestPlan:
        """
        Refines each test case in the draft test plan by adding exact target selectors and values.

        Args:
            website_map: Discovered elements and structure of the website under test.
            draft_plan: The plan containing the high-level objectives and test case list.

        Returns:
            A refined TestPlan Pydantic object containing fully specified test cases with steps.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", TEST_WRITER_SYSTEM_PROMPT),
            ("user", """
Website Map (Available selectors, links, inputs):
{website_map_json}

Draft Test Plan to fill in steps for:
{draft_plan_json}

Please write the detailed, step-by-step selectors and values for all test cases and return the updated Test Plan.
""")
        ])

        formatted_prompt = prompt.format_messages(
            website_map_json=website_map.model_dump_json(indent=2),
            draft_plan_json=draft_plan.model_dump_json(indent=2)
        )

        try:
            structured_llm = self.model.with_structured_output(TestPlan)
            refined_plan = structured_llm.invoke(formatted_prompt)
            if refined_plan and hasattr(refined_plan, "test_cases") and len(refined_plan.test_cases) > 0:
                # Validate that each test case has steps
                for tc in refined_plan.test_cases:
                    if not tc.steps:
                        from app.schemas.test_case import TestStep
                        tc.steps = [
                            TestStep(step_number=1, action="navigate", target=website_map.url, expected_result="Page loads"),
                            TestStep(step_number=2, action="verify_element", target="body", expected_result="Page is ready")
                        ]
                return refined_plan
        except Exception as e:
            print(f"[TestWriterAgent Warning] Structured refinement failed: {e}. Preserving draft plan with fallback steps.")

        # If LLM refinement fails, ensure every case in draft_plan has at least default steps
        from app.schemas.test_case import TestStep
        for tc in draft_plan.test_cases:
            if not tc.steps:
                tc.steps = [
                    TestStep(step_number=1, action="navigate", target=website_map.url, expected_result=f"Navigate to {website_map.url}"),
                    TestStep(step_number=2, action="verify_element", target="body", expected_result="Page content visible")
                ]

        return draft_plan


# Singleton instance
test_writer_agent = TestWriterAgent()
