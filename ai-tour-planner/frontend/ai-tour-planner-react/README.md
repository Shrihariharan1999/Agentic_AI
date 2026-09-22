# AI Tour Planner React Frontend

## Run

npm install

Copy `.env.example` to `.env` and set your FastAPI URL.

npm run dev

Backend endpoints:
- POST /chat
- GET /sessions
- GET /sessions/{session_id}/messages
- DELETE /sessions/{session_id}

For production, configure FastAPI CORS and set VITE_API_URL to the deployed API URL.
