"""Build and run the Coordinator, Analyst, Validator, and report graph."""

from datetime import date
from dotenv import load_dotenv
from typing import Literal
from pathlib import Path
import os
import json
import re
import logging
from uuid import uuid4
from html.parser import HTMLParser

from browser_agent import browser_research
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from tools import inspect_data, analyze_data, create_chart
from embed_images_tool import write_document_with_images
from mcp_client import load_mcp_tools

load_dotenv()

logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)

CURRENT_DATE = date.today().isoformat()

MAX_HISTORY_MESSAGES = 5
MAX_HISTORY_MESSAGE_CHARS = 800
MAX_HISTORY_TOTAL_CHARS = 3000
MAX_VALIDATION_HISTORY_MESSAGES = 12
MAX_VALIDATION_HISTORY_CHARS = 6000
MAX_VALIDATOR_CURRENT_TURN_CHARS = 12000
MAX_VALIDATION_RETRIES = 1
# Tool call cap - configurable via environment variable
MAX_TOOL_CALLS_PER_TURN = int(os.getenv("MAX_TOOL_CALLS_PER_TURN", "8"))
MAX_TOOL_RESULT_CHARS = 3500
ANALYST_BLOCKED_TOOLS = {
    "write_document_with_images",
    "filesystem_write_file",
    "filesystem_edit_file",
    "filesystem_move_file",
}
READ_ONLY_FILESYSTEM_TOOLS = {
    "read_file",
    "read_text_file",
    "read_multiple_files",
    "list_directory",
    "directory_tree",
    "search_files",
    "get_file_info",
}
ANALYST_FILESYSTEM_ROOT = "workspace_filesystem_"

REPORT_REQUEST_PATTERN = re.compile(
    r"(?:\b(?:create|generate|write|produce|publish)\b.{0,40}\b(?:report|document)\b|\b(?:export|save)\b.{0,40}\b(?:report|document|analysis)\b|\bsave as\b)",
    re.IGNORECASE,
)
MAX_REPORT_VALIDATION_CHARS = 12000


class _ReportTextExtractor(HTMLParser):
    """Extract visible report text without sending embedded images to the LLM."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_content = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip_content = True

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip_content = False

    def handle_data(self, data):
        if not self._skip_content and data.strip():
            self.parts.append(data.strip())


def _compact_report_for_validation(content: str, report_format: str) -> str:
    """Keep report meaning while removing oversized HTML/image payloads."""
    if report_format == "html":
        parser = _ReportTextExtractor()
        parser.feed(content)
        content = "\n".join(parser.parts)

    if len(content) <= MAX_REPORT_VALIDATION_CHARS:
        return content

    half_limit = MAX_REPORT_VALIDATION_CHARS // 2
    return (
        content[:half_limit]
        + "\n\n[Middle of report omitted for validation.]\n\n"
        + content[-half_limit:]
    )


def _user_requested_report(message: str) -> bool:
    return bool(REPORT_REQUEST_PATTERN.search(message))


SYSTEM_PROMPT = f"""
You are an evidence-based data analyst. Date: {CURRENT_DATE}.

Tools: inspect_data, analyze_data, create_chart, browser_research, and filesystem tools.

Rules:
- Use tools for dataset facts; never invent data, numbers, sources, or dataset names.
- Hallucination control: treat missing, empty, truncated, or failed tool output as unknown. Never guess or fill gaps. State "not verified" when evidence is insufficient, and cite only facts present in tool results.
- Use inspect_data for missing schema; analyze_data for calculations; create_chart for requested or useful visuals.
- Use browser_research for current, recent, live, or external facts. Do not rely on memory when evidence can be searched.
- When several independent tools are needed, request them together in one response to reduce repeated reasoning. Do not batch tools that depend on an earlier result.
- For filesystem requests, use the workspace root and relative paths such as `reports/CSK_Article.md`; do not search outside the allowed root.
- A search with path `.` may list only the root. For a named file, search likely subdirectories such as `reports`, `files`, `research`, and `analyses`, then read the matching file directly before reporting it missing.
- Use only tool evidence and answer the user's latest request. Follow the Coordinator plan unless it conflicts with that request.
- If dataset facts are required but no dataset exists, ask for a CSV or Excel upload.
- Do not write reports during analysis or claim a report was created. The application writes reports after validation.
- When the application provides a report path, repeat it exactly; generated reports use `workspace/reports/<filename>`.
- Do not output chart URLs, image links, chart paths, or chart filenames; the UI displays charts.
- Keep answers concise while including important evidence.
"""

COORDINATOR_PROMPT = f"""
You are the Coordinator. Date: {CURRENT_DATE}. Plan only; do not answer, calculate, or create charts.

