"""
Self-Healing Agent
==================
The Self-Healing Agent corrects test selectors or values when they fail.

WHY DO WE NEED A SELF-HEALING AGENT?
Websites change frequently. An update might change a button's ID from `#signup-btn` 
to `#register-btn`. In traditional testing, this breaks the test suite until a human 
manually updates the code.
The Self-Healing Agent automatically handles this:
1. It analyzes the failed step, the error message, and the current page HTML / Map.
2. It reviews past successful healing steps from the RAG database.
3. It suggests a corrected selector (e.g. using CSS class, text locator, or tag name).
4. It updates the test case so it can be retried immediately.

HOW IT FITS IN THE PIPELINE:
  Failed Step + Selector Error + WebsiteMap -> [Self-Healing Agent] -> Healed Step (Retried)
"""

from pydantic import BaseModel, Field                 # For structured LLM output schemas
from langchain_core.prompts import ChatPromptTemplate  # Prompt templates
from app.models.factory import model_factory            # Our model factory
from app.schemas.test_case import TestCase              # Schema for test cases
from app.schemas.website import WebsiteMap              # Schema representing the website elements


class HealedStepSuggestion(BaseModel):
    """
    Structured suggestion output from the Self-Healing Agent.
    """
    step_number: int = Field(description="The step number that failed and needs to be healed")
    healed_target: str = Field(description="The new corrected target selector (CSS, XPath, or text locator)")
    healed_value: str = Field(default="", description="The new corrected value if input changes are needed")
    reason: str = Field(description="Detailed explanation of why this healed selector was chosen")


SELF_HEALING_SYSTEM_PROMPT = """
You are the Self-Healing Agent of an autonomous web testing system.

Your job is to repair a failed test step by updating its target selector or input value based 
on the current elements present in the Website Map.

Locate the element the test was trying to interact with using alternative attributes:
- Text content matching the button name.
- Input fields with matching placeholders or name attributes.
- CSS classes or structural tags.

Strictly return a structured `HealedStepSuggestion` output.
"""


class SelfHealingAgent:
    """
    Analyzes selector failures and generates corrected targets to heal broken tests.
    """

    def __init__(self):
        # Retrieve the LLM configured for self-healing
        self.model = model_factory.get("self_healing")

    def heal_step(
        self,
        test_case: TestCase,
        failed_step_number: int,
        error_message: str,
        website_map: WebsiteMap,
        past_healing_examples: str = ""
    ) -> HealedStepSuggestion:
        """
        Calculates a corrected selector or value for a failed test step.

        Args:
            test_case: The original test case.
            failed_step_number: The index/number of the step that failed.
            error_message: The failure output or error text.
            website_map: The current state of the page (WebsiteMap).
            past_healing_examples: Historical healing cases from RAG.

        Returns:
            A HealedStepSuggestion detailing the corrected target and rationale.
        """
        # Retrieve the specific failed step details
        failed_step = next((s for s in test_case.steps if s.step_number == failed_step_number), None)
        failed_step_text = f"Action: {failed_step.action}, Target: '{failed_step.target}', Value: '{failed_step.value}'" if failed_step else "Unknown Step"

        prompt = ChatPromptTemplate.from_messages([
            ("system", SELF_HEALING_SYSTEM_PROMPT),
            ("user", """
Failed Step:
{failed_step_text}

Failure Error Message:
{error_message}

Current Website Map (Available Elements):
{website_map_json}

Historical RAG Examples:
{past_healing_examples}

Please find a working locator/selector to heal this step.
""")
        ])

        formatted_prompt = prompt.format_messages(
            failed_step_text=failed_step_text,
            error_message=error_message,
            website_map_json=website_map.model_dump_json(indent=2),
            past_healing_examples=past_healing_examples
        )

        # Bind structured output
        structured_llm = self.model.with_structured_output(HealedStepSuggestion)

        # Invoke the LLM
        healed_suggestion = structured_llm.invoke(formatted_prompt)

        return healed_suggestion


# Singleton instance
self_healing_agent = SelfHealingAgent()
