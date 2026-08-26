# Autonomous Data Analyst

An agentic data-analysis application that lets a user upload a CSV or Excel dataset, ask questions in natural language, generate charts, perform web-supported research, and optionally export a validated report.

The project has two user-facing processes:

```text
Streamlit frontend -> FastAPI backend -> Coordinator -> Analyst -> tools -> Validator
```

For report requests only, the backend adds a draft artifact step:

```text
Analyst -> draft report -> Validator reads draft -> retry or publish final report
```

Regular chat requests do not create report files.

## Features

- Upload `.csv` and `.xlsx` datasets per chat session.
- Preserve chat sessions, dataset versions, messages, and chart references in SQLite.
- Inspect schema, missing values, duplicate rows, previews, and data types.
- Run descriptive statistics, grouping, filtering, sorting, percentages, correlations, and trend analysis.
- Create bar, line, histogram, scatter, and pie charts with matplotlib.
- Use Serper or Tavily for external and current-information research.
- Use Gemini structured outputs for planning and validation.
- Generate Markdown, HTML, or plain-text reports.
- Embed generated chart images in HTML reports.
- Validate report content before publishing the final report.
- Keep filesystem MCP access inside the configured sandbox/workspace.

## Project Structure

```text
autonomous-data-analyst/
├── README.md
├── requirements.txt
├── .env.example
├── .env                         # local secrets; do not commit
├── backend/
│   ├── agent.py                 # Coordinator, Analyst, Validator, graph routing
│   ├── main.py                  # FastAPI app and HTTP endpoints
│   ├── tools.py                 # pandas analysis and chart tools
│   ├── database.py              # SQLite sessions, datasets, and messages
│   ├── browser_agent.py         # Serper/Tavily research tool
│   ├── mcp_client.py            # MCP server connections and tool loading
│   ├── mcp_server.py            # custom filesystem/report MCP server
│   ├── filesystem_mcp.py        # filesystem MCP helper/test server
│   ├── embed_images_tool.py     # local report writer with embedded images
│   ├── writer_agent.py          # asynchronous MCP writer client
│   ├── charts/                  # generated PNG charts
│   └── test/                    # integration and manual MCP tests
├── datasets/                    # uploaded dataset files and metadata
├── frontend/
│   ├── app.py                   # Streamlit controls, API calls, and data flow
│   ├── ui_assets.py             # Loads optional presentation assets
│   ├── styles/
│   │   └── app.css              # Visual styling only
│   └── scripts/                 # Browser behavior only
├── mcp_data/                    # MCP test data and documents
├── sandbox/                     # filesystem MCP sandbox
└── workspace/
    ├── charts/                  # reserved workspace chart area
    ├── files/                   # filesystem MCP files
    ├── reports/                 # generated reports and drafts
    └── research/                # research artifacts
```

The code is organized as a code-first walkthrough: start in `frontend/app.py`, follow its FastAPI requests into `backend/main.py`, and then follow the agent and tool calls. CSS and browser scripts are separated so they can be studied independently.

Runtime files such as `backend/agent.db`, generated charts, uploaded datasets, reports, `.env`, and `.venv` are local state. They should normally be excluded from source control.

## Requirements

- Windows, macOS, or Linux
- Python 3.10 or newer
- Node.js and `npx` for the filesystem and Tavily MCP servers
- A Google Gemini API key
- A Serper API key for the primary web-search provider, or a Tavily API key for fallback research

## Installation

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Set the values in `.env`:

```env
GOOGLE_API_KEY=your-gemini-api-key
SERPER_API_KEY=your-serper-api-key
TAVILY_API_KEY=your-tavily-api-key
MAX_TOOL_CALLS_PER_TURN=8
```

Do not put real keys in `README.md`, `.env.example`, Git commits, or chat messages.

## Running the Application

Open two terminals in the project directory.

Terminal 1, start FastAPI:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location backend
uvicorn main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

Terminal 2, start Streamlit:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

Open the URL printed by Streamlit, normally `http://localhost:8501`.

The backend must be running before the frontend sends requests. Uvicorn reloads Python changes automatically, but a dependency or environment-variable change requires restarting the process.

