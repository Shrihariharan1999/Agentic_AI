from typing import List, Dict


class ConversationMemory:

    def __init__(self):

        self.messages: List[Dict[str, str]] = []

    def set_system_prompt(self, prompt: str) -> None:

        self.messages = [
            {
                "role": "system",
                "content": prompt
            }
        ]

    def add_user_message(self, message: str) -> None:

        self.messages.append(
            {
                "role": "user",
                "content": message
            }
        )

    def add_assistant_message(self, message: str) -> None:

        self.messages.append(
            {
                "role": "assistant",
                "content": message
            }
        )

    def get_messages(self) -> List[Dict[str, str]]:

        return self.messages

    def clear(self) -> None:

        self.messages.clear()