Use supplied metadata and call only inspect_data when it is insufficient. Identify relevant columns, evidence, analysis steps, visual goals, and required capabilities.

Capabilities: data=inspection/calculation/charts; web=current or external facts; filesystem=file/report operations. Select only needed capabilities. Current questions require web; reports require filesystem.

Never invent facts or tool syntax. Describe what the Analyst should do, not how to call tools. Treat missing or conflicting evidence as unresolved and require verification. If dataset facts are required but no dataset exists, require an upload. For a named workspace file, search its likely subdirectories and read it before concluding that it is missing.

For reports, return a filesystem-safe name without extension and format md, html, or txt; default to md. Otherwise return null name and format. If the title is "New Chat", create a 3-6 word title; otherwise preserve it.

Return only structured output.
"""

VALIDATOR_PROMPT = f"""
You are the Validator. Date: {CURRENT_DATE}.

Check the Analyst response against all current-turn evidence: intent, numerical claims, tool interpretation, relevance, unnecessary work, chart explanations, contradictions, and external-source support. Current questions require external evidence; memory-only answers FAIL. Check that previous feedback was corrected. Any unsupported claim, invented value/path/source, ignored tool failure, or conclusion beyond the evidence is a FAIL.

For reports, validate the draft path and contents supplied by the application. Do not fail merely because the requested format is wrapped or rendered.

