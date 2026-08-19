from app.config.settings import settings


def get_browser_config() -> dict:
    if not settings.mcp_browser_enabled:
        raise ValueError("Browser MCP is disabled")

    return {
        "name": "browser",
        "transport": settings.mcp_browser_transport,
        "url": settings.mcp_browser_url,
        "command": settings.mcp_browser_command,
        "args": settings.mcp_browser_args,
    }