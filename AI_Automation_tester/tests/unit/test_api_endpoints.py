from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.api.app import app
from app.services.run_manager import run_manager


client = TestClient(app)


def test_api_health():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@patch("app.api.routes.test_runs.run_workflow_async")
def test_api_create_and_get_run(mock_bg_task):
    # 1. Create a run
    payload = {
        "target_url": "https://example.com",
        "environment": "development"
    }
    response = client.post("/api/test-runs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "run_id" in data
    run_id = data["run_id"]

    # 2. Query run detail
    get_res = client.get(f"/api/test-runs/{run_id}")
    assert get_res.status_code == 200
    run_detail = get_res.json()
    assert run_detail["run_id"] == run_id
    assert run_detail["target_url"].rstrip("/") == "https://example.com"
    assert "progress_percent" in run_detail
    assert "current_stage" in run_detail
    assert "logs" in run_detail
    assert "stats" in run_detail

    # 3. List runs
    list_res = client.get("/api/test-runs")
    assert list_res.status_code == 200
    runs = list_res.json()
    assert any(r.get("run_id") == run_id or r.get("id") == run_id for r in runs)

