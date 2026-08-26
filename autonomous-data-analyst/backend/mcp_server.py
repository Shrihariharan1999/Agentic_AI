"""Run the custom FastMCP server that exposes the application workspace."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP


BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"

for folder in ("files", "charts", "research"):
    # Create MCP-backed directories at startup so tools can use stable paths.
    (WORKSPACE_DIR / folder).mkdir(parents=True, exist_ok=True)

mcp = FastMCP("Autonomous Data Analyst")


if __name__ == "__main__":
    mcp.run(transport="stdio")