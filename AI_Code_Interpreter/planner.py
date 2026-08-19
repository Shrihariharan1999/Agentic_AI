from llm import LLM
from prompts import PLANNER_PROMPT


class Planner:

    def __init__(self):

        self.llm = LLM()

    def classify(self, user_query: str) -> str:

        messages = [
            {
                "role": "system",
                "content": PLANNER_PROMPT
            },
            {
                "role": "user",
                "content": user_query
            }
        ]

        action = self.llm.generate(messages)

        return action.strip().lower()