Return PASS only when the answer is correct, relevant, complete, and supported. Otherwise return FAIL with concise correction instructions.
"""

class CoordinatorDecision(BaseModel):
    plan: str = Field(description="Detailed step-by-step execution plan for the Analyst.")
    title: str = Field(description="Short session title of 3 to 6 words.")
    capabilities: list[Literal["data", "web", "filesystem"]] = Field(default_factory=list, description="Capabilities required for this request.")
    report_name: str | None = Field(default=None, description="Concise report filename without extension, or null when no report is requested.")
    report_format: Literal["md", "html", "txt"] | None = Field(default=None, description="Report format: md, html, or txt; null when no report is requested.")

class ValidationDecision(BaseModel):
    status: Literal["PASS", "FAIL"]
    feedback: str = Field(description="Validation result or concise correction instructions.")

class AgentState(MessagesState):
    dataset_name: str | None
    dataset_metadata: str
    task_plan: str
    session_title: str
    capabilities: list[str]
    report_requested: bool
    report_name: str | None
    report_format: str | None
    draft_report_path: str | None
    draft_report_content: str | None
    report_path: str | None
    generated_charts: list[str]  # Track charts created in this turn
    validation_status: str
    validation_feedback: str
    validation_history: list
    previous_history_context: str
    retry_count: int
    tool_call_count: int
    turn_start_index: int

def _compact_history_text(text: str) -> str:
    if len(text) <= MAX_HISTORY_MESSAGE_CHARS:
        return text
    return text[:MAX_HISTORY_MESSAGE_CHARS - 80] + "\n\n[History message truncated.]"

def _select_history_for_context(history: list) -> list:
    selected = []
    total_chars = 0

    for item in reversed(history[-MAX_HISTORY_MESSAGES:]):
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue

        content = _compact_history_text(str(item.get("content", "")))
        remaining = MAX_HISTORY_TOTAL_CHARS - total_chars
        if remaining <= 0:
            break

        if len(content) > remaining:
            if remaining < 220:
                break
            content = content[:remaining - 40] + "\n\n[History trimmed.]"

        selected.append({"role": role, "content": content})
        total_chars += len(content)

    selected.reverse()
    return selected

def _build_previous_history_context(history: list) -> str:
    if not history:
        return "No previous conversation context."

    selected = []
    for item in history[-MAX_VALIDATION_HISTORY_MESSAGES:]:
        role = item.get("role")
        if role in {"user", "assistant"}:
            selected.append(f"{role.upper()}:\n{item.get('content', '')}")

    if not selected:
        return "No previous conversation context."

    return "\n\n".join(selected)[:MAX_VALIDATION_HISTORY_CHARS]

def _message_text(message) -> str:
    content = message.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )

    return str(content)

def _build_current_turn_context(messages: list, start_index: int) -> str:
    context = []

    for message in messages[start_index:]:
        if isinstance(message, HumanMessage):
            role = "USER"
        elif isinstance(message, AIMessage):
            role = "ANALYST"
        elif isinstance(message, ToolMessage):
            role = "TOOL"
        else:
            role = "MESSAGE"

        context.append(f"{role}:\n{_message_text(message)}")

    full_context = "\n\n".join(context)
    if len(full_context) <= MAX_VALIDATOR_CURRENT_TURN_CHARS:
        return full_context

    # Keep the request and latest evidence visible while bounding repeated
    # tool output that would otherwise be sent again to the Validator.
    first_message = context[0] if context else ""
    recent_context = "\n\n".join(context[1:])
    remaining = MAX_VALIDATOR_CURRENT_TURN_CHARS - len(first_message) - 80
    if remaining <= 0:
        return first_message[:MAX_VALIDATOR_CURRENT_TURN_CHARS]

    return (
        first_message
        + "\n\n[Earlier current-turn evidence omitted.]\n\n"
        + recent_context[-remaining:]
    )

class DataAnalystAgent:

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
        self.coordinator_llm_base = ChatGoogleGenerativeAI(model="gemini-3.5-flash")
        # These are the only local tools the Analyst may request. Report
        # writing remains an application step after validation.
        self.local_tools = [inspect_data, analyze_data, create_chart, browser_research]
        self.coordinator_tools = [inspect_data]
        self.coordinator_llm_with_tools = self.coordinator_llm_base.bind_tools(self.coordinator_tools)
        self.coordinator_llm = self.coordinator_llm_base.with_structured_output(CoordinatorDecision)
        self.validator_llm = self.llm.with_structured_output(ValidationDecision)

        self.mcp_client = None
        self.mcp_tools = []
        self.execution_mcp_tools = []
        self.all_tools = list(self.local_tools)
        self.tool_registry = {}
        self.graph = None

    async def _load_mcp_tools(self):
        if self.mcp_client is not None:
            return

        self.mcp_client, self.mcp_tools = await load_mcp_tools()

        self.execution_mcp_tools = self.mcp_tools
        self.all_tools = self.local_tools + self.execution_mcp_tools
        self.tool_registry = {tool.name: tool for tool in self.all_tools}

        print(f"[MCP] Analyst-capable tools loaded: {len(self.all_tools)}")

    def _select_tools_for_capabilities(self, capabilities):
        selected = []

        if "data" in capabilities:
            selected.extend([inspect_data, analyze_data, create_chart])

        if "web" in capabilities:
            selected.append(browser_research)

        if "filesystem" in capabilities:
            selected.extend(
                tool for tool in self.execution_mcp_tools
                if tool.name.startswith(ANALYST_FILESYSTEM_ROOT)
                and tool.name.split("_filesystem_", 1)[-1] in READ_ONLY_FILESYSTEM_TOOLS
            )

        unique_tools, seen = [], set()

        for tool in selected:
            if tool.name not in seen:
                seen.add(tool.name)
                unique_tools.append(tool)

        return unique_tools

    def _build_graph(self):
        # Keep report generation behind a separate branch so ordinary answers
        # never create files as a side effect.
        def coordinator(state: AgentState):
            session_title = state.get("session_title") or "New Chat"
            dataset_name = state.get("dataset_name") or "No dataset uploaded"
            dataset_metadata = state.get("dataset_metadata") or "No dataset metadata available."
            user_message = _message_text(state["messages"][-1])

            coordinator_context = f"""
Dataset: {dataset_name}

Metadata:
{dataset_metadata}

User request:
{user_message}

Existing session title:
{session_title}

