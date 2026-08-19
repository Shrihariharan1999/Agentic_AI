from dataclasses import dataclass


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    transport: str
    url: str = ""
    command: str = ""
    args: tuple[str, ...] = ()
    enabled: bool = True