## Typical Usage

1. Open the Streamlit application.
2. Create or select a chat session.
3. Upload a CSV or Excel file in the sidebar.
4. Ask a normal data question, such as `What is the average fare?`.
5. Ask for a chart when a visual is useful, such as `Show survival by passenger class`.
6. Ask explicitly for a report, such as `Create an HTML report named titanic_analysis_shri`.
7. Find generated reports under `workspace/reports/`.

## Agent Workflow

### 1. Session and dataset loading

`main.py` receives the session ID, loads the current dataset for that session, and calls `set_dataframe()` in `tools.py`. The database stores each upload as a version and marks only the newest version as current.

The analysis tools use module-level `DATAFRAME` and `DATASET_NAME` values. This keeps tool calls simple, but it means the application is intended for a single active backend process and should be revisited before adding multi-worker deployment.

### 2. Coordinator

The Coordinator receives the user request and dataset metadata. It decides:

- The analysis plan
- Required capabilities: `data`, `web`, and/or `filesystem`
- Whether a report was requested
- The report name without an extension
- The report format: `md`, `html`, or `txt`

The Coordinator may call `inspect_data`, but it does not perform the actual analysis or answer the user.

### 3. Analyst

The Analyst follows the Coordinator plan and calls only the tools needed for the request. It can inspect data, calculate statistics, create charts, perform research, and use read-only filesystem tools.

Report-writing tools are blocked from direct Analyst use. This prevents an unvalidated response from being presented as a completed report.

### 4. Validator

The Validator checks numerical claims, interpretation, relevance, chart explanations, and external evidence. For a normal chat request, it validates the Analyst response directly.

For a report request, the application first writes a draft, reads the actual draft file back, and gives the Validator both its path and contents. This means the Validator sees the artifact that will be reviewed, including HTML wrapper content when HTML is selected.

### 5. Report lifecycle

Report detection is intentionally limited to messages containing terms such as `report`, `document`, `export`, `write up`, or `save as`.

Report request flow:

```text
report_requested = true
	|
Coordinator selects name and format
	|
Analyst produces evidence-based content
	|
Application writes <name>__draft.<format>
	|
Validator reads the draft
	|
PASS ----------------------------- FAIL
 |                                  |
Write final report              Analyst receives feedback
Return final path                Draft is overwritten on retry
				      |
			      Validate again
```

The default maximum is one retry (`MAX_VALIDATION_RETRIES = 1`). If the retry limit is exceeded, the latest report is written with a validation warning returned to the user. The current implementation does not delete draft files automatically; drafts are useful for debugging and can be cleaned up later.

Normal chat flow remains:

```text
Coordinator -> Analyst/tools -> Validator -> response
```

No draft or final report is written when `report_requested` is false.

## Backend API

### `GET /`

Health response confirming that the application is running.

### `POST /sessions`

Creates a chat session.

```json
{
  "title": "New Chat"
}
```

### `GET /sessions`

Lists sessions ordered by most recently updated.

### `GET /sessions/{session_id}`

Returns session metadata, the current dataset, and saved messages.

### `DELETE /sessions/{session_id}`

Deletes the session, its dataset files, metadata, and stored messages.

### `POST /upload?session_id=<id>`

Uploads a CSV or Excel file, stores it under `datasets/`, creates metadata, and makes it current for the session.

### `POST /chat`

Accepts:

```json
{
  "session_id": "session-uuid",
  "message": "Create an HTML report about this dataset"
}
```

Returns the response, chart URLs, validation status, report path when applicable, and session title.

## Analysis Tools

`inspect_data()` returns dataset name, dimensions, data types, duplicate count, missing-value counts, and a bounded schema view.

`analyze_data()` supports:

```text
summary, describe, count, sum, mean, median, min, max,
std, variance, unique, value_counts, groupby, filter, sort,
top_n, percentage, correlation, missing, duplicates, trend
```

`create_chart()` supports:

```text
bar, line, histogram, scatter, pie
```

Tool results are truncated to control model token usage. Narrower questions are preferable when a dataset has many columns or rows.

