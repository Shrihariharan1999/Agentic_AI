from llm import LLM
from memory import ConversationMemory
from executor import PythonExecutor
from prompts import (
    CODE_GENERATION_PROMPT,
    EXPLANATION_PROMPT,
)
from planner import Planner
from prompts import CODE_ONLY_PROMPT

class CodeInterpreterAgent:

    def __init__(self):

        self.llm = LLM()
        self.memory = ConversationMemory()
        self.executor = PythonExecutor()
        self.planner = Planner()

    def run(self, user_query: str) -> str:

        action = self.planner.classify(user_query)
        print(action)

        if action == "general_chat":

                messages = [
                    {
                        "role": "user",
                        "content": user_query
                    }
                ]

                return self.llm.generate(messages)
        if action == "generate_code":

                messages = [
                    {
                        "role": "system",
                        "content": CODE_ONLY_PROMPT
                    },
                    {
                        "role": "user",
                        "content": user_query
                    }
                ]
                return self.llm.generate(messages)

        if action == "execute_python":

            # -----------------------------
            # Step 1: Generate Python Code
            # -----------------------------

            self.memory.clear()

            self.memory.set_system_prompt(CODE_GENERATION_PROMPT)

            self.memory.add_user_message(user_query)

            generated_code = self.llm.generate(
                self.memory.get_messages()
            )

            # -----------------------------
            # Step 2: Execute Python
            # -----------------------------

            execution_result = self.executor.execute(
                generated_code
            )

            # -----------------------------
            # Step 3: Explain Result
            # -----------------------------

            explanation_messages = [
                {
                    "role": "system",
                    "content": EXPLANATION_PROMPT,
                },
                {
                    "role": "user",
                    "content":
                        f"""
                            User Request:
                            {user_query}

                            Generated Python Code:

                            {generated_code}

                            Execution Success:
                            {execution_result.success}

                            Execution Output:

                            {execution_result.output}

                            Execution Error:

                            {execution_result.error}
                            """
                                        }
                                    ]

            final_response = self.llm.generate(
                explanation_messages
            )

            return final_response