Current date:
{CURRENT_DATE}
"""

            print("[LLM] Coordinator: deciding the plan and whether dataset inspection is needed")
            first_response = self.coordinator_llm_with_tools.invoke([SystemMessage(content=COORDINATOR_PROMPT), HumanMessage(content=coordinator_context)])
            inspection_result = ""

            for tool_call in getattr(first_response, "tool_calls", []):
                if tool_call["name"] == "inspect_data":
                    inspection_result = inspect_data.invoke(tool_call["args"])
                    print("[COORDINATOR] inspect_data executed")

            if inspection_result:
                coordinator_context += f"\n\nFresh dataset inspection:\n{inspection_result}"

            print("[LLM] Coordinator: creating the structured execution plan")
            final_decision = self.coordinator_llm.invoke([SystemMessage(content=COORDINATOR_PROMPT), HumanMessage(content=coordinator_context)])
            final_title = session_title if session_title != "New Chat" else final_decision.title.strip()
            capabilities = list(dict.fromkeys(final_decision.capabilities))
            report_requested = bool(
                final_decision.report_name
                or final_decision.report_format
                or state.get("report_requested", False)
            )

            print(f"[COORDINATOR] PLAN: {final_decision.plan}")
            print(f"[COORDINATOR] TITLE: {final_title}")
            print(f"[COORDINATOR] CAPABILITIES: {capabilities}")
            print(f"[COORDINATOR] REPORT_REQUESTED: {report_requested}")
            if report_requested:
                print(f"[COORDINATOR] REPORT_NAME: {final_decision.report_name} | FORMAT: {final_decision.report_format}")

            return {
                "task_plan": final_decision.plan,
                "session_title": final_title,
                "capabilities": capabilities,
                "report_name": final_decision.report_name,
                "report_format": final_decision.report_format,
                "report_requested": report_requested,
                "dataset_metadata": inspection_result or dataset_metadata,
            }

        def analyst(state: AgentState):
            dataset_name = state.get("dataset_name") or "No dataset uploaded"
            dataset_metadata = state.get("dataset_metadata") or "No dataset metadata available."
            task_plan = state.get("task_plan", "")
            validation_feedback = state.get("validation_feedback", "")
            retry_count = state.get("retry_count", 0)
            tool_call_count = state.get("tool_call_count", 0)
            remaining_tool_calls = max(0, MAX_TOOL_CALLS_PER_TURN - tool_call_count)
            capabilities = state.get("capabilities", [])
            generated_charts = state.get("generated_charts", [])

            # Format chart information for the analyst
            charts_info = ""
            if generated_charts:
                charts_info = f"""

Generated charts in this analysis:
{chr(10).join(f"- {chart}" for chart in generated_charts)}

The application will display and embed these charts after validation. Use the
chart evidence in your answer, but do not write a document or reference chart
paths in the response.
"""

            analyst_prompt = f"""
{SYSTEM_PROMPT}

Current dataset:
{dataset_name}

Dataset metadata:
{dataset_metadata}

Coordinator plan:
{task_plan}

Required capabilities:
{(", ".join(capabilities) if capabilities else "None")}{charts_info}

Tool-call budget:
Maximum this turn: {MAX_TOOL_CALLS_PER_TURN}
Already used: {tool_call_count}
Remaining: {remaining_tool_calls}
Use tools only when necessary. Do not request tools when the remaining budget is 0.

Current date:
{CURRENT_DATE}
"""

            messages = list(state["messages"])

            if retry_count > 0 and messages and isinstance(messages[-1], AIMessage):
                messages = messages[:-1]

            if validation_feedback:
                analyst_prompt += f"""

Previous validator feedback:
{validation_feedback}

Retry number:
{retry_count}

