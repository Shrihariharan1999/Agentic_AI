import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLM:

    def __init__(self):

        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY")
        )

        self.model = "meta/llama-3.1-8b-instruct"

    def chat(self,messages,temperature=0.2,max_tokens=512):

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return response