## MCP Integration

`mcp_client.py` connects to:

- The custom Python MCP server in `backend/mcp_server.py`
- The filesystem MCP server scoped to `sandbox/`

The Analyst receives filesystem tools only when the Coordinator selects the `filesystem` capability. Report writing is centralized in the application and is not exposed as a normal Analyst action.

`writer_agent.py` is an alternative asynchronous client for the custom `write_document` MCP tool. The main graph currently uses `write_document_with_images()` from `embed_images_tool.py` for local report generation.

## Storage

- SQLite database: `backend/agent.db`
- Uploaded datasets: `datasets/<dataset-id>__<filename>`
- Dataset metadata: `datasets/<dataset-id>_metadata.json`
- Generated charts: `backend/charts/`
- Reports: `workspace/reports/`
- MCP workspace files: `workspace/files/`, `workspace/research/`, and `workspace/charts/`

The database schema contains `sessions`, `datasets`, and `messages`. Dataset uploads are versioned per session, and messages can retain chart references.

## Testing and Checks

Compile the main Python modules:

```powershell
.\.venv\Scripts\python.exe -m py_compile backend\agent.py backend\main.py frontend\app.py
```

Build the LangGraph without making a model request:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); from agent import DataAnalystAgent; agent = DataAnalystAgent(); agent._build_graph(); print('graph-build-ok')"
```

Run the available pytest tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/test -q
```

Some tests are integration/manual checks and may require API keys, Node.js, or running external MCP servers.

## Troubleshooting

### `FastAPI backend is not running`

Start Uvicorn from the `backend/` directory and confirm `http://127.0.0.1:8000/` responds.

### Gemini authentication errors

Check `GOOGLE_API_KEY` in `.env`, then restart Uvicorn. Do not rely on a `.env` change being picked up by an already-running process.

### Web research is unavailable

Set `SERPER_API_KEY`. If Serper is unavailable or evidence is insufficient, configure `TAVILY_API_KEY` and ensure `npx` can install/run `tavily-mcp`.

### MCP tools do not load

Verify Node.js and `npx` are on `PATH`. On Windows the code uses `npx.cmd`. Also check that the sandbox and workspace directories are writable.

### A report is not created

Check that the request clearly asks for a report or export, inspect Validator output, and look for `[REPORT]` messages in the Uvicorn terminal. A report is written after validation passes or after the retry limit is exceeded.

### Dataset appears to change between sessions

The analysis tools currently hold one module-level dataframe. `main.py` reloads the selected session dataset before each chat, which is correct for the current single-process setup. Multiple Uvicorn workers would require a session-aware data store instead.

## Extension Guide

To add a new analysis operation:

1. Add the operation to the `analyze_data()` docstring.
2. Add validation for required columns and types.
3. Implement the calculation using pandas.
4. Bound or truncate large output.
5. Add a focused test.

To add a new agent capability:

1. Add or wrap the tool in the owning module.
2. Register it in `DataAnalystAgent.__init__()`.
3. Add capability selection rules in `_select_tools_for_capabilities()`.
4. Update the Coordinator prompt so it can select the capability.
5. Update this README and add a test for the routing behavior.

To change report behavior, preserve the separation between draft generation, validation, and final publishing. Any change should also verify that regular chat requests do not create files.

## Design Notes and Limitations

- The LLM is responsible for planning, tool selection, report prose, and validation; deterministic pandas code performs the calculations.
- Validation improves reliability but is not a formal proof of correctness.
- Web research depends on third-party provider availability and source quality.
- Uploaded files and generated reports are local filesystem artifacts, not a production object store.
- The current FastAPI globals are suitable for local development but need redesign for concurrent multi-user workers.
- Report filenames are sanitized by the report writer.

## Development Checklist

Before committing a change:

1. Read the owning module and nearby tests.
2. Keep normal chat and report-only behavior separate.
3. Run Python compilation and diagnostics.
4. Run the narrowest relevant test.
5. Check generated files and remove temporary artifacts.
6. Never commit `.env`, API keys, `.venv`, SQLite runtime data, uploaded personal data, or generated reports unless intentionally required.
