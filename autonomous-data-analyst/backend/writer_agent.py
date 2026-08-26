"""Provide an asynchronous MCP client for validated document writing."""

import os
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
REPORTS_DIR = WORKSPACE_DIR / "reports"

MAX_WRITER_TOOL_CALLS = 2


class WriterAgent:
    """Standalone MCP client for writing validated reports."""

    def __init__(self):
        """Create the workspace directories used by the writer."""
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _filesystem_params(self):
        return StdioServerParameters(
            command="npx.cmd" if os.name == "nt" else "npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", str(WORKSPACE_DIR)],
            env=os.environ.copy(),
        )

    def _custom_mcp_params(self):
        return StdioServerParameters(
            command=os.sys.executable,
            args=[str(BASE_DIR / "backend" / "mcp_server.py")],
            env=os.environ.copy(),
        )

    async def write(
        self,
        session_id: str,
        document_name: str,
        document_format: str,
        content: str,
        charts: list[str] | None = None,
        validation_status: str = "PASS",
    ) -> dict:
        # Both MCP sessions are opened here so this standalone writer can be
        # tested independently from the main LangGraph report branch.
        charts = charts or []

        if validation_status not in {"PASS", "UNVERIFIED"}:
            raise ValueError(f"Invalid validation status: {validation_status}")

        filesystem_params = self._filesystem_params()
        custom_params = self._custom_mcp_params()

        async with stdio_client(filesystem_params) as (fs_read, fs_write):
            async with ClientSession(fs_read, fs_write) as filesystem_session:
                await filesystem_session.initialize()

                async with stdio_client(custom_params) as (custom_read, custom_write):
                    async with ClientSession(custom_read, custom_write) as custom_session:
                        await custom_session.initialize()

                        custom_tools = await custom_session.list_tools()

                        custom_write_document = next(
                            (tool for tool in custom_tools.tools if tool.name == "write_document"),
                            None,
                        )

                        if custom_write_document is None:
                            raise RuntimeError("Custom MCP write_document tool is unavailable.")

                        print("[WRITER] Using custom write_document.")

                        result = await custom_session.call_tool(
                            "write_document",
                            {
                                "session_id": session_id,
                                "document_name": document_name,
                                "document_format": document_format,
                                "content": content,
                                "images": charts,
                                "validation_status": validation_status,
                            },
                        )

                        print(f"[WRITER RESULT] {result}")

                        return {
                            "status": "SUCCESS",
                            "result": str(result),
                            "validation_status": validation_status,
                            "document_name": document_name,
                            "document_format": document_format,
                        }