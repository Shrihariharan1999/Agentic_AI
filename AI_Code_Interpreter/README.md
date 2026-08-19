# AI Code Interpreter

An interactive Python agent that interprets user requests, selects tools, executes code-related tasks, and returns a natural-language response.

## Project structure

- `agent.py`: agent orchestration
- `planner.py`: request planning
- `executor.py`: execution layer
- `llm.py`: model integration
- `memory.py`: conversation or task memory
- `prompts.py`: agent prompts
- `main.py`: interactive CLI entry point

## Setup

Create and activate a virtual environment, install the dependencies, configure `.env`, and start the assistant:

```bash
pip install -r requirements.txt
python main.py
```

Type `exit` to end an interactive session. Keep API keys in `.env`; do not commit secrets.