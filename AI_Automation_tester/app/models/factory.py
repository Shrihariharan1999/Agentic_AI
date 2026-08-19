from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config.settings import settings


class ModelFactory:
    def get(self, agent_name: str):
        provider = settings.get_provider(agent_name)
        model_name = settings.get_model_name(agent_name)

        if not model_name:
            raise ValueError(f"No model configured for agent: {agent_name}")

        if provider == "google":
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY is not configured")

            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.google_api_key,
                temperature=0.2,
                max_output_tokens=8192,
            )

        if provider == "nvidia":
            if not settings.nvidia_api_key:
                raise ValueError("NVIDIA_API_KEY is not configured")

            extra_body = None
            if "nemotron" in model_name.lower():
                extra_body = {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": 16384,
                }

            return ChatOpenAI(
                model=model_name,
                api_key=settings.nvidia_api_key,
                base_url=settings.nvidia_base_url,
                temperature=1,
                top_p=0.95,
                max_tokens=16384,
                extra_body=extra_body,
                model_kwargs={"parallel_tool_calls": False},
            )

        raise ValueError(f"Unsupported LLM provider: {provider}")


model_factory = ModelFactory()