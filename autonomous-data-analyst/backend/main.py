"""Expose dataset, session, chat, chart, and report operations over FastAPI."""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from io import BytesIO
from pathlib import Path
import json
import pandas as pd

from agent import DataAnalystAgent
from database import db
from tools import set_dataframe

app = FastAPI(title="Autonomous Data Analyst")

agent = DataAnalystAgent()
# These values mirror the currently selected session dataset for the local
# single-process server; _load_current_dataset refreshes them before chat.
df = None
dataset_name = None
dataset_metadata = ""
current_dataset_id = None

CHART_DIR = Path(__file__).parent / "charts"
CHART_DIR.mkdir(exist_ok=True)

DATASET_DIR = Path(__file__).parent.parent / "datasets"
DATASET_DIR.mkdir(exist_ok=True)

REPORTS_DIR = Path(__file__).parent.parent / "workspace" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/charts", StaticFiles(directory=CHART_DIR), name="charts")
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")


class ChatRequest(BaseModel):
    session_id: str
    message: str


class SessionRequest(BaseModel):
    title: str = "New Chat"


def _dataset_file_path(dataset_id: str, filename: str) -> Path:
    safe_filename = Path(filename).name
    return DATASET_DIR / f"{dataset_id}__{safe_filename}"


def _dataset_metadata_path(dataset_id: str) -> Path:
    return DATASET_DIR / f"{dataset_id}_metadata.json"


def _build_dataset_metadata(dataset_name: str, dataframe: pd.DataFrame) -> str:
    metadata_parts = [
        f"Dataset Name: {dataset_name}",
        f"Rows: {len(dataframe)}",
        f"Columns: {len(dataframe.columns)}",
        f"Duplicate Rows: {dataframe.duplicated().sum()}",
        "Columns and Data Types:"
    ]

    for column, dtype in dataframe.dtypes.items():
        metadata_parts.append(f"- {column}: {dtype}")

    missing_values = dataframe.isnull().sum()
    missing_values = missing_values[missing_values > 0]

    metadata_parts.append("Missing Values:")

    if missing_values.empty:
        metadata_parts.append("- None")
    else:
        for column, missing in missing_values.items():
            metadata_parts.append(f"- {column}: {missing}")

    return "\n".join(metadata_parts)


def _load_current_dataset(session_id: str):
    # Reload the session's current file before every chat so the shared tools
    # analyze the dataset selected for this session.
    global df, dataset_name, dataset_metadata, current_dataset_id

    dataset = db.get_current_dataset(session_id)

    if not dataset:
        df = None
        dataset_name = None
        dataset_metadata = ""
        current_dataset_id = None
        return None

    dataset_id = dataset["dataset_id"]
    filename = dataset["filename"]

    dataset_path = _dataset_file_path(dataset_id, filename)
    metadata_path = _dataset_metadata_path(dataset_id)

    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="Current dataset file is missing.")

    if dataset_path.suffix.lower() == ".csv":
        df = pd.read_csv(dataset_path)
    elif dataset_path.suffix.lower() == ".xlsx":
        df = pd.read_excel(dataset_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported dataset format.")

    dataset_name = filename
    current_dataset_id = dataset_id

    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        dataset_metadata = metadata.get("metadata", "")
    else:
        dataset_metadata = _build_dataset_metadata(dataset_name, df)

    set_dataframe(df, dataset_name)

    return dataset


@app.get("/")
def home():
    """Provide a small health check used by the Streamlit frontend."""
    return {"status": "running", "application": "Autonomous Data Analyst"}


@app.post("/sessions")
def create_session(request: SessionRequest):
    """Create and persist a new conversation."""
    title = request.title.strip() or "New Chat"
    session_id = db.create_session(title)

    return {
        "session_id": session_id,
        "title": title
    }


@app.get("/sessions")
def get_sessions():
    """Return conversations for the sidebar."""
    return {"sessions": db.get_sessions()}


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Return one conversation, its current dataset, and its messages."""
    session = db.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    dataset = db.get_current_dataset(session_id)
    messages = db.get_messages(session_id)

    return {
        "session": session,
        "current_dataset": dataset,
        "messages": messages
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    session = db.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    datasets = db.get_datasets(session_id)

    for dataset in datasets:
        dataset_path = _dataset_file_path(dataset["dataset_id"], dataset["filename"])
        metadata_path = _dataset_metadata_path(dataset["dataset_id"])

        if dataset_path.exists():
            dataset_path.unlink()

        if metadata_path.exists():
            metadata_path.unlink()

    db.delete_session(session_id)

    return {
        "status": "session deleted",
        "session_id": session_id
    }


@app.post("/upload")
async def upload(session_id: str, file: UploadFile = File(...)):
    """Parse, persist, and activate one CSV or Excel dataset for a session."""
    global df, dataset_name, dataset_metadata, current_dataset_id

    session = db.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    filename = Path(file.filename).name
    file_bytes = await file.read()
    suffix = Path(filename).suffix.lower()

    if suffix == ".csv":
        dataframe = pd.read_csv(BytesIO(file_bytes))
    elif suffix == ".xlsx":
        dataframe = pd.read_excel(BytesIO(file_bytes))
    else:
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported.")

    dataset_id = db.add_dataset(session_id, filename)

    dataset_path = _dataset_file_path(dataset_id, filename)
    dataset_path.write_bytes(file_bytes)

    metadata_text = _build_dataset_metadata(filename, dataframe)
    current_dataset = db.get_current_dataset(session_id)

    metadata = {
        "dataset_id": dataset_id,
        "session_id": session_id,
        "dataset_name": filename,
        "version": current_dataset["version"],
        "rows": len(dataframe),
        "columns": list(dataframe.columns),
        "column_count": len(dataframe.columns),
        "duplicate_rows": int(dataframe.duplicated().sum()),
        "metadata": metadata_text
    }

    metadata_path = _dataset_metadata_path(dataset_id)
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8"
    )

    df = dataframe
    dataset_name = filename
    dataset_metadata = metadata_text
    current_dataset_id = dataset_id

    set_dataframe(df, dataset_name)

    db.save_message(
        session_id,
        "dataset_upload",
        json.dumps({
            "dataset_id": dataset_id,
            "filename": filename,
            "version": metadata["version"]
        }),
        dataset_id
    )

    return {
        "session_id": session_id,
        "dataset_id": dataset_id,
        "filename": filename,
        "version": metadata["version"],
        "rows": len(df),
        "columns": list(df.columns),
        "metadata": dataset_metadata
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """Load session context, run the agent graph, and return its result."""
    global dataset_name, dataset_metadata, current_dataset_id

    session = db.get_session(request.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    current_dataset = _load_current_dataset(request.session_id)

    if current_dataset:
        messages = db.get_messages_since_dataset_upload(
            request.session_id,
            current_dataset["dataset_id"]
        )
    else:
        messages = db.get_messages(request.session_id)
        dataset_name = None
        dataset_metadata = ""
        current_dataset_id = None

    user_message_count = sum(
        1 for message in messages
        if message["role"] == "user"
    )

    result = await agent.chat(
            message=request.message,
            history=messages,
            dataset_name=dataset_name,
            dataset_metadata=dataset_metadata,
            session_title=session["title"],
            session_id=request.session_id,
            dataset_id=current_dataset_id,
        )

    generated_title = result.get("session_title", "").strip()

    if not session["title_generated"] and user_message_count >= 1 and generated_title:
        db.rename_session(request.session_id, generated_title)
        db.mark_title_generated(request.session_id)

    db.save_message(
        request.session_id,
        "user",
        request.message,
        current_dataset_id
    )

    db.save_message(
        request.session_id,
        "assistant",
        result["response"],
        current_dataset_id,
        result.get("charts", []),
        result.get("report_path")
    )

    current_session = db.get_session(request.session_id)
    chart_urls = [f"/charts/{chart}" for chart in result["charts"]]

    return {
        "session_id": request.session_id,
        "dataset_id": current_dataset_id,
        "response": result["response"],
        "charts": chart_urls,
        "report_path": result.get("report_path"),
        "validation_status": result["validation_status"],
        "title": current_session["title"]
    }