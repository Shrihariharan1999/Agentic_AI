# VoyageAI — AI Tour Planner

VoyageAI is an AI-powered travel planning app that turns natural-language trip requests into an organized itinerary. Users can ask for destinations, dates, durations, travel modes, hotels, restaurants, weather, attractions, and route details, and the app responds with a structured travel plan.

This project combines:
- React + Vite frontend
- Firebase Authentication for login and session protection
- FastAPI backend for API routes and token validation
- Firestore persistence for chat sessions and messages
- Google Gemini model orchestration via LangChain/LangGraph-style agent workflows
- Real travel-related tools for destinations, routes, hotels, weather, attractions, and more
- Docker and Google Cloud deployment support

---

## Features

- Conversational trip planning
- Weather-aware recommendations for date-aware planning
- Session-based chat persistence
- User ownership checks using Firebase UID
- Google Sign-In authentication
- FastAPI endpoints for chat and session history
- React web app with Markdown-based responses
- Secure environment-variable configuration for secrets
- Docker-ready backend and Cloud Run deployment support

---

## Tech Stack

- Frontend: React, Vite, JavaScript
- Backend: Python, FastAPI, Uvicorn
- AI orchestration: LangChain / LangGraph / deepagents-style workflow
- Model: Google Gemini
- Auth: Firebase Authentication
- Database: Firestore
- Deployment: Firebase Hosting + Google Cloud Run
- Containerization: Docker
- Monitoring: LangSmith / Cloud logging

---

## Project Structure

```text
ai-tour-planner/
├── backend/
│   ├── __init__.py
│   ├── agents.py
│   ├── chat_helper.py
│   ├── database.py
│   ├── firebase.py
│   ├── main.py
│   ├── models.py
│   ├── test_train_tools.py
│   └── tools.py
├── frontend/
│   └── ai-tour-planner-react/
│       ├── src/
│       ├── package.json
│       ├── firebase.json
│       ├── .firebaserc
│       └── index.html
├── Dockerfile
├── requirements.txt
├── .gitignore
├── .env.example
├── VoyageAI_COMPLETE_PROJECT_README.md
└── README.md
```

---

## Prerequisites

Before running the project, install:

- Python 3.11+
- Node.js 18+
- npm
- Firebase CLI
- Docker (optional for containerized local testing)
- Google Cloud CLI (for deployment)

You will also need:
- a Firebase project
- Firestore enabled
- Google Sign-In enabled
- API keys for Gemini and any travel/service APIs used by the tools

---

## Environment Variables

### Backend

Create a `.env` file in the project root and add values similar to:

```env
GEMINI_MODEL=gemini-3.5-flash-lite
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=VoyageAI

GOOGLE_API_KEY=<your-key>
LANGSMITH_API_KEY=<your-key>
GEOAPIFY_API_KEY=<your-key>
GOOGLE_PLACES_API_KEY=<your-key>
SERPAPI_API_KEY=<your-key>
SERPER_API_KEY=<your-key>
RAILRADAR_API_KEY=<your-key>
```

### Frontend

Create a `.env` file inside `frontend/ai-tour-planner-react` and set:

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_FIREBASE_API_KEY=<firebase-web-api-key>
VITE_FIREBASE_AUTH_DOMAIN=<firebase-auth-domain>
VITE_FIREBASE_PROJECT_ID=<firebase-project-id>
VITE_FIREBASE_STORAGE_BUCKET=<firebase-storage-bucket>
VITE_FIREBASE_MESSAGING_SENDER_ID=<firebase-sender-id>
VITE_FIREBASE_APP_ID=<firebase-app-id>
```

Do not commit real keys or Firebase admin credentials. Use `.env.example` as the template.

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Shrihariharan1999/Agentic_AI.git
cd Agentic_AI/ai-tour-planner
```

### 2. Backend setup

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# or
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

### 3. Frontend setup

```bash
cd frontend/ai-tour-planner-react
npm install
```

---

## Run the App Locally

### Start the backend

From the project root:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

FastAPI docs:

```text
http://127.0.0.1:8000/docs
```

### Start the frontend

From the React app folder:

```bash
npm run dev
```

The frontend usually runs at:

```text
http://localhost:5173
```

---

## API Endpoints

The backend exposes these routes:

| Method | Route | Description |
|---|---|---|
| POST | /chat | Submit a travel prompt and receive AI response |
| GET | /sessions | List the authenticated user's sessions |
| GET | /sessions/{session_id}/messages | Get session messages |
| DELETE | /sessions/{session_id} | Delete a session |

Requests require a valid Firebase ID token in the Authorization header.

Example:

```http
POST /chat
Authorization: Bearer <firebase-id-token>
Content-Type: application/json
```

```json
{
  "session_id": "example-session-id",
  "message": "Plan a 3-day trip to Chennai with hotels and food recommendations"
}
```

---

## Authentication Flow

VoyageAI uses Firebase Authentication with Google Sign-In.

```text
Google Sign-In
  ↓
Firebase user
  ↓
Firebase ID token
  ↓
React app sends Bearer token
  ↓
FastAPI verifies token
  ↓
Backend uses Firebase UID for ownership checks
```

This ensures the frontend cannot impersonate another user and that chat data remains protected.

---

## Deployment

### Frontend deployment with Firebase Hosting

```bash
cd frontend/ai-tour-planner-react
npm run build
firebase deploy --only hosting
```

### Backend deployment with Cloud Run

```bash
gcloud run deploy voyageai-backend \
  --source . \
  --project=<gcp-project-id> \
  --region=<gcp-region> \
  --service-account="<cloud-run-service-account>" \
  --allow-unauthenticated
```

The backend and frontend are deployed separately:
- React app is served via Firebase Hosting
- FastAPI app is served via Cloud Run

---

## Architecture Overview

```text
User
  ↓
React Frontend
  ↓
Firebase Auth
  ↓
FastAPI Backend
  ↓
Main AI Agent
  ├── Weather Agent
  ├── Travel tools
  ├── Session logic
  └── Final itinerary response
  ↓
Firestore App Storage
```

The system uses a tool-first design where the model only calls the services needed to answer the user request and avoids unnecessary exploration.

---

## Security Notes

- Never store API keys in source control
- Never upload Firebase admin credentials to GitHub
- Keep `.env` files local only
- Use Firebase config variables for frontend code
- Use Cloud Secret Manager or environment variables for backend deployment

---

## Troubleshooting

### CORS errors
Check that the frontend origin is allowed in the backend `allow_origins` settings.

### Firebase auth fails
Verify:
- Firebase project is correct
- Google Sign-In is enabled
- frontend env variables are filled correctly
- token is being sent in the Authorization header

### Backend fails to start
Check:
- required Python packages are installed
- `.env` values are present
- service dependencies are accessible

### React points to localhost in production
Set `VITE_API_URL` to the deployed backend URL and rebuild.

---

## Important Notes

This repository includes a fuller implementation reference in:

```text
VoyageAI_COMPLETE_PROJECT_README.md
```

That file contains deeper deployment, architecture, and operations details for production use.

---

## License

No license is currently specified in this project. If this repository is made public, add a `LICENSE` file and update this section accordingly.
