"""Run a manual end-to-end check of filesystem and custom MCP writing."""

import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
CUSTOM_SERVER = BASE_DIR / "backend" / "mcp_server.py"


async def main():
    """Run the end-to-end custom MCP report-writing check."""
    # This script intentionally inspects the generated file so a failed MCP
    # response cannot be mistaken for a successful report write.
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    filesystem_params = StdioServerParameters(
        command="npx.cmd" if os.name == "nt" else "npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(WORKSPACE_DIR)],
        env=os.environ.copy(),
    )

    custom_params = StdioServerParameters(
        command=os.sys.executable,
        args=[str(CUSTOM_SERVER)],
        env=os.environ.copy(),
    )

    async with stdio_client(filesystem_params) as (fs_read, fs_write):
        async with ClientSession(fs_read, fs_write) as fs_session:
            await fs_session.initialize()

            async with stdio_client(custom_params) as (custom_read, custom_write):
                async with ClientSession(custom_read, custom_write) as custom_session:
                    await custom_session.initialize()

                    print("[WRITER TEST] Filesystem and custom MCP connected.")

                    report_content = """# Loan Default Analysis

## Validation
PASS

## Key Findings
- Overall default rate: 22.22%
- Renters show a higher default rate than homeowners.
- Loan-to-income burden is positively associated with default risk.

This report contains only validated analysis.
"""

                    result = await custom_session.call_tool(
                        "write_document",
                        {
                            "session_id": "writer-test",
                            "document_name": "Loan Default Analysis",
                            "document_format": "md",
                            "content": report_content,
                            "images": [],
                            "validation_status": "PASS",
                        },
                    )

                    print("\n[WRITER TEST RESULT]")
                    print(result)

                    report_path = WORKSPACE_DIR / "reports" / "Loan Default Analysis.md"

                    print("\n[EXPECTED REPORT]")
                    print(report_path)

                    if report_path.exists():
                        print("\n✅ REPORT CREATED")
                        print(report_path.read_text(encoding="utf-8"))
                    else:
                        print("\n⚠️ REPORT PATH NOT FOUND")
                        print("Check the path returned by write_document().")


if __name__ == "__main__":
    asyncio.run(main())