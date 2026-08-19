from __future__ import annotations
from typing import List, Dict
from openai import OpenAI
from config import config


class LLM:
    """
    Wrapper around an OpenAI-compatible chat model.
    """

    def __init__(self):

        self.client = OpenAI(base_url=config.BASE_URL,api_key=config.API_KEY,)
        self.model = config.MODEL_NAME

    def generate(self,messages: List[Dict[str, str]],temperature: float | None = None,) -> str:

        if temperature is None:
            temperature = config.TEMPERATURE

        try:

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=config.MAX_TOKENS,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:

            raise RuntimeError(f"LLM request failed:\n{e}") from e