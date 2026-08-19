from langchain_core.language_models import BaseChatModel


class BaseAgent:
    def __init__(self, model: BaseChatModel, tools: list):
        self.model = model
        self.tools = tools
        