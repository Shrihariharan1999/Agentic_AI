from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCapabilities:
    tool_calling: bool
    structured_output: bool
    streaming: bool


@dataclass(frozen=True)
class ModelConfig:
    agent_name: str
    provider: str
    model_name: str
    capabilities: ModelCapabilities

    