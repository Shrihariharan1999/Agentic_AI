# My First Agent

A small terminal-based agent that uses an LLM to choose and run registered tools before composing a final answer.

## Project structure

- `main.py`: interactive command-line entry point
- `llm.py`: model client
- `registry.py`: available tool registry
- `tools.py`: tool implementations
- `prompts.py`: tool-selection and response prompts

## Setup

Create and activate a virtual environment, install the dependencies, configure `.env`, and run:

```bash
pip install -r requirements.txt
python main.py
```

Enter `exit` to stop the assistant. Keep API keys in `.env`; do not commit secrets.