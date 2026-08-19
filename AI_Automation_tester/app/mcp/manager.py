from contextlib import asynccontextmanager

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from app.config.settings import settings


class MCPManager:
    def __init__(self):
        self._client = None

    def _build_config(self) -> dict:
        config = {}

        if not settings.mcp_browser_enabled:
            return config

        if settings.mcp_browser_transport == "streamable_http":
            if not settings.mcp_browser_url:
                raise ValueError("MCP_BROWSER_URL is not configured")

            config["browser"] = {
                "transport": "streamable_http",
                "url": settings.mcp_browser_url,
            }

        elif settings.mcp_browser_transport == "stdio":
            if not settings.mcp_browser_command:
                raise ValueError("MCP_BROWSER_COMMAND is not configured")

            args = [arg for arg in settings.mcp_browser_args.split(",") if arg]

            config["browser"] = {
                "transport": "stdio",
                "command": settings.mcp_browser_command,
                "args": args,
            }

        else:
            raise ValueError(f"Unsupported MCP transport: {settings.mcp_browser_transport}")

        return config

    def create_client(self) -> MultiServerMCPClient:
        config = self._build_config()

        if not config:
            raise ValueError("No MCP servers are enabled")

        self._client = MultiServerMCPClient(config)

        return self._client

    async def get_tools(self):
        client = self.create_client()
        return await client.get_tools()

    @asynccontextmanager
    async def browser_session(self):
        client = self.create_client()

        async with client.session("browser") as session:
            tools = await load_mcp_tools(session)
            yield tools


mcp_manager = MCPManager()