Correct the previous answer using the available evidence and explicitly address the validator feedback.
"""
                messages.append(HumanMessage(content=f"The previous answer failed validation.\n\nValidator feedback:\n{validation_feedback}\n\nCorrect the previous answer using the available evidence.\nDo not ignore the validator feedback.\nDo not invent new information."))

            # Bind only tools required by this request. Sending every MCP tool
            # schema on every Analyst call can consume more tokens than the data.
            selected_tools = [
                tool for tool in self._select_tools_for_capabilities(capabilities)
                if tool.name not in ANALYST_BLOCKED_TOOLS
            ]
            print(f"[ANALYST INVOKED] tools={len(selected_tools)} (request capabilities: {capabilities})")

            if selected_tools:
                print("[LLM] Analyst: reasoning with tools to answer the user request")
                response = self.llm.bind_tools(selected_tools).invoke([SystemMessage(content=analyst_prompt), *messages])
            else:
                print("[LLM] Analyst: reasoning without tools")
                response = self.llm.invoke([SystemMessage(content=analyst_prompt), *messages])

            return {"messages": [response]}

        def route_after_analyst(state: AgentState):
            # Tool calls must finish first; only report requests need a draft
            # artifact before validation.
            if getattr(state["messages"][-1], "tool_calls", None):
                return "tools"
            return "draft_writing" if state.get("report_requested", False) else "validator"

        async def execute_tools(state: AgentState):
            tool_calls = getattr(state["messages"][-1], "tool_calls", [])

            if not tool_calls:
                return {"tool_call_count": state.get("tool_call_count", 0)}

            current_count = state.get("tool_call_count", 0)
            remaining = MAX_TOOL_CALLS_PER_TURN - current_count
            generated_charts = list(state.get("generated_charts", []))
            selected_tool_names = {
                tool.name
                for tool in self._select_tools_for_capabilities(state.get("capabilities", []))
                if tool.name not in ANALYST_BLOCKED_TOOLS
            }

            print(f"\n[TOOLS] Processing {len(tool_calls)} tool call(s) | Budget: {current_count}/{MAX_TOOL_CALLS_PER_TURN}")

            if remaining <= 0:
                print("[TOOLS] ❌ Tool-call budget exhausted.")
                return {"messages": [ToolMessage(content="Tool-call limit reached for this user turn. Continue using the evidence already collected.", tool_call_id=tool_calls[0]["id"])], "tool_call_count": current_count}

            allowed_calls = tool_calls[:remaining]
            # Allow all tools - analyst can choose what's needed
            results = []

            for idx, call in enumerate(allowed_calls, 1):
                tool_name = call["name"]
                tool_args = call["args"]
                
                print(f"\n  [{idx}/{len(allowed_calls)}] 🔧 Tool: {tool_name}")
                print(f"      Args: {json.dumps(tool_args, indent=6) if tool_args else 'None'}")

                if tool_name in ANALYST_BLOCKED_TOOLS:
                    error_msg = "Report file creation is handled after validation; continue with analysis only."
                    print(f"      🚫 {error_msg}")
                    results.append(ToolMessage(content=error_msg, tool_call_id=call["id"]))
                    continue

                if tool_name not in selected_tool_names:
                    error_msg = f"Tool '{tool_name}' was not selected for this request. Continue with the available capabilities."
                    print(f"      🚫 {error_msg}")
                    results.append(ToolMessage(content=error_msg, tool_call_id=call["id"]))
                    continue

                tool = self.tool_registry.get(tool_name)

                if not tool:
                    error_msg = f"Tool '{tool_name}' is not available."
                    print(f"      ❌ {error_msg}")
                    results.append(ToolMessage(content=error_msg, tool_call_id=call["id"]))
                    continue

                try:
                    result = await tool.ainvoke(tool_args)
                    result_str = str(result)
                    if len(result_str) > MAX_TOOL_RESULT_CHARS:
                        result_str = (
                            result_str[: MAX_TOOL_RESULT_CHARS - 80]
                            + "\n\n[Tool result truncated to control token usage.]"
                        )
                    # Track generated charts
                    if "CHART_PATH:" in result_str:
                        chart_path = result_str.replace("CHART_PATH:", "").strip()
                        if chart_path not in generated_charts:
                            generated_charts.append(chart_path)
                            print(f"      📊 Chart tracked: {chart_path}")
                    # Truncate long results for console display
                    display_result = result_str[:200] + "..." if len(result_str) > 200 else result_str
                    print(f"      ✅ Result: {display_result}")
                    results.append(ToolMessage(content=result_str, tool_call_id=call["id"]))
                except Exception as exc:
                    error_msg = f"Tool execution failed: {exc}"
                    print(f"      ❌ {error_msg}")
                    results.append(ToolMessage(content=error_msg, tool_call_id=call["id"]))

            new_count = current_count + len(allowed_calls)
            print(f"\n[TOOLS] ✅ Executed {len(allowed_calls)} tool(s) | Total: {new_count}/{MAX_TOOL_CALLS_PER_TURN}")
            if generated_charts:
                print(f"[CHARTS] Tracked {len(generated_charts)} chart(s): {', '.join(generated_charts)}\n")

            return {"messages": results, "tool_call_count": new_count, "generated_charts": generated_charts}

        def draft_writing(state: AgentState):
            """Write a report draft so the validator can inspect the artifact."""
            messages = state.get("messages", [])
            turn_start_index = state.get("turn_start_index", 0)
            response_text = ""

            for msg in reversed(messages[turn_start_index:]):
                if isinstance(msg, AIMessage):
                    response_text = _message_text(msg)
                    if response_text:
                        break

            if not response_text:
                return {}

            report_name = state.get("report_name") or f"Analysis_Report_{uuid4().hex[:8]}"
            report_format = state.get("report_format") or "md"
            draft_name = f"{report_name}__draft"
            try:
                write_document_with_images.invoke({
                    "document_name": draft_name,
                    "content": response_text,
                    "image_files": state.get("generated_charts") or None,
                    "format": report_format,
                })
            except Exception as exc:
                print(f"[REPORT] ❌ Error writing draft: {exc}")
                return {}

            # Read back the generated file so validation covers the artifact,
            # not merely the text that was passed to the writer.
            draft_path = f"workspace/reports/{draft_name}.{report_format}"
            draft_file = Path(__file__).resolve().parent.parent / draft_path
            draft_file_content = draft_file.read_text(encoding="utf-8")
            print(f"[REPORT] 📝 Draft ready for validation: {draft_path}")
            return {
                "draft_report_path": draft_path,
                "draft_report_content": draft_file_content,
            }

        def validator(state: AgentState):
            current_context = _build_current_turn_context(state["messages"], state["turn_start_index"])
            previous_feedback = state.get("validation_feedback", "")
            draft_path = state.get("draft_report_path")
            draft_content = _compact_report_for_validation(
                state.get("draft_report_content") or "",
                state.get("report_format") or "md",
            )

            validator_context = f"""
{VALIDATOR_PROMPT}

Previous validator feedback:
{previous_feedback or "None"}

Complete current-turn execution:
{current_context}
"""

            if state.get("report_requested", False):
                validator_context += f"""

Report draft to validate:
Path: {draft_path or "unavailable"}
Contents:
{draft_content or "unavailable"}
"""

            print("[LLM] Validator: checking the answer against collected evidence")
            response = self.validator_llm.invoke([HumanMessage(content=validator_context)])
            print(f"[VALIDATOR] {response.status} - {response.feedback}")

            retry_count = state.get("retry_count", 0)
            validation_history = list(state.get("validation_history", []))
            validation_history.append({"status": response.status, "feedback": response.feedback})

            if response.status == "FAIL":
                retry_count += 1

            return {"validation_status": response.status, "validation_feedback": response.feedback, "validation_history": validation_history, "retry_count": retry_count}

        def route_after_validator(state: AgentState):
            status = state.get("validation_status", "FAIL")
            retry_count = state.get("retry_count", 0)

            if not state.get("report_requested", False):
                return END

            if status == "PASS":
                return "report_writing"

            return "analyst" if retry_count <= MAX_VALIDATION_RETRIES else "report_writing"

        def report_writing(state: AgentState):
            """Write report when validator passes OR retries exceeded."""
            if not state.get("report_requested", False):
                print("\n[REPORT] 🚫 Report NOT written - user did not request one")
                return {}

            status = state.get("validation_status", "FAIL")
            retry_count = state.get("retry_count", 0)
            generated_charts = state.get("generated_charts", [])
            
            # Extract response text from last message
            messages = state.get("messages", [])
            response_text = ""
            turn_start_index = state.get("turn_start_index", 0)
            current_turn_messages = messages[turn_start_index:]
            for msg in reversed(current_turn_messages):
                if isinstance(msg, AIMessage):
                    response_text = _message_text(msg)
                    if response_text:
                        break
            
            # Determine if we should write report and what status to show
            should_write_report = False
            if status == "PASS":
                should_write_report = True
                print(f"\n[REPORT] ✅ Writing report - Validator PASSED")
            elif retry_count > MAX_VALIDATION_RETRIES:
                should_write_report = True
                print(f"\n[REPORT] ⚠️ Writing report - Validation retries exceeded (attempt {retry_count})")
            else:
                print(f"\n[REPORT] 🚫 Report NOT written - Validation failed and retries available")
            
            # Write report if conditions met
            if should_write_report and response_text:
                dataset_name = state.get("dataset_name") or "Analysis"
                dataset_stem = Path(dataset_name).stem
                report_name = state.get("report_name")
                document_name = report_name or f"Analysis_Report_{dataset_stem}_{uuid4().hex[:8]}"
                report_format = state.get("report_format") or "md"
                final_content = response_text
                
                try:
                    result = write_document_with_images.invoke({
                        "document_name": document_name,
                        "content": final_content,
                        "image_files": generated_charts if generated_charts else None,
                        "format": report_format,
                    })
                    print(f"[REPORT] 📄 {result}")
                    return {"report_path": f"workspace/reports/{document_name}.{report_format}"}
                except Exception as e:
                    print(f"[REPORT] ❌ Error writing report: {e}")
            
            return {}

        graph_builder = StateGraph(AgentState)
        graph_builder.add_node("coordinator", coordinator)
        graph_builder.add_node("analyst", analyst)
        graph_builder.add_node("tools", execute_tools)
        graph_builder.add_node("draft_writing", draft_writing)
        graph_builder.add_node("validator", validator)
        graph_builder.add_node("report_writing", report_writing)
        graph_builder.add_edge(START, "coordinator")
        graph_builder.add_edge("coordinator", "analyst")

        graph_builder.add_conditional_edges("analyst", route_after_analyst, {"tools": "tools", "draft_writing": "draft_writing", "validator": "validator"})
        graph_builder.add_edge("tools", "analyst")
        graph_builder.add_edge("draft_writing", "validator")
        graph_builder.add_conditional_edges("validator", route_after_validator, {"analyst": "analyst", "report_writing": "report_writing", END: END})
        graph_builder.add_edge("report_writing", END)

        self.graph = graph_builder.compile()

    def _ensure_graph(self):
        if self.graph is None:
            self._build_graph()

    async def chat(self, message: str, history: list, dataset_name: str | None, dataset_metadata: str = "", session_title: str = "New Chat", session_id: str = "", dataset_id: str | None = None):
        print("[FLOW] Starting agent graph")
        await self._load_mcp_tools()
        self._ensure_graph()

        messages = []

        for item in _select_history_for_context(history):
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant":
                messages.append(AIMessage(content=item["content"]))

        messages.append(HumanMessage(content=message))
        turn_start_index = len(messages) - 1

        print("[FLOW] Running Coordinator -> Analyst -> Tools -> Validator graph")
        result = await self.graph.ainvoke({
            "messages": messages,
            "dataset_name": dataset_name,
            "dataset_metadata": dataset_metadata,
            "task_plan": "",
            "session_title": session_title,
            "capabilities": [],
            "report_requested": _user_requested_report(message),
            "report_name": None,
            "report_format": None,
            "draft_report_path": None,
            "draft_report_content": None,
            "report_path": None,
            "generated_charts": [],
            "validation_status": "",
            "validation_feedback": "",
            "validation_history": [],
            "previous_history_context": _build_previous_history_context(history),
            "retry_count": 0,
            "tool_call_count": 0,
            "turn_start_index": turn_start_index,
        })

        print(f"[STATE TITLE] {result.get('session_title', '')}")

        current_messages = result["messages"][turn_start_index:]
        last_message = result["messages"][-1]
        charts = []

        for item in current_messages:
            if not isinstance(item, ToolMessage):
                continue

            content = item.content

            if isinstance(content, str) and content.startswith("CHART_PATH:"):
                chart_path = content.replace("CHART_PATH:", "").strip()
                if chart_path not in charts:
                    charts.append(chart_path)

            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and block.get("text", "").startswith("CHART_PATH:"):
                        chart_path = block["text"].replace("CHART_PATH:", "").strip()
                        if chart_path not in charts:
                            charts.append(chart_path)

        response_text = _message_text(last_message)
        validation_status = result.get("validation_status", "FAIL")
        report_path = result.get("report_path")

        if validation_status != "PASS":
            response_text = "⚠️ Verification warning: The answer could not be fully verified against the available evidence.\n\n" + response_text

        return {
            "response": response_text,
            "charts": charts,
            "validation_status": validation_status,
            "report_path": report_path,
            "validation_history": result.get("validation_history", []),
            "session_title": result.get("session_title", ""),
        }