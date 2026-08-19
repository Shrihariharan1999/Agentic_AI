from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT_ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)


def _resolve_path(filename: str) -> Path:
    file_path = WORKSPACE / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path


def create_file(filename: str) -> str:
    file_path = _resolve_path(filename)
    file_path.touch(exist_ok=True)
    return f"{filename} created successfully."


def read_file(filename: str) -> str:
    file_path = _resolve_path(filename)

    if not file_path.exists():
        return f"{filename} does not exist."

    return file_path.read_text(encoding="utf-8")


def write_file(filename: str, content: str) -> str:
    file_path = _resolve_path(filename)
    file_path.write_text(content, encoding="utf-8")
    return f"{filename} updated successfully."


def delete_file(filename: str) -> str:
    file_path = _resolve_path(filename)

    if not file_path.exists():
        return f"{filename} does not exist."

    file_path.unlink()
    return f"{filename} deleted successfully."