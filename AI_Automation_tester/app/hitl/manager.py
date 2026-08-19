"""
Human-In-The-Loop (HITL) Manager
================================
Manages manual reviews and approval checkpoints during the test pipeline.

WHY DO WE NEED A HITL MANAGER?
Autonomous agents are powerful, but sometimes they need human validation:
- When a test plan is generated: the QA lead should approve/modify it before execution.
- When a CAPTCHA is encountered: a human is needed to solve it.
- When high-risk/destructive actions are requested.

This module provides state handlers and interrupt packaging for LangGraph's native
checkpoints and FastAPI integrations.
"""

from app.schemas.workflow import HumanIntervention     # Schema for human intervention state
from app.schemas.enums import HumanAction               # Action enums (Approve, Reject)


class HITLManager:
    """
    Coordinates state updates and message formatting for human validation pauses.
    """

    def create_intervention_request(self, reason: str, instructions: str) -> dict:
        """
        Creates a dictionary payload representing a pending human review state.

        Args:
            reason: Why the automation has stopped (e.g. "Test Plan generated").
            instructions: Directions for the human (e.g. "Review and type APPROVED").

        Returns:
            A state update dict matching `human_intervention` structure.
        """
        return {
            "human_intervention": HumanIntervention(
                required=True,
                reason=reason,
                instructions=instructions,
                response=""
            ).model_dump()
        }

    def resolve_intervention(self, action: HumanAction, response_text: str = "") -> dict:
        """
        Resolves an outstanding intervention by creating the response update payload.

        Args:
            action: The action chosen by the human (e.g. HumanAction.APPROVE).
            response_text: Feedback or comments left by the reviewer.

        Returns:
            A state update dict clearing the block.
        """
        return {
            "human_intervention": HumanIntervention(
                required=False,  # Clear the block
                reason="",
                instructions="",
                response=f"Action: {action.value}. Feedback: {response_text}"
            ).model_dump()
        }


# Singleton instance
hitl_manager = HITLManager()
