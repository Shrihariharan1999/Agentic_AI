"""
Planner Agent
=============
The Planner Agent analyzes the discovered website map and writes a high-level test plan.

WHY DO WE NEED A PLANNER AGENT?
Directly running browser tests without a plan leads to poor coverage and chaotic
executions. The Planner acts like a human QA lead:
1. It analyzes the elements discovered on the webpage (headers, forms, buttons, links).
2. It reviews similar historical test plans retrieved from RAG.
3. It outlines the test objective, strategy, and lists the test cases to execute
   (including verification steps and priorities).

HOW IT FITS IN THE PIPELINE:
  Discovery Agent (evidence) -> WebsiteMap -> [Planner Agent] -> TestPlan -> Test Writer
"""

from langchain_core.prompts import ChatPromptTemplate  # For templating LLM prompts
from app.models.factory import model_factory            # Our model factory
from app.schemas.test_case import TestPlan              # Pydantic schema for the output test plan
from app.schemas.website import WebsiteMap              # Schema representing the discovered site


PLANNER_SYSTEM_PROMPT = """
You are the Principal QA Lead and Test Architect of an autonomous web testing system.

Your job is to analyze the Website Map of a target website and design a structured, high-coverage Test Plan.
The Test Plan must focus on:
1. Core User Journeys: Map the primary user flow based on discovered navigation, forms, and buttons.
2. Functional & Interactive Verification: Form submission, search/filtering, modal dialogs, and navigation link health.
3. Categorization & Prioritization: 
   - Assign clear IDs (e.g. TC-001, TC-002, TC-003, ...).
   - Set priorities: 'critical' for landing/core flows, 'high' for primary actions/navigation, 'medium'/'low' for edge cases.
   - Categorize cases: 'smoke', 'navigation', 'functional', 'form_validation', or 'ui_responsive'.
4. Specificity: Write clear test case titles, step-by-step objectives, and expected outcomes based on actual discovered DOM elements.

Generate 3 to 8 high-impact, realistic test cases.
Strictly generate the output matching the TestPlan schema.
"""


class PlannerAgent:
    """
    Analyzes the structure of the target website and constructs a structured TestPlan.
    """

    def __init__(self):
        # Retrieve the configured LLM for planning
        self.model = model_factory.get("planner")

    def generate_plan(self, website_map: WebsiteMap, historical_context: str = "") -> TestPlan:
        """
        Generates a TestPlan based on the website map and RAG historical context.

        Args:
            website_map: The website map containing links, inputs, forms, and headers.
            historical_context: Text describing past test plans from similar websites.

        Returns:
            A TestPlan Pydantic object containing objective, strategy, and test cases.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_SYSTEM_PROMPT),
            ("user", """
Target URL: {url}
Website Map Details:
- Title: {title}
- Description: {description}
- Navigation links found: {nav_count}
- Regular links found: {link_count}
- Buttons found: {button_count}
- Input fields found: {input_count}
- Forms found: {form_count}
- Authentication required: {auth_required}
- CAPTCHA present: {captcha_present}

Discovered Interactive Elements:
{website_map_json}

Historical Reference Context from past test suites:
{historical_context}

Please design a comprehensive, production-grade Test Plan for this website.
""")
        ])

        formatted_prompt = prompt.format_messages(
            url=website_map.url,
            title=website_map.title or website_map.url,
            description=website_map.description or "Web application under test",
            nav_count=len(website_map.navigation),
            link_count=len(website_map.links),
            button_count=len(website_map.buttons),
            input_count=len(website_map.inputs),
            form_count=len(website_map.forms),
            auth_required=website_map.authentication_required,
            captcha_present=website_map.captcha_present,
            website_map_json=website_map.model_dump_json(indent=2),
            historical_context=historical_context or "No historical plans found. Create standard web test suite."
        )

        try:
            structured_llm = self.model.with_structured_output(TestPlan)
            response = structured_llm.invoke(formatted_prompt)
            if response and hasattr(response, "test_cases") and len(response.test_cases) > 0:
                # Ensure sequential IDs and categories are present
                for idx, tc in enumerate(response.test_cases, start=1):
                    if not tc.id or tc.id == "CASE":
                        tc.id = f"TC-{idx:03d}"
                    if not tc.priority:
                        tc.priority = "high" if idx <= 2 else "medium"
                return response
        except Exception as e:
            print(f"[PlannerAgent Warning] Structured LLM invocation failed: {e}. Generating fallback plan.")

        # Resilient fallback plan if LLM output fails
        from app.schemas.test_case import TestCase, TestStep
        from app.schemas.enums import TestCaseStatus

        title = website_map.title or "Target Site"
        cases = [
            TestCase(
                id="TC-001",
                title=f"Verify {title} Homepage Loads and Renders Core Elements",
                description=f"Validate that {website_map.url} navigates successfully and key headers/links render.",
                priority="critical",
                category="smoke",
                preconditions=["Browser is online", f"Target {website_map.url} is accessible"],
                expected_result=f"Page loads with HTTP 200 and title contains '{title}'.",
                status=TestCaseStatus.DRAFT,
                steps=[
                    TestStep(step_number=1, action="navigate", target=website_map.url, expected_result="Page loads"),
                    TestStep(step_number=2, action="verify_element", target="body", expected_result="Body is visible"),
                ]
            ),
            TestCase(
                id="TC-002",
                title="Verify Primary Navigation Links",
                description="Test that discovered navigation items are clickable and functional.",
                priority="high",
                category="navigation",
                preconditions=["Homepage is loaded"],
                expected_result="Navigation items respond to click events.",
                status=TestCaseStatus.DRAFT,
                steps=[
                    TestStep(step_number=1, action="navigate", target=website_map.url, expected_result="Homepage loaded"),
                    TestStep(step_number=2, action="verify_element", target="a", expected_result="Links are present"),
                ]
            )
        ]

        if website_map.inputs or website_map.forms:
            cases.append(
                TestCase(
                    id="TC-003",
                    title="Verify Interactive Form and Input Elements",
                    description="Validate input fields can receive user focus and typed characters.",
                    priority="high",
                    category="functional",
                    preconditions=["Form elements exist on page"],
                    expected_result="Inputs accept text without validation crashes.",
                    status=TestCaseStatus.DRAFT,
                    steps=[
                        TestStep(step_number=1, action="navigate", target=website_map.url, expected_result="Page loaded"),
                        TestStep(step_number=2, action="verify_element", target="input", expected_result="Input is interactive"),
                    ]
                )
            )

        return TestPlan(
            objective=f"Autonomous QA verification suite for {title} ({website_map.url})",
            strategy="Automated smoke, functional, and navigation verification using Playwright MCP browser agent.",
            test_cases=cases
        )


# Singleton instance
planner_agent = PlannerAgent()
