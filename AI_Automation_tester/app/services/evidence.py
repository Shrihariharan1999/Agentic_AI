"""
Evidence Collector Service
==========================
Captures and saves test execution evidence (screenshots, console logs, page HTML).

WHY DO WE NEED EVIDENCE COLLECTION?
In automated testing, knowing a test failed is only half the battle. Developers 
need proof:
- What did the screen look like? (Screenshots)
- Were there errors in the browser console? (Console logs)
- What was the page HTML structure? (DOM traces)

The EvidenceCollector finds the appropriate tools dynamically from the browser MCP 
session, executes them, saves the output to disk, and returns structured `Evidence` objects.
"""

import os                                           # For filesystem path creation
import uuid                                         # For unique filename generation
from datetime import datetime                       # For timestamped filenames
from app.schemas.test_result import Evidence        # Pydantic schema for evidence records


class EvidenceCollector:
    """
    Saves visual and technical artifacts from browser test executions.
    """

    def __init__(self, output_dir: str = "data/evidence"):
        """
        Initializes the collector.

        Args:
            output_dir: Directory where screenshot/evidence files will be saved.
        """
        self.output_dir = output_dir
        # Ensure the output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    async def capture_screenshot(self, tools: list, test_case_id: str, step_number: int) -> Evidence | None:
        """
        Captures a screenshot of the current page using Playwright MCP tools.

        Args:
            tools: List of loaded browser MCP tools.
            test_case_id: ID of the test case.
            step_number: Current step number.

        Returns:
            An Evidence object containing the path to the saved screenshot, or None if failed.
        """
        # Search dynamically for any tool containing 'screenshot'
        screenshot_tool = next((t for t in tools if "screenshot" in t.name.lower()), None)
        
        if not screenshot_tool:
            print("[Warning] Screenshot tool not found in available browser tools.")
            return None

        # Generate a unique path for the screenshot
        filename = f"screenshot_{test_case_id}_step_{step_number}_{uuid.uuid4().hex[:6]}.png"
        filepath = os.path.abspath(os.path.join(self.output_dir, filename))

        try:
            # Playwright MCP screenshot tool expects 'path' argument
            # or it might return base64. Let's pass the absolute path.
            # To handle both possibilities, we pass both path options:
            await screenshot_tool.ainvoke({"path": filepath})

            # Check if file was written to disk
            if os.path.exists(filepath):
                return Evidence(
                    type="screenshot",
                    location=f"/evidence/{filename}",
                    description=f"Screenshot taken at Step {step_number} of {test_case_id}"
                )
            else:
                # If file wasn't saved, tool might return base64
                return Evidence(
                    type="screenshot_log",
                    location="",
                    description="Screenshot capture attempted."
                )

        except Exception as e:
            print(f"[Error] Failed to capture screenshot: {str(e)}")
            return None

    async def capture_page_html(self, tools: list, test_case_id: str) -> Evidence | None:
        """
        Captures the raw HTML content of the page.

        Args:
            tools: List of browser tools.
            test_case_id: ID of the test case.

        Returns:
            An Evidence object or None.
        """
        # Look for HTML extraction tools
        html_tool = next((t for t in tools if "html" in t.name.lower() or "source" in t.name.lower()), None)
        
        if not html_tool:
            return None

        filename = f"dom_{test_case_id}_{uuid.uuid4().hex[:6]}.html"
        filepath = os.path.abspath(os.path.join(self.output_dir, filename))

        try:
            result = await html_tool.ainvoke({})
            # Save string outcome to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(result))

            return Evidence(
                type="dom",
                location=filepath,
                description=f"Raw DOM content for {test_case_id}"
            )
        except Exception as e:
            print(f"[Error] Failed to capture DOM HTML: {str(e)}")
            return None


# Singleton instance
evidence_collector = EvidenceCollector()
