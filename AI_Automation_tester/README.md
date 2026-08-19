# AI Automation Tester

An agentic web testing platform that discovers website workflows, plans browser actions, executes tests, analyzes failures, and produces evidence-backed reports.

## Highlights

- LangGraph workflow orchestration
- Browser-based discovery and test execution
- Self-healing and failure analysis agents
- Evidence capture, reporting, and human-in-the-loop review
- Optional RAG, MCP, and LangSmith integrations

## Project structure

- `app/agents/`: discovery, planning, execution, analysis, and reporting agents
- `app/graph/`: workflow state and graph nodes
- `app/services/`: run management, extraction, evidence, and reporting services
- `app/api/`: API application and routes
- `frontend/`: browser interface
- `tests/`: unit and integration tests

## Setup

Create and activate a virtual environment, install the dependencies, configure the values in `.env`, and run:

```bash
pip install -r requirements.txt
python run.py
```

Run the test suite with:

```bash
pytest
```

Never commit `.env` or API keys.