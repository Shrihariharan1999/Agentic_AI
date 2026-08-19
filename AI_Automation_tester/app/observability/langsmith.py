"""
LangSmith Observability
=======================
LangSmith is LangChain's cloud tracing and observability platform.

WHY DO WE NEED THIS?
When an AI agent runs, it may call 10-20 LLM calls behind the scenes.
Without tracing, you can't see what the agent was "thinking", which tools
it called, how long each step took, or why it made a wrong decision.

With LangSmith enabled, EVERY:
  - LLM call (prompt sent, response received, token count, latency)
  - Tool call (which tool, what args, what result)
  - Agent step (reason → act → observe loop)
  - Chain invocation
...is automatically sent to LangSmith's dashboard for inspection.

HOW IT WORKS:
LangChain reads specific environment variables at startup.
If those env vars are set, all LangChain/LangGraph operations
are automatically traced — no code changes needed in agents.

SETUP:
1. Create a free account at https://smith.langchain.com
2. Get your API key from the settings page
3. Set LANGSMITH_API_KEY and LANGSMITH_TRACING=true in .env
"""

import os  # Standard library for reading and setting environment variables

from app.config.settings import settings  # Our Pydantic settings (reads from .env)


def setup_langsmith() -> None:
    """
    Configures LangSmith tracing by setting the required environment variables.

    LangChain reads these specific env vars at import time and at runtime:
      LANGCHAIN_TRACING_V2   → tells LangChain to activate tracing
      LANGCHAIN_API_KEY      → authenticates your requests to LangSmith
      LANGCHAIN_PROJECT      → groups all traces under a named project
      LANGCHAIN_ENDPOINT     → the LangSmith API server URL

    This function must be called BEFORE any agents or chains are created,
    so it's called at the very start of main().

    Returns:
        None — side effect is setting environment variables
    """

    # Only set up tracing if the user has enabled it in .env
    # LANGSMITH_TRACING=false (default) → skip this entire function
    if not settings.langsmith_tracing:
        return  # Exit early — do not configure any tracing

    # LANGCHAIN_TRACING_V2=true enables the tracing v2 protocol
    # This flag is what tells LangChain to send data to LangSmith
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

    # LANGCHAIN_API_KEY authenticates with LangSmith's cloud service
    # Get this from https://smith.langchain.com → Settings → API Keys
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key

    # LANGCHAIN_PROJECT groups traces together under a named project
    # e.g. "ai-web-tester" → you'll see this project in the LangSmith UI
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

    # LANGCHAIN_ENDPOINT points to the LangSmith API server
    # Default is the cloud: "https://api.smith.langchain.com"
    # Change this for self-hosted LangSmith deployments
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
