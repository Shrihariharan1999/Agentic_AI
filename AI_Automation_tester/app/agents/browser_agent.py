from langchain.agents import create_agent

from app.models.factory import model_factory


def create_browser_agent(tools: list):
    model = model_factory.get("discovery")

    return create_agent(
        model=model,
        tools=tools,
        system_prompt="You are a browser automation agent. Use the available browser tools to inspect and interact with websites. Do not invent information that you can obtain from the browser.",
    )