"""
Tool Guardrails
===============
Tool guardrails control WHICH browser actions AI agents are allowed to perform.

WHY DO WE NEED TOOL GUARDRAILS?
The Executor Agent is given a browser and told to "execute test cases."
Without guardrails, the agent might (accidentally or if prompted maliciously):
  - Click "Delete Account"
  - Submit a real purchase
  - Access admin-only pages it shouldn't touch
  - Fill in real credit card numbers

Tool guardrails intercept tool calls BEFORE they execute and block dangerous ones.

HOW IT FITS IN THE PIPELINE:
  ExecutorAgent → decides to call browser_click("#delete-account") →
  [ToolGuardrail checks] → BLOCKED / ALLOWED → MCP server
"""

from typing import Any  # For type hinting flexible dict values


# -------------------------------------------------------------------------
# BLOCKED TOOL PATTERNS
# These strings, if found in a tool name or its arguments, will block the call.
# Lowercase — we compare against lowercased versions of names/args.
# -------------------------------------------------------------------------
BLOCKED_TOOL_PATTERNS = [
    "delete",      # Any deletion action (e.g. "delete_account", "delete_post")
    "remove",      # Any removal action
    "purchase",    # Any payment completion
    "payment",     # Payment-related actions
    "checkout",    # Completing an e-commerce checkout with real money
    "drop",        # Database-level drop operations (if somehow exposed)
]

# -------------------------------------------------------------------------
# BLOCKED SELECTOR PATTERNS
# These CSS selectors/text patterns indicate dangerous elements.
# The agent should not interact with elements matching these patterns.
# -------------------------------------------------------------------------
BLOCKED_SELECTOR_PATTERNS = [
    "confirm-delete",   # Confirmation dialogs for delete actions
    "delete-account",   # Account deletion buttons
    "unsubscribe",      # Subscription cancellation
    "btn-danger",       # Bootstrap "danger" buttons often trigger destructive actions
]


def is_tool_allowed(tool_name: str, tool_args: dict[str, Any]) -> bool:
    """
    Checks whether an MCP tool call is safe to execute.

    Args:
        tool_name: The MCP tool being called (e.g. "browser_click", "browser_navigate")
        tool_args: The arguments being passed (e.g. {"selector": "#submit-button"})

    Returns:
        True  → the tool call is safe, allow it
        False → the tool call is dangerous, block it
    """

    # Convert tool name to lowercase for case-insensitive matching
    # "Browser_Click" and "browser_click" should both be checked
    tool_name_lower = tool_name.lower()

    # --- Check 1: Block by tool name ---
    # e.g. if there's a tool called "browser_delete_cookies" → block
    for pattern in BLOCKED_TOOL_PATTERNS:
        if pattern in tool_name_lower:
            return False  # Tool name contains a blocked keyword

    # --- Check 2: Block by argument content ---
    # Convert all args to a single string for pattern matching
    # e.g. {"selector": "#confirm-delete-btn"} → "#confirm-delete-btn"
    args_as_string = str(tool_args).lower()  # str(dict) gives a readable representation

    # Check if any argument contains a blocked pattern
    for pattern in BLOCKED_TOOL_PATTERNS:
        if pattern in args_as_string:
            return False  # Argument contains a blocked keyword

    # Check if any argument contains a blocked selector pattern
    for selector_pattern in BLOCKED_SELECTOR_PATTERNS:
        if selector_pattern in args_as_string:
            return False  # Argument targets a blocked element type

    # If none of the checks fired, the tool call is allowed
    return True


def assert_tool_allowed(tool_name: str, tool_args: dict[str, Any]) -> None:
    """
    Raises an error if the tool call should be blocked.

    Use this in places where you want to stop execution immediately
    if a dangerous tool call is detected.

    Args:
        tool_name: The MCP tool being called
        tool_args: The arguments being passed

    Raises:
        ValueError: If the tool call is blocked by guardrails
    """

    # Reuse the is_tool_allowed check
    if not is_tool_allowed(tool_name, tool_args):
        # Raise a descriptive error so the agent knows WHY it was blocked
        raise ValueError(
            f"Tool call BLOCKED by safety guardrails.\n"
            f"  Tool: '{tool_name}'\n"
            f"  Args: {tool_args}\n"
            f"  Reason: The tool or its arguments match a blocked pattern.\n"
            f"  Blocked patterns: {BLOCKED_TOOL_PATTERNS}"
        )
