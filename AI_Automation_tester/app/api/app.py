"""
FastAPI Server Setup
====================
Configures and initializes the FastAPI application instance.

WHY DO WE NEED THIS?
FastAPI is the web framework that hosts our REST API endpoints. This file:
1. Creates the FastAPI application instance.
2. Configures CORS (Cross-Origin Resource Sharing) middleware, allowing web browsers 
   on other domains (like a React frontend) to call our API safely.
3. Mounts the static evidence directory (data/evidence) so screenshots captured 
   during test runs can be loaded via HTTP URL in reports.
4. Mounts the reports directory (data/reports) so generated HTML dashboards are viewable.
5. Registers the routes defined in api/routes/test_runs.py.

RUNNING THE SERVER:
  uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload
"""

import os                                               # Filesystem utilities
from fastapi import FastAPI                             # FastAPI framework
from fastapi.middleware.cors import CORSMiddleware      # CORS configuration
from fastapi.staticfiles import StaticFiles             # Static asset server

from app.api.routes.test_runs import router as test_runs_router  # API router


# Initialize the FastAPI app
# title, description, and version will display on the auto-generated Swagger UI (/docs)
app = FastAPI(
    title="AI Web Automation Tester API",
    description="Backend API hosting the autonomous LangGraph + MCP Playwright testing pipeline.",
    version="1.0.0"
)

# -------------------------------------------------------------------------
# CORS MIDDLEWARE
# Required if the frontend client (e.g. React/Vue) is hosted on a different 
# port or domain (e.g. localhost:3000 calling localhost:8000).
# -------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],             # In production, specify exact domain list
    allow_credentials=True,
    allow_methods=["*"],             # Allow all standard HTTP methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],             # Allow all headers
)

# -------------------------------------------------------------------------
# MOUNT STATIC ASSETS
# Serves directories directly over HTTP:
# - data/evidence at /evidence (e.g. localhost:8000/evidence/screenshot.png)
# - data/reports at /reports (e.g. localhost:8000/reports/report_run_123.html)
# -------------------------------------------------------------------------
os.makedirs("data/evidence", exist_ok=True)
os.makedirs("data/reports", exist_ok=True)

app.mount("/evidence", StaticFiles(directory="data/evidence"), name="evidence")
app.mount("/reports", StaticFiles(directory="data/reports"), name="reports")
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")

# -------------------------------------------------------------------------
# REGISTER ROUTERS
# -------------------------------------------------------------------------
app.include_router(test_runs_router)


@app.get("/")
def read_root():
    """
    Landing check to verify the API server is healthy.
    """
    return {
        "status": "healthy",
        "service": "AI Web Automation Tester API",
        "documentation": "/docs"  # Points developers to Swagger interactive docs
    }
