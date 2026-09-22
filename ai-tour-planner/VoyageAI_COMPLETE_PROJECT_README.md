# VoyageAI — Complete Project & Deployment Reference

> **AI Tour Planner | React + FastAPI + Gemini + LangGraph/deepagents + Firebase + Firestore + Docker + Cloud Run**
>
> This document is the long-form technical reference for the current VoyageAI architecture, source modules, data flow, development workflow, Firebase configuration, GCP deployment, redeployment/rebuild procedures, operations, troubleshooting, and production rules.

---

## 1. What VoyageAI Is

VoyageAI is a conversational AI travel-planning application. The user interacts with a React web application and can ask for trip planning involving destinations, dates, duration, budget, transport, hotels, restaurants, weather, attractions, routes, and other travel preferences.

The central design principle is:

```text
REAL TOOL DATA > MODEL ASSUMPTIONS
USER CONSTRAINTS > SILENT CHANGES
FEWER NECESSARY TOOL CALLS > TOOL EXPLORATION
```

The system uses a Main Agent to coordinate travel planning and a focused Weather Agent for seasonal/exact-date weather analysis. Travel information is obtained from dedicated tools that call external services.

---

# 2. Final Production Architecture

```text
                              ┌───────────────────────────┐
                              │        USER BROWSER       │
                              └─────────────┬─────────────┘
                                            │ HTTPS
                                            ▼
                              ┌───────────────────────────┐
                              │     FIREBASE HOSTING      │
                              │       React + Vite        │
                              └─────────────┬─────────────┘
                                            │
                              Firebase ID Token + API calls
                                            │
                                            ▼
                              ┌───────────────────────────┐
                              │        GOOGLE CLOUD       │
                              │          CLOUD RUN        │
                              │                           │
                              │ FastAPI / Uvicorn         │
                              │ backend.main:app          │
                              └─────────────┬─────────────┘
                                            │
                         ┌──────────────────┼──────────────────┐
                         │                  │                  │
                         ▼                  ▼                  ▼
                 ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
                 │   agents.py │   │ chat_helper  │   │  firebase.py │
                 │ Agent layer │   │ Firestore    │   │ Firebase Admin│
                 └──────┬──────┘   └──────┬───────┘   └──────┬───────┘
                        │                  │                  │
                        ▼                  ▼                  ▼
                 ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
                 │   tools.py  │   │  Firestore   │   │ Firebase Auth│
                 │ travel tools│   │ chat/session │   │ ID token      │
                 └──────┬──────┘   └──────────────┘   └──────────────┘
                        │
             ┌──────────┼───────────┬───────────┬───────────┐
             ▼          ▼           ▼           ▼           ▼
          Weather    Places       Routes      Flights     Hotels
             │          │           │           │           │
             └──────────┴───────────┴───────────┴───────────┘
                                  │
                                  ▼
                               Trains
                                  │
                                  ▼
                         External travel services

Cloud Build → Docker image → Artifact Registry → Cloud Run revision

Secret Manager → runtime API keys
LangSmith → model / agent / tool traces
Cloud Logging → application/request logs
Cloud Monitoring → metrics
Cloud Billing → budgets / spend monitoring
```

### Important architecture separation

The frontend is **not** served by FastAPI. The current deployment is:

```text
React/Vite build
      ↓
dist/
      ↓
Firebase Hosting
```

and separately:

```text
Python backend
      ↓
Docker
      ↓
Cloud Run
```

The Docker image may contain the `frontend/` directory because the Dockerfile copies it, but Uvicorn runs `backend.main:app`; therefore the React application is still deployed through Firebase Hosting.

---

# 3. Core Request Flow

A normal authenticated chat request follows this path:

```text
1. User signs in with Google through Firebase Authentication
              ↓
2. React receives Firebase user/session
              ↓
3. React obtains an ID token
              ↓
4. React sends POST /chat with Authorization: Bearer <ID token>
              ↓
5. FastAPI verifies the Firebase ID token
              ↓
6. Backend resolves/creates the Firestore chat session
              ↓
7. Backend loads recent conversation history
              ↓
8. Backend saves the new user message to Firestore
              ↓
9. After the configured number of user messages, title_model may generate a title
              ↓
10. run_tour_agent(...) starts the agent workflow
              ↓
11. Main/Weather agent uses only necessary tools
              ↓
12. Final response is returned
              ↓
13. Assistant response is saved to Firestore
              ↓
14. FastAPI returns JSON to React
              ↓
15. React renders Markdown response
```

---

# 4. Repository Structure

```text
ai-tour-planner/
│
├── .env                         # LOCAL secrets/config; never commit
├── .gitignore
├── Dockerfile
├── requirements.txt
├── README.md
│
├── backend/
│   ├── __init__.py
│   ├── agents.py                # Main orchestration + Weather Agent
│   ├── tools.py                 # Travel/API tools
│   ├── chat_helper.py           # Firestore chat/session persistence
│   ├── firebase.py              # Firebase Admin / Firestore initialization
│   ├── main.py                  # FastAPI app + API endpoints + auth
│   ├── database.py              # LEGACY MySQL connection code
│   ├── models.py                # LEGACY SQLAlchemy models
│   ├── test_train_tools.py      # Train-tool tests
│   └── <firebase-admin-json>    # LOCAL service account; NEVER commit
│
└── frontend/
    └── ai-tour-planner-react/
        ├── .env                 # Vite frontend config; never commit if sensitive
        ├── .firebaserc          # Firebase project alias
        ├── firebase.json        # Firebase deployment configuration
        ├── index.html
        ├── package.json
        ├── package-lock.json
        ├── src/
        │   ├── App.jsx          # Main UI, auth, sessions, chat
        │   ├── api.js           # Backend HTTP client
        │   ├── firebase.js      # Firebase Web SDK setup
        │   ├── main.jsx         # React entry point
        │   └── styles.css       # Application styling
        └── dist/                # Generated Vite production build
```

---

# 5. Python Backend — File-by-File Reference

## 5.1 `backend/agents.py`

### Responsibility

This is the AI orchestration layer. It converts a user request into a structured travel-planning workflow and coordinates the Main Agent and Weather Agent.

### Main responsibilities

```text
Request understanding
        ↓
Trip vs general vs clarification
        ↓
Weather preparation
        ↓
Main Agent planning
        ↓
Real travel tools
        ↓
Final response
```

### Model

The project loads the Gemini model from the environment:

```python
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
```

The agent stack uses:

```text
Google Gemini
LangChain
LangGraph
Deep Agents
```

### Main state

The planner maintains fields representing the current request, including values such as:

```text
messages
user_message
intent
clarification
origin
destination
duration_days
requested_month
departure_date
return_date
dates_are_user_provided
flight_requested
budget
preferences
weather_plan
max_tool_calls
tool_calls_used
response
```

The exact set can evolve with the current implementation; the important architectural idea is that agent state separates user constraints, planning context, tool-budget information, and the final response.

### Main Agent

The Main Agent is the coordinator. Current agent-visible travel capabilities are designed around:

```python
[
    search_google_places,
    get_route,
    search_flights,
    search_hotels,
    get_weather,
    google_web_search,
    search_train_stations,
    search_trains,
]
```

The agent should not automatically call every tool.

### Weather Agent

Weather is isolated because weather can influence whether the trip period is practical and how outdoor/indoor activities should be scheduled.

Weather-agent capabilities:

```python
[
    get_weather,
    analyze_seasonal_weather,
]
```

A tool-call limit is applied to reduce unnecessary API usage and latency.

### Train Agent history

An independent Train Agent existed in earlier iterations but was intentionally removed. Train logic now belongs to the Main Agent + train tools.

This reduced:

```text
LLM calls
Token consumption
Latency
Repeated reasoning
```

### Public entry point

```python
run_tour_agent(message, thread_id=..., max_tool_calls=...)
```

This function is what the FastAPI layer uses to execute a complete planning turn.

---

## 5.2 `backend/tools.py`

### Responsibility

`tools.py` is the real-world data layer. The LLM decides *when* a tool is needed, while the tool implementation performs the actual API call.

The key rule is:

```text
Model reasoning
      ↓
Tool invocation
      ↓
Real external API
      ↓
Structured result
      ↓
Model planning
```

### Weather tools

`get_weather(...)`

Used for exact-date weather retrieval.

Conceptually:

```text
city + start_date + end_date
          ↓
weather provider
          ↓
forecast / daily weather data
```

`analyze_seasonal_weather(...)`

Used for historical/seasonal reasoning when exact dates are not yet established.

### Places

`search_google_places(...)`

Used to retrieve real:

```text
Attractions
Restaurants
Food options
Shopping places
Local points of interest
```

Returned values may include:

```text
name
address
rating
rating count
coordinates
Google Maps URL
```

The agent should preserve returned URLs and factual fields rather than creating them.

### Routes

`get_route(...)`

Used for verified movement between two locations.

Typical information:

```text
distance
duration
route information
```

This is especially important when grouping nearby attractions and reducing unnecessary backtracking.

### Flights

`search_flights(...)`

Used when flight planning is requested and enough information exists.

The output should be treated as live search data returned by the configured provider.

### Hotels

`search_hotels(...)`

Used to search accommodation for the actual stay dates. The agent should provide multiple suitable results when available and preserve real returned prices/URLs rather than inventing them.

### Web search

`google_web_search(...)`

This is a fallback/general research capability. The preferred order is:

```text
Dedicated travel API/tool
        ↓
Generic web search only when necessary
```

### Train station search

`search_train_stations(query, limit=5)`

Used only when the Main Agent does not know a reliable station code or the station choice is ambiguous.

The LLM should normally choose a practical rail gateway using geography and travel knowledge before performing repeated station searches.

### Train search

`search_trains(from_station, to_station, start_date, end_date=None, class_code="3A", quota_code="GN")`

The agent-visible abstraction is intentionally compact. The train tool handles the underlying train search and availability workflow internally.

Current intended behavior:

```text
Station codes only
        ↓
Search trains
        ↓
Check top candidate availability internally
        ↓
Rank availability
        ↓
Return compact result
```

Availability ranking:

```text
AVAILABLE
RAC
WAITLIST
AVAILABILITY DATA UNAVAILABLE
```

Availability-data-unavailable must not be described as sold out.

### Train date rule

When both journey directions are known:

```text
ONE search_trains call
start_date = outbound
end_date   = return
```

Dates supplied by the user are hard constraints unless the user explicitly allows flexibility.

---

## 5.3 `backend/chat_helper.py`

### Responsibility

This module is the Firestore persistence layer for:

```text
chat sessions
user messages
assistant messages
session titles
```

The old 10-minute expiration mechanism has been removed from the current flow. Existing legacy `expires_at` fields can remain in old Firestore documents; the current code ignores them.

### Data classes

The module defines lightweight record objects for sessions and messages.

Conceptually:

```python
ChatSessionRecord
MessageRecord
```

### Session functions

`create_session(...)`

Creates the Firestore session document and initializes timestamps.

`get_session(...)`

Retrieves one session and verifies that the stored `user_id` matches the authenticated user.

`get_or_create_session(...)`

Returns the existing owned session or creates it when absent.

`get_all_sessions(...)`

Fetches all sessions owned by the authenticated Firebase user and sorts them by activity.

`get_session_messages(...)`

Returns stored messages for one owned session.

`delete_session(...)`

Deletes the user's messages associated with the session and then deletes the session document.

### Message functions

`save_message(...)`

Writes a user/assistant message and updates the parent session's `updated_at` value.

`get_recent_chat(...)`

Loads recent conversation history used for the next agent turn.

The current implementation uses Firestore filtering and Python-side sorting for the recent-history query to avoid relying on an additional composite index.

### Title generation

`maybe_generate_session_title(...)`

The current design generates a title only after enough user messages exist. The selected title-generation input is limited to the most recent user messages rather than passing the whole conversation.

This reduces token usage.

---

## 5.4 `backend/firebase.py`

### Responsibility

Initializes Firebase Admin and exposes the Firestore client used by the backend.

Conceptually:

```text
Firebase Admin SDK
       ↓
service account / Google credentials
       ↓
Firestore client
       ↓
chat_helper.py
```

The local service-account JSON is sensitive credential material and must be ignored by Git.

In production, the preferred design is to use the Cloud Run service account and Google Cloud IAM rather than packaging private credentials into the container.

---

## 5.5 `backend/main.py`

### Responsibility

`main.py` is the FastAPI HTTP boundary.

It handles:

```text
HTTP requests
CORS
Firebase ID-token verification
session ownership
chat calls
Firestore persistence
```

### FastAPI application

```python
app = FastAPI(title="VoyageAI")
```

### CORS

Current production origins include the local Vite origins and the deployed Firebase Hosting origin.

When the production frontend URL changes, update CORS and redeploy Cloud Run.

### Authentication

The backend uses a bearer-token dependency:

```text
Authorization: Bearer <Firebase ID token>
```

Firebase Admin verifies the token and extracts the Firebase UID.

### API endpoints

#### `POST /chat`

Input:

```json
{
  "session_id": "...",
  "message": "Plan a 3-day trip..."
}
```

Flow:

```text
verify user
→ get/create session
→ load recent chat
→ save user message
→ maybe generate title
→ run_tour_agent
→ save assistant response
→ return JSON
```

#### `GET /sessions`

Returns all sessions belonging to the authenticated user.

#### `GET /sessions/{session_id}/messages`

Returns messages only when the session belongs to the authenticated user.

#### `DELETE /sessions/{session_id}`

Deletes an owned session and its messages.

### Ownership protection

The backend checks:

```text
request user UID
        ==
Firestore session user_id
```

This prevents one authenticated user from reading another user's conversation through the backend API.

---

## 5.6 `backend/database.py` — Legacy

This module belongs to the former MySQL/SQLAlchemy architecture.

Historical architecture:

```text
FastAPI
  ↓
SQLAlchemy
  ↓
PyMySQL
  ↓
MySQL
```

The current production chat/session architecture is:

```text
FastAPI
  ↓
Firebase Admin
  ↓
Firestore
```

Cloud SQL/MySQL was removed from the active deployment to reduce cost and operational overhead.

Keep this file only if you intentionally want the historical implementation for learning/reference. It is not part of the current production chat/session flow.

---

## 5.7 `backend/models.py` — Legacy

This contains the SQLAlchemy models from the earlier MySQL implementation.

The historical model concepts included chat/session and review/message data.

The current Firestore implementation does not use these SQLAlchemy ORM models for the production chat flow.

---

## 5.8 `backend/test_train_tools.py`

### Responsibility

Train-tool regression/testing module.

Use it to validate that train station lookup, train search, date handling, and availability-related behavior work correctly before deploying.

Typical pattern:

```powershell
python -m pytest backend/test_train_tools.py -v -s
```

The exact tests can evolve with `tools.py`.

---

## 5.9 `backend/__init__.py`

Marks `backend` as a Python package so relative imports such as:

```python
from .tools import ...
from .firebase import ...
```

work correctly.

---

# 6. Python Module Dependency Map

```text
backend.main
   ├── backend.agents
   ├── backend.chat_helper
   └── backend.firebase

backend.agents
   ├── Gemini
   ├── LangChain
   ├── LangGraph
   ├── Deep Agents
   └── backend.tools

backend.chat_helper
   ├── Firebase Firestore
   └── Gemini title model

backend.firebase
   └── Firebase Admin SDK

backend.tools
   └── External travel APIs / services

backend.database
   └── LEGACY SQLAlchemy/MySQL

backend.models
   └── LEGACY SQLAlchemy models

backend.test_train_tools
   └── backend.tools
```

---

# 7. Agent Architecture in Detail

## 7.1 Why a graph?

The workflow is not just one uncontrolled LLM call. The graph provides explicit stages.

```text
START
  ↓
Understand request
  ↓
┌─────────────────────┐
│ trip?               │
│ general?            │
│ needs clarification?│
└──────────┬──────────┘
           │
     ┌─────┼─────────────┐
     │     │             │
     ▼     ▼             ▼
  Weather Clarify    Main Agent
     │      │             │
     └──────┴──────┬──────┘
                    ▼
                  Final
                    ↓
                   END
```

## 7.2 Request understanding

The planner first establishes whether the user is asking for:

```text
trip
```

```text
general travel question
```

or:

```text
clarification required
```

It is important that the system does not invent critical missing values such as exact dates, duration, origin, destination, or budget constraints.

## 7.3 Weather-first planning

For a trip request:

```text
Trip request
    ↓
Weather analysis
    ↓
Main travel planning
```

When exact dates are supplied:

```text
use those exact dates
```

When only a month/year is supplied:

```text
seasonal weather analysis
        ↓
planner-suggested date window
        ↓
ask user when an important confirmation is needed
```

## 7.4 Tool-budgeting

The agent has an explicit tool-call budget.

The purpose is to avoid:

```text
repeated searches
station permutations
multiple hotel searches without need
multiple restaurant searches without need
unnecessary route calculations
```

This is both a latency and cost-control mechanism.

---

# 8. Travel Planning Rules

## Dates

```text
User-provided exact dates = HARD CONSTRAINT
```

Never silently:

```text
change dates
extend trip
shorten trip
search other dates to force transport
```

If the requested dates make a transport option impossible, report that constraint and ask what the user wants to change.

## Budget

Keep the user's stated budget unchanged.

Do not claim:

```text
"this fits your budget"
```

unless the actual returned costs support the statement.

## Hotels

Search for the actual stay dates.

Provide at least two suitable options when available.

Preserve real returned:

```text
prices
URLs
hotel details
```

Do not invent missing values.

## Restaurants

Use real place-search results.

For vegetarian/non-vegetarian preferences, use the user's actual preference and return real places from the tool results.

## Places

Group geographically close attractions on the same day where practical.

Use routes when actual movement time/distance matters.

## Trains

Use practical rail gateways rather than repeatedly exploring station permutations.

If a nearby major rail gateway is needed, choose one practical gateway based on geography and then use route data for onward movement.

Tatkal may be mentioned as a possibility when the user explicitly wants a train but current seats are unavailable; never claim Tatkal availability without evidence from an appropriate source.

---

# 9. Firestore Data Architecture

The current production chat store contains two logical collections:

```text
chat_sessions
messages
```

## 9.1 `chat_sessions`

Document ID:

```text
session_id
```

Conceptual fields:

```text
user_id
 title
 created_at
 updated_at
```

Legacy documents may contain:

```text
expires_at
```

but the current implementation does not use session expiry.

## 9.2 `messages`

Each message is a separate document with fields such as:

```text
session_id
user_id
role
content
created_at
```

Typical roles:

```text
user
assistant
```

## 9.3 Ownership model

Every session/message is associated with a Firebase UID.

The backend performs an ownership check before reading/deleting session data.

## 9.4 Index

The Firestore deployment created a composite index for the `messages` collection using:

```text
session_id ASC
created_at ASC
```

The current recent-history implementation can filter and sort in Python, reducing reliance on additional index definitions.

---

# 10. Firebase Architecture

Firebase is used for several different concerns:

```text
Firebase Authentication → user sign-in
Firestore               → chat persistence
Firebase Hosting        → React static frontend
```

These are separate products/services even though they are inside the same Firebase project.

---

# 11. Firebase Authentication Setup

Current authentication uses Google Sign-In.

## Console setup

In Firebase Console:

```text
Authentication
    ↓
Sign-in method
    ↓
Google
    ↓
Enable
```

A Web App is registered so the React application can initialize Firebase.

## Browser flow

```text
Google Sign-In
      ↓
Firebase user
      ↓
getIdToken()
      ↓
Authorization header
      ↓
FastAPI
```

The client does not send a password to the FastAPI API.

---

# 12. Firebase Hosting Frontend

## Frontend directory

```text
frontend/ai-tour-planner-react
```

## Install dependencies

```powershell
cd frontend/ai-tour-planner-react
npm install
```

## Local development

```powershell
npm run dev
```

Vite normally serves the application on a localhost port such as `5173`.

## Production build

```powershell
npm run build
```

Output:

```text
dist/
```

## Hosting initialization

From the React project directory:

```powershell
firebase init hosting
```

Choose the existing Firebase project and use `dist` as the public directory. For a React SPA, enable the single-page-app rewrite.

## Hosting deployment

```powershell
firebase deploy --only hosting
```

This deploys only Hosting content/configuration, not Cloud Run.

Firebase's current Hosting quickstart documents the same initialization and deployment flow.

---

# 13. Firebase Firestore Database Management

## Current production creation path

The current Firestore database was created through the Firebase Console:

```text
Firebase Console
→ Build
→ Firestore Database
→ Create database
→ Native / Production mode
→ choose region
```

The current deployment uses the `asia-south1` Firestore location.

## CLI initialization for a project that manages Firestore configuration

From the project root:

```powershell
firebase init firestore
```

This can create/configure local Firestore Security Rules and index configuration files.

Typical files:

```text
firestore.rules
firestore.indexes.json
firebase.json
```

## Deploy Firestore rules and indexes

```powershell
firebase deploy --only firestore
```

Firebase documents `--only firestore` as the partial deployment target for Firestore Security Rules and indexes.

## View Firestore indexes

```powershell
firebase firestore:indexes
```

Firebase documents this command for listing deployed indexes.

## Firestore emulator

For local Firestore testing, when the emulator is configured:

```powershell
firebase emulators:start --only firestore
```

## Current composite index definition

The deployed VoyageAI `messages` index is represented conceptually by:

```json
{
  "indexes": [
    {
      "collectionGroup": "messages",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "session_id", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "ASCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

This example documents the current index that was created during development. Keep index definitions synchronized if you choose to manage them through `firestore.indexes.json`.

## Important rules-management warning

If Security Rules are maintained in local files and deployed with the CLI, those deployed rules can overwrite console-managed rules. Keep the source-of-truth location consistent. Firebase explicitly warns about this deployment interaction.

## Current app-specific note

VoyageAI's current backend talks to Firestore through the Firebase Admin SDK. Do not add a second independent database implementation unless there is a clear architectural requirement.

---

# 14. Firebase CLI Command Reference

## Login

```powershell
firebase login
```

## Logout

```powershell
firebase logout
```

## List projects

```powershell
firebase projects:list
```

## Set/select Firebase project

```powershell
firebase use <PROJECT_ID>
```

## Add an alias interactively

```powershell
firebase use --add
```

## Initialize Hosting

```powershell
firebase init hosting
```

## Initialize Firestore

```powershell
firebase init firestore
```

## Deploy Hosting

```powershell
firebase deploy --only hosting
```

## Deploy Firestore configuration

```powershell
firebase deploy --only firestore
```

## Deploy multiple Firebase resources

```powershell
firebase deploy --only hosting,firestore
```

## Full Firebase project deployment

```powershell
firebase deploy
```

Use this only when you intentionally want all locally configured deployable Firebase resources updated.

## Preview channel

```powershell
firebase hosting:channel:deploy <CHANNEL_ID>
```

Firebase documents preview channels as a way to test changes before live deployment.

## List Hosting sites

```powershell
firebase hosting:sites:list
```

## Firebase version

```powershell
firebase --version
```

## Update Firebase CLI

```powershell
npm install -g firebase-tools
```

---

# 15. Google Cloud Projects Used

The deployment separates concerns between the Firebase project and the Google Cloud project used for Cloud Run.

```text
Firebase project:
voyageai-702fe

Cloud Run / infrastructure project:
voyageai-161299
```

Cloud Run region:

```text
asia-south1
```

Current production services:

```text
Firebase Hosting → voyageai-702fe.web.app
Cloud Run        → voyageai-backend
```

---

# 16. Google Cloud CLI Setup

## Install Google Cloud CLI

Install the current Google Cloud CLI for your operating system.

## Authenticate

```powershell
gcloud auth login
```

## Check authenticated accounts

```powershell
gcloud auth list
```

## Set active project

```powershell
gcloud config set project voyageai-161299
```

## Verify project

```powershell
gcloud config get-value project
```

## Get project number

```powershell
gcloud projects describe voyageai-161299 --format="value(projectNumber)"
```

---

# 17. Enable Required Google Cloud APIs

```powershell
gcloud services enable run.googleapis.com --project=voyageai-161299
```

```powershell
gcloud services enable cloudbuild.googleapis.com --project=voyageai-161299
```

```powershell
gcloud services enable artifactregistry.googleapis.com --project=voyageai-161299
```

```powershell
gcloud services enable secretmanager.googleapis.com --project=voyageai-161299
```

Check enabled services:

```powershell
gcloud services list --enabled --project=voyageai-161299
```

---

# 18. Cloud Run Runtime Service Account

Create the dedicated runtime service account:

```powershell
gcloud iam service-accounts create voyageai-cloud-run `
  --project=voyageai-161299 `
  --display-name="VoyageAI Cloud Run"
```

Expected identity pattern:

```text
voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com
```

List service accounts:

```powershell
gcloud iam service-accounts list --project=voyageai-161299
```

---

# 19. Firestore IAM for Cloud Run

Grant Firestore access to the Cloud Run runtime service account in the Firebase project:

```powershell
gcloud projects add-iam-policy-binding voyageai-702fe `
  --member="serviceAccount:voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" `
  --role="roles/datastore.user"
```

Check IAM policy:

```powershell
gcloud projects get-iam-policy voyageai-702fe
```

---

# 20. Cloud Build / Source Deployment IAM

For source-based Cloud Run deployment, the build identity needs the appropriate build/deployment permissions.

Get project number:

```powershell
gcloud projects describe voyageai-161299 --format="value(projectNumber)"
```

The deployment used the Compute/Builder identity represented by:

```text
<PROJECT_NUMBER>-compute@developer.gserviceaccount.com
```

Grant the Cloud Run Builder role:

```powershell
gcloud projects add-iam-policy-binding voyageai-161299 `
  --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" `
  --role="roles/run.builder"
```

Replace `<PROJECT_NUMBER>` with the value returned by `gcloud projects describe`.

---

# 21. Secret Manager

## Required secret names

The current backend uses these environment/secret names:

```text
GOOGLE_API_KEY
LANGSMITH_API_KEY
GEOAPIFY_API_KEY
GOOGLE_PLACES_API_KEY
SERPAPI_API_KEY
SERPER_API_KEY
RAILRADAR_API_KEY
```

Secret names are not secret values.

Never place the actual values in this README or source code.

## Enable Secret Manager

```powershell
gcloud services enable secretmanager.googleapis.com --project=voyageai-161299
```

## Create a secret

```powershell
gcloud secrets create GOOGLE_API_KEY `
  --project=voyageai-161299 `
  --replication-policy="automatic"
```

Repeat for each required secret.

## List secrets

```powershell
gcloud secrets list --project=voyageai-161299
```

## Add a secret version

For simple interactive/controlled environments, use the current Google Cloud Secret Manager command appropriate to your shell. When storing API keys on Windows, avoid accidental trailing CR/LF characters.

A safe PowerShell pattern is:

```powershell
$value = "<SECRET_VALUE>"
$tempFile = Join-Path $env:TEMP "voyageai-secret.txt"
[System.IO.File]::WriteAllText($tempFile, $value, [System.Text.UTF8Encoding]::new($false))
gcloud secrets versions add GOOGLE_API_KEY --project=voyageai-161299 --data-file=$tempFile
Remove-Item $tempFile
```

Repeat with the appropriate secret name.

## View secret versions

```powershell
gcloud secrets versions list GOOGLE_API_KEY --project=voyageai-161299
```

Do not print secret values into terminal history or logs.

## Grant Cloud Run access

```powershell
gcloud secrets add-iam-policy-binding GOOGLE_API_KEY `
  --project=voyageai-161299 `
  --member="serviceAccount:voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor"
```

Repeat for all secrets used by the container.

---

# 22. Environment Variables

## Local backend `.env`

Typical values/configuration:

```env
GEMINI_MODEL=gemini-3.5-flash-lite
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=VoyageAI

GOOGLE_API_KEY=<local secret>
LANGSMITH_API_KEY=<local secret>
GEOAPIFY_API_KEY=<local secret>
GOOGLE_PLACES_API_KEY=<local secret>
SERPAPI_API_KEY=<local secret>
SERPER_API_KEY=<local secret>
RAILRADAR_API_KEY=<local secret>
```

Any historical MySQL `DATABASE_URL` value belongs to the legacy architecture and is not part of the active Cloud Run chat/session flow.

## Frontend `.env`

The current Vite frontend needs the production backend URL:

```env
VITE_API_URL=https://voyageai-backend-571503113205.asia-south1.run.app
```

After changing any `VITE_*` variable:

```powershell
npm run build
```

and then redeploy Hosting.

---

# 23. Dockerfile

Current container concept:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

## What the Dockerfile does

```text
python:3.11-slim
        ↓
working directory /app
        ↓
install Python requirements
        ↓
copy backend
        ↓
copy frontend directory
        ↓
expose port
        ↓
start Uvicorn
```

Cloud Run supplies the runtime port through the `PORT` environment variable.

---

# 24. Python Dependencies

Current production dependencies:

```text
fastapi==0.141.1
uvicorn[standard]==0.52.4

langchain==1.4.0
langchain-core==1.6.2
langgraph==1.2.11
deepagents==0.7.13
langchain-google-genai==4.4.0

langsmith==0.12.4

firebase-admin==7.6.0
google-cloud-firestore==2.31.0

python-dotenv==1.2.3
requests==2.34.2
```

Legacy-only packages such as SQLAlchemy/PyMySQL were removed from the active production requirements after the Firestore migration.

---

# 25. Local Backend Development

From project root:

```powershell
python -m venv .venv
```

Activate in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start FastAPI:

```powershell
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

---

# 26. Local Frontend Development

```powershell
cd frontend/ai-tour-planner-react
npm install
npm run dev
```

The frontend should use the local backend during development:

```env
VITE_API_URL=http://127.0.0.1:8000
```

For production, use the Cloud Run URL instead.

---

# 27. Frontend File-by-File Reference

## `src/App.jsx`

This is the main UI component.

Responsibilities include:

```text
Firebase authentication state
Google Sign-In
Sign-out
Session list
Active session selection
Loading chat messages
Sending messages
Deleting sessions
sessionStorage for active session
Markdown rendering
Responsive sidebar/menu behavior
Loading/typing state
Error banners
```

The session expiration timer from the old 10-minute implementation has been removed.

## `src/api.js`

Centralizes HTTP calls from React to FastAPI.

Conceptually:

```text
api.sessions()
api.sessionMessages(sessionId)
api.chat(sessionId, message)
api.deleteSession(sessionId)
```

Each authenticated backend request includes a Firebase ID token.

## `src/firebase.js`

Initializes the Firebase Web SDK and exposes:

```text
auth
Google provider
Firebase app configuration
```

## `src/main.jsx`

React entry point.

Typical responsibility:

```text
ReactDOM
  ↓
<StrictMode>
  ↓
<App />
```

## `src/styles.css`

Contains application-level styling for the chat interface, sidebar, composer, messages, buttons, responsive layout, and authentication/loading views.

## `package.json`

Defines:

```text
React runtime dependencies
Firebase
React Markdown
Lucide React
Vite
build/dev scripts
```

---

# 28. Frontend Authentication + API Sequence

```text
Firebase Auth
    ↓
currentUser
    ↓
getIdToken()
    ↓
api.js
    ↓
Authorization: Bearer <token>
    ↓
FastAPI dependency
    ↓
auth.verify_id_token(...)
    ↓
Firebase UID
```

The UID becomes the ownership key for the Firestore-backed session system.

---

# 29. First-Time GCP Deployment — Full Sequence

This is the full deployment path in order.

## Step 1 — Login

```powershell
gcloud auth login
```

## Step 2 — Select project

```powershell
gcloud config set project voyageai-161299
```

## Step 3 — Enable APIs

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --project=voyageai-161299
```

## Step 4 — Create runtime service account

```powershell
gcloud iam service-accounts create voyageai-cloud-run `
  --project=voyageai-161299 `
  --display-name="VoyageAI Cloud Run"
```

## Step 5 — Grant Firestore role

```powershell
gcloud projects add-iam-policy-binding voyageai-702fe `
  --member="serviceAccount:voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" `
  --role="roles/datastore.user"
```

## Step 6 — Configure source-deployment IAM

Get project number:

```powershell
gcloud projects describe voyageai-161299 --format="value(projectNumber)"
```

Grant builder role to the applicable deployment identity:

```powershell
gcloud projects add-iam-policy-binding voyageai-161299 `
  --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" `
  --role="roles/run.builder"
```

## Step 7 — Create secrets and grant access

Create each secret, add the value, and grant:

```text
roles/secretmanager.secretAccessor
```

## Step 8 — Deploy Cloud Run

From the project root, use the production command in Section 30.

## Step 9 — Build frontend

```powershell
cd frontend/ai-tour-planner-react
npm run build
```

## Step 10 — Initialize Hosting if first time

```powershell
firebase login
firebase init hosting
```

## Step 11 — Deploy Hosting

```powershell
firebase deploy --only hosting
```

---

# 30. Cloud Run — Canonical Production Deployment / Rebuild Command

From the project root:

```powershell
gcloud run deploy voyageai-backend `
  --source . `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --service-account="voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" `
  --allow-unauthenticated `
  --set-env-vars="LANGSMITH_TRACING=true,LANGSMITH_PROJECT=VoyageAI,GEMINI_MODEL=gemini-3.5-flash-lite" `
  --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,LANGSMITH_API_KEY=LANGSMITH_API_KEY:latest,GEOAPIFY_API_KEY=GEOAPIFY_API_KEY:latest,GOOGLE_PLACES_API_KEY=GOOGLE_PLACES_API_KEY:latest,SERPAPI_API_KEY=SERPAPI_API_KEY:latest,SERPER_API_KEY=SERPER_API_KEY:latest,RAILRADAR_API_KEY=RAILRADAR_API_KEY:latest"
```

### This command is the normal backend "rebuild + redeploy"

Because it uses:

```text
--source .
```

the source is rebuilt and deployed through the configured Google Cloud build/deployment flow.

Operationally:

```text
Local source
    ↓
Cloud Build
    ↓
Docker image
    ↓
Artifact Registry
    ↓
new Cloud Run revision
    ↓
traffic to deployed revision
```

---

# 31. Cloud Run — Rebuild After Backend Code Change

When changing:

```text
backend/agents.py
backend/tools.py
backend/chat_helper.py
backend/firebase.py
backend/main.py
Dockerfile
requirements.txt
```

run:

```powershell
cd <PROJECT_ROOT>
```

then:

```powershell
gcloud run deploy voyageai-backend `
  --source . `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --service-account="voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" `
  --allow-unauthenticated `
  --set-env-vars="LANGSMITH_TRACING=true,LANGSMITH_PROJECT=VoyageAI,GEMINI_MODEL=gemini-3.5-flash-lite" `
  --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,LANGSMITH_API_KEY=LANGSMITH_API_KEY:latest,GEOAPIFY_API_KEY=GEOAPIFY_API_KEY:latest,GOOGLE_PLACES_API_KEY=GOOGLE_PLACES_API_KEY:latest,SERPAPI_API_KEY=SERPAPI_API_KEY:latest,SERPER_API_KEY=SERPER_API_KEY:latest,RAILRADAR_API_KEY=RAILRADAR_API_KEY:latest"
```

Then verify:

```powershell
gcloud run services describe voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1
```

---

# 32. Cloud Run — Frontend-Only Change

If only React code changed:

```powershell
cd frontend/ai-tour-planner-react
npm run build
firebase deploy --only hosting
```

You do **not** need to rebuild Cloud Run just because React changed.

---

# 33. Cloud Run — Full-Stack Change

If both frontend and backend changed:

```powershell
cd frontend/ai-tour-planner-react
npm run build
firebase deploy --only hosting
```

then:

```powershell
cd <PROJECT_ROOT>
gcloud run deploy voyageai-backend `
  --source . `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --service-account="voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" `
  --allow-unauthenticated `
  --set-env-vars="LANGSMITH_TRACING=true,LANGSMITH_PROJECT=VoyageAI,GEMINI_MODEL=gemini-3.5-flash-lite" `
  --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,LANGSMITH_API_KEY=LANGSMITH_API_KEY:latest,GEOAPIFY_API_KEY=GEOAPIFY_API_KEY:latest,GOOGLE_PLACES_API_KEY=GOOGLE_PLACES_API_KEY:latest,SERPAPI_API_KEY=SERPAPI_API_KEY:latest,SERPER_API_KEY=SERPER_API_KEY:latest,RAILRADAR_API_KEY=RAILRADAR_API_KEY:latest"
```

---

# 34. Cloud Run — Service Inspection Commands

## List services

```powershell
gcloud run services list --project=voyageai-161299 --region=asia-south1
```

## Describe service

```powershell
gcloud run services describe voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1
```

## List revisions

```powershell
gcloud run revisions list `
  --service=voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1
```

## Show service URL

```powershell
gcloud run services describe voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --format="value(status.url)"
```

---

# 35. Cloud Run — Logs

Read recent logs:

```powershell
gcloud run services logs read voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --limit=100
```

Useful search terms:

```text
ERROR
Traceback
5xx
REQUEST COMPLETED
TOOL CALL
```

The application logs use messages such as:

```text
[TourPlanner] NEW USER REQUEST
[TourPlanner] ...
[TourPlanner] REQUEST COMPLETED
```

Logs are usually the quickest way to inspect a single failing request.

---

# 36. Cloud Run — Scaling Controls

Current maximum instance setting:

```text
3
```

Command:

```powershell
gcloud run services update voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --max=3
```

This is an instance-scaling limit, not a three-user or three-request limit.

To inspect the service after changing scaling:

```powershell
gcloud run services describe voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1
```

---

# 37. Cloud Run — Rollback

First list revisions:

```powershell
gcloud run revisions list `
  --service=voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1
```

To send 100% of traffic to a known good revision:

```powershell
gcloud run services update-traffic voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --to-revisions=<REVISION_NAME>=100
```

To return traffic to the latest revision:

```powershell
gcloud run services update-traffic voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --to-latest
```

Cloud Run's current rollback documentation uses `gcloud run services update-traffic` for revision-based rollbacks.

---

# 38. Optional Manual Docker/Image Deployment

The canonical VoyageAI deployment uses source deployment. A manual image pipeline is useful when you want explicit control over the image tag.

Conceptual flow:

```text
Dockerfile
   ↓
docker build
   ↓
Artifact Registry
   ↓
Cloud Run --image
```

Example pattern:

```powershell
docker build -t <REGION>-docker.pkg.dev/voyageai-161299/<REPOSITORY>/voyageai-backend:<TAG> .
```

Authenticate Docker to Artifact Registry when required:

```powershell
gcloud auth configure-docker <REGION>-docker.pkg.dev
```

Push:

```powershell
docker push <REGION>-docker.pkg.dev/voyageai-161299/<REPOSITORY>/voyageai-backend:<TAG>
```

Deploy that image:

```powershell
gcloud run deploy voyageai-backend `
  --image=<REGION>-docker.pkg.dev/voyageai-161299/<REPOSITORY>/voyageai-backend:<TAG> `
  --project=voyageai-161299 `
  --region=asia-south1
```

This is an alternative deployment strategy, not the current primary VoyageAI path.

---

# 39. Cloud Run — Destructive Commands

Delete service:

```powershell
gcloud run services delete voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1
```

This is destructive. Do not use it for a normal redeploy.

---

# 40. Artifact Registry Operations

List repositories:

```powershell
gcloud artifacts repositories list --project=voyageai-161299
```

List images in a known repository:

```powershell
gcloud artifacts docker images list <REGION>-docker.pkg.dev/voyageai-161299/<REPOSITORY>
```

Describe repository:

```powershell
gcloud artifacts repositories describe <REPOSITORY> `
  --location=<REGION> `
  --project=voyageai-161299
```

Do not delete an image/repository unless you understand which Cloud Run revisions depend on it.

---

# 41. Production URLs

Current frontend:

```text
https://voyageai-702fe.web.app
```

Current backend:

```text
https://voyageai-backend-571503113205.asia-south1.run.app
```

FastAPI docs:

```text
https://voyageai-backend-571503113205.asia-south1.run.app/docs
```

---

# 42. End-to-End Production Verification

## Backend

Open:

```text
<BACKEND_URL>/docs
```

Expected result:

```text
FastAPI Swagger UI
```

## Frontend

Open:

```text
<HOSTING_URL>
```

## Authentication

```text
Google Sign-In
```

## Session APIs

After login, verify:

```text
GET /sessions → 200
```

## Chat

Send a simple request and verify:

```text
POST /chat → 200
```

## Persistence

Refresh the page and verify:

```text
session remains visible
messages remain visible
```

## Delete

Delete a test chat and verify:

```text
session removed
messages removed
```

## Observability

Confirm:

```text
Cloud Run log entry
LangSmith trace
Firestore writes
```

---

# 43. LangSmith Observability

The backend is configured for LangSmith tracing.

Environment configuration:

```env
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=VoyageAI
LANGSMITH_API_KEY=<secret>
```

LangSmith helps inspect:

```text
LLM calls
tool calls
latency
agent flow
errors
token usage
```

One recorded example from development showed a trace around:

```text
17.37 seconds
32.3K tokens
estimated cost around $0.0132
```

Treat this as a development observation for a particular run, not as a fixed cost for every request.

Known optimization area:

```text
Repeated train searches
Repeated hotel searches
Repeated Places searches
Large final model context
```

---

# 44. Token and Tool Efficiency

VoyageAI is intentionally designed to control tool usage.

## Why

External APIs may be slow and some are billable.

Excessive agent exploration causes:

```text
higher latency
higher token usage
higher API usage
higher cloud cost
less deterministic behavior
```

## Current approach

```text
focused agent architecture
+ dedicated tools
+ tool-call budget
+ stop when sufficient evidence exists
```

The weather specialist is retained because weather is a high-value planning input. A separate train specialist was removed because the Main Agent can coordinate the compact train tool interface directly.

---

# 45. Common Deployment Workflows

## Workflow A — Only `tools.py` changed

```powershell
cd <PROJECT_ROOT>
gcloud run deploy voyageai-backend `
  --source . `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --service-account="voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" `
  --allow-unauthenticated `
  --set-env-vars="LANGSMITH_TRACING=true,LANGSMITH_PROJECT=VoyageAI,GEMINI_MODEL=gemini-3.5-flash-lite" `
  --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,LANGSMITH_API_KEY=LANGSMITH_API_KEY:latest,GEOAPIFY_API_KEY=GEOAPIFY_API_KEY:latest,GOOGLE_PLACES_API_KEY=GOOGLE_PLACES_API_KEY:latest,SERPAPI_API_KEY=SERPAPI_API_KEY:latest,SERPER_API_KEY=SERPER_API_KEY:latest,RAILRADAR_API_KEY=RAILRADAR_API_KEY:latest"
```

## Workflow B — Only React changed

```powershell
cd frontend/ai-tour-planner-react
npm run build
firebase deploy --only hosting
```

## Workflow C — `backend/main.py` CORS changed

```text
Change main.py
   ↓
Cloud Run source deploy
   ↓
new revision
   ↓
test production frontend
```

## Workflow D — Secret value changed

1. Add new Secret Manager version.
2. Keep Cloud Run configured to use `:latest` when that is your chosen policy.
3. Redeploy/reconfigure the service when needed so the new runtime configuration is applied according to the deployment design.
4. Test the affected tool.

## Workflow E — `requirements.txt` changed

```text
Update requirements.txt
        ↓
Cloud Run source deploy
        ↓
Cloud Build rebuild
        ↓
new image/revision
```

---

# 46. Troubleshooting

## 46.1 Backend returns 500

Read logs:

```powershell
gcloud run services logs read voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --limit=100
```

Look for the first application traceback, not only the final HTTP 500 line.

## 46.2 Backend returns 401

Possible causes:

```text
Firebase user is signed out
ID token missing
ID token invalid/expired
frontend connected to wrong Firebase project
backend verifying another Firebase project
```

Inspect the browser Network tab and confirm:

```text
Authorization: Bearer <Firebase ID token>
```

Do not replace this with a LangSmith/API secret.

## 46.3 Backend returns 403

The session likely belongs to another Firebase UID.

The ownership check is intentional.

## 46.4 CORS error

Check `backend/main.py` includes the deployed Hosting origin.

After modifying CORS:

```powershell
gcloud run deploy voyageai-backend --source . ...
```

## 46.5 Frontend still calls localhost

Check:

```text
frontend/ai-tour-planner-react/.env
```

Production value should be:

```env
VITE_API_URL=https://<CLOUD_RUN_URL>
```

Then:

```powershell
npm run build
firebase deploy --only hosting
```

## 46.6 Old frontend still appears

Try:

```text
Ctrl + Shift + R
```

or an Incognito window.

## 46.7 Firebase Hosting prompts to overwrite `dist/index.html`

For a Vite React app, keep the generated build output and answer the initialization prompt so the existing build is not replaced.

## 46.8 Firestore session list is empty

Check:

```text
Firebase account
Firebase UID
backend project
Firestore project
```

Remember that historical MySQL chat records were not automatically migrated to Firestore.

## 46.9 Secret value contains CR/LF

A malformed secret can create an HTTP header error such as:

```text
Invalid leading whitespace, reserved character(s), or return character(s) in header value
```

Store a clean secret version using a file written without a trailing newline, as described in the Secret Manager section.

## 46.10 Cloud Run deployment fails before the container starts

Check:

```text
Cloud Build permissions
Artifact Registry API
Cloud Run API
Secret Manager API
runtime service account
```

Then inspect Cloud Build/Cloud Run error details.

---

# 47. Testing Commands

## Backend import check

```powershell
python -c "import backend.main; print('backend import OK')"
```

## Run train tests

```powershell
python -m pytest backend/test_train_tools.py -v -s
```

## Start local backend

```powershell
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

## Start frontend

```powershell
cd frontend/ai-tour-planner-react
npm run dev
```

## Frontend production build check

```powershell
npm run build
```

---

# 48. Complete Command Cheat Sheet

## Google Cloud

```powershell
gcloud auth login
gcloud auth list
gcloud config set project voyageai-161299
gcloud config get-value project
gcloud projects describe voyageai-161299 --format="value(projectNumber)"
gcloud services list --enabled --project=voyageai-161299
gcloud run services list --project=voyageai-161299 --region=asia-south1
gcloud run revisions list --service=voyageai-backend --project=voyageai-161299 --region=asia-south1
gcloud run services describe voyageai-backend --project=voyageai-161299 --region=asia-south1
gcloud run services logs read voyageai-backend --project=voyageai-161299 --region=asia-south1 --limit=100
gcloud run services update voyageai-backend --project=voyageai-161299 --region=asia-south1 --max=3
gcloud run services update-traffic voyageai-backend --project=voyageai-161299 --region=asia-south1 --to-latest
```

## Backend deployment

```powershell
gcloud run deploy voyageai-backend --source . --project=voyageai-161299 --region=asia-south1 --service-account="voyageai-cloud-run@voyageai-161299.iam.gserviceaccount.com" --allow-unauthenticated --set-env-vars="LANGSMITH_TRACING=true,LANGSMITH_PROJECT=VoyageAI,GEMINI_MODEL=gemini-3.5-flash-lite" --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,LANGSMITH_API_KEY=LANGSMITH_API_KEY:latest,GEOAPIFY_API_KEY=GEOAPIFY_API_KEY:latest,GOOGLE_PLACES_API_KEY=GOOGLE_PLACES_API_KEY:latest,SERPAPI_API_KEY=SERPAPI_API_KEY:latest,SERPER_API_KEY=SERPER_API_KEY:latest,RAILRADAR_API_KEY=RAILRADAR_API_KEY:latest"
```

## Firebase

```powershell
firebase --version
firebase login
firebase projects:list
firebase use --add
firebase use <PROJECT_ID>
firebase init hosting
firebase init firestore
firebase deploy --only hosting
firebase deploy --only firestore
firebase deploy --only hosting,firestore
firebase deploy
firebase firestore:indexes
firebase hosting:sites:list
firebase hosting:channel:deploy <CHANNEL_ID>
```

## React

```powershell
cd frontend/ai-tour-planner-react
npm install
npm run dev
npm run build
```

## Backend local

```powershell
cd <PROJECT_ROOT>
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

---

# 49. Security Rules

Never commit:

```text
.env
service-account JSON
API keys
private keys
credential files
Firebase Admin private credentials
```

Recommended `.gitignore` entries:

```gitignore
.env
.env.*
!.env.example

*.json
```

If you need to commit a non-sensitive JSON configuration file, use a more specific ignore rule instead of ignoring every JSON file.

For the Firebase Admin service account, prefer an explicit rule such as:

```gitignore
backend/*firebase-adminsdk*.json
```

Also avoid committing:

```text
node_modules/
dist/
.venv/
__pycache__/
*.pyc
```

---

# 50. Suggested Repository `.env.example`

A public repository can include a template such as:

```env
GEMINI_MODEL=gemini-3.5-flash-lite
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=VoyageAI

GOOGLE_API_KEY=
LANGSMITH_API_KEY=
GEOAPIFY_API_KEY=
GOOGLE_PLACES_API_KEY=
SERPAPI_API_KEY=
SERPER_API_KEY=
RAILRADAR_API_KEY=
```

The actual `.env` remains local and private.

---

# 51. Why MySQL Was Removed

The early project used MySQL/Cloud SQL for persistence. The current version uses Firestore.

Historical path:

```text
React
 ↓
FastAPI
 ↓
SQLAlchemy
 ↓
MySQL / Cloud SQL
```

Current path:

```text
React
 ↓
FastAPI
 ↓
Firebase Admin SDK
 ↓
Firestore
```

Reasons for the migration in this project included cost control and simpler serverless persistence.

The MySQL modules remain historical/legacy unless deliberately reactivated.

---

# 52. Cost-Control Architecture

Current cost-conscious choices include:

```text
Firebase Spark plan
Cloud Run min instances = 0
Cloud Run max instances = 3
Limited agent tool calls
Small model where practical
One focused Weather Agent
No separate Train Agent
Persistent Firestore instead of Cloud SQL
```

The project also has a configured Cloud Run spend/budget safeguard. Cloud billing controls should always be verified against current Google Cloud behavior and plan limits.

---

# 53. Billing, Budgets and Cost Protection

The project was configured with a cost-control target for Cloud Run and a maximum of 3 Cloud Run instances. The exact billing UI and spend-cap behavior can change over time, so the Console should remain the source of truth for the current account-level billing configuration.

## Cloud Run scaling

```powershell
gcloud run services update voyageai-backend `
  --project=voyageai-161299 `
  --region=asia-south1 `
  --max=3
```

## Where to inspect costs

```text
Google Cloud Console
→ Billing
→ Reports

Google Cloud Console
→ Billing
→ Budgets & alerts

Firebase Console
→ Usage / Billing
```

Also remember that Gemini/API-provider usage can be billed separately from Cloud Run if those services use a different Google Cloud project or external provider account.

---

# 54. Monitoring

## Cloud Run Metrics

Path:

```text
Google Cloud Console
→ Cloud Run
→ voyageai-backend
→ Metrics
```

Useful metrics:

```text
Request count
2xx / 4xx / 5xx
Latency
Instance count
Billable instance time
```

Metrics dashboards can have reporting delay, so use logs to investigate an individual request.

## Cloud Logging

Path:

```text
Cloud Run
→ voyageai-backend
→ Logs
```

## Billing

Path:

```text
Google Cloud Console
→ Billing
→ Reports
```

Check both infrastructure spend and external API/model usage.

---

# 55. Production State Snapshot

Current architecture:

```text
React frontend                 ✅
Firebase Hosting               ✅
Google Authentication          ✅
Firestore                      ✅
FastAPI backend                ✅
Docker                         ✅
Cloud Build                    ✅
Artifact Registry              ✅
Cloud Run                      ✅
Secret Manager                 ✅
LangSmith                      ✅
CORS                           ✅
Persistent chat                ✅
```

Current Cloud Run configuration includes:

```text
Region: asia-south1
Service: voyageai-backend
Max instances: 3
Min instances: 0
```

---

# 56. Development-to-Production Diagram

```text
Developer edits code
        │
        ├───────────────────────────────┐
        │                               │
        ▼                               ▼
backend/*.py                     frontend/src/*
        │                               │
        ▼                               ▼
local FastAPI                  npm run build
        │                               │
        │                               ▼
        │                      frontend/dist/
        │                               │
        │                               ▼
        │                      Firebase Hosting
        │
        ▼
gcloud run deploy --source .
        │
        ▼
Cloud Build
        │
        ▼
Docker image
        │
        ▼
Artifact Registry
        │
        ▼
Cloud Run revision
        │
        ▼
Production FastAPI
```

---

# 57. Important Engineering Principles

## 56.1 Do not hallucinate travel facts

Never invent:

```text
prices
availability
hotel amenities
ratings
train schedules
flight schedules
URLs
distance
travel time
weather observations
```

unless clearly identified as a planner estimate rather than a retrieved fact.

## 56.2 Preserve user constraints

```text
Exact dates → fixed
Budget → fixed unless user changes it
Destination → fixed unless user changes it
Transport preference → respected
Duration → do not invent
```

## 56.3 Ask when an important choice is missing

Examples:

```text
No destination
No duration
No travel period
No origin for a requested flight
```

Do not silently create an arbitrary itinerary.

## 56.4 Use dedicated tools first

```text
Weather question → weather tool
Places → Places tool
Route → route tool
Flight → flight tool
Hotel → hotel tool
Train → train tool
```

Generic web search is the fallback.

---

# 58. Architecture Decisions and Their Reasons

| Decision | Reason in this project |
|---|---|
| React + Firebase Hosting | Static frontend deployment with simple hosting workflow |
| FastAPI + Cloud Run | Containerized Python API with scaling-to-zero behavior |
| Firestore | Serverless persistent chat/session store |
| Firebase Auth | Simple Google sign-in and UID-based identity |
| Gemini | Main language model |
| LangGraph | Explicit workflow/state routing |
| deepagents | Tool-using agent behavior and subagent capability |
| Dedicated Weather Agent | Weather has direct impact on date/activity planning |
| No separate Train Agent | Reduces duplicated model/tool calls |
| Secret Manager | Keeps server-side API keys outside source code |
| LangSmith | Traceability and token/tool observability |
| Tool-call budget | Cost and latency control |
| Source-based Cloud Run deployment | One command for rebuild + redeploy |

---

# 59. Resume/Portfolio Description

A concise project description:

> **VoyageAI — AI Tour Planner:** Built a full-stack agentic travel-planning platform using React, FastAPI, Google Gemini, LangGraph/deepagents, Firebase Authentication, Firestore, real travel APIs, Docker, Google Cloud Run, Secret Manager, Firebase Hosting, and LangSmith. Designed a tool-using planner that combines weather, places, routes, flights, hotels, and trains while preserving user constraints, persistent conversation history, authentication, observability, and cloud deployment.

---

# 60. Public Repository Checklist

Before pushing the project to GitHub:

```text
[ ] .env is ignored
[ ] Firebase Admin service-account JSON is ignored
[ ] No API key appears in source code
[ ] No API key appears in README
[ ] No access token appears in logs/README
[ ] No password appears in README
[ ] Local personal Windows path removed from README
[ ] Personal email removed from public README unless intentionally published
[ ] dist/ handling is intentional
[ ] node_modules/ ignored
[ ] .venv/ ignored
[ ] README contains setup steps but no secrets
```

Project IDs and public service URLs are generally identifiers rather than secret credentials, but they can still be replaced with placeholders in a public README when desired.

---

# 61. Deployment Checklist

## Backend

```text
[ ] requirements.txt updated
[ ] Dockerfile valid
[ ] backend imports locally
[ ] Firebase Admin works
[ ] secrets exist
[ ] secret versions are correct
[ ] Cloud Run service account exists
[ ] Firestore IAM exists
[ ] Secret Manager IAM exists
[ ] CORS includes frontend origin
[ ] gcloud run deploy succeeds
[ ] /docs loads
[ ] production logs show healthy requests
```

## Frontend

```text
[ ] VITE_API_URL is correct
[ ] npm install succeeds
[ ] npm run build succeeds
[ ] dist/index.html exists
[ ] Firebase project is correct
[ ] Hosting is initialized
[ ] SPA rewrite is configured
[ ] firebase deploy --only hosting succeeds
[ ] deployed site loads
[ ] Google Sign-In works
```

## Firestore

```text
[ ] Firestore database exists
[ ] correct Firebase project selected
[ ] Cloud Run service account has Firestore access
[ ] session ownership logic works
[ ] messages persist
[ ] delete works
[ ] required indexes exist if the query requires them
```

---

# 62. Official Documentation References

Google Cloud Run:

- https://cloud.google.com/run/docs
- https://cloud.google.com/run/docs/deploying-source-code
- https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration

Firebase Hosting:

- https://firebase.google.com/docs/hosting/quickstart
- https://firebase.google.com/docs/hosting/test-preview-deploy

Firebase CLI:

- https://firebase.google.com/docs/cli

Cloud Firestore indexes:

- https://firebase.google.com/docs/reference/firestore/indexes

Firebase Authentication:

- https://firebase.google.com/docs/auth

---

# 63. Final Command Workflows to Memorize

## Backend changed

```text
edit backend
   ↓
gcloud run deploy voyageai-backend --source . ...
   ↓
check logs
   ↓
check /docs
   ↓
test frontend
```

## Frontend changed

```text
edit React
   ↓
npm run build
   ↓
firebase deploy --only hosting
   ↓
refresh site
```

## Firestore rules/indexes changed

```text
edit firestore.rules / firestore.indexes.json
   ↓
firebase deploy --only firestore
   ↓
verify Firebase Console / indexes
```

## Full release

```text
backend changes
   ↓
Cloud Run deploy
   ↓
frontend build
   ↓
Firebase Hosting deploy
   ↓
production verification
   ↓
Cloud Run logs + LangSmith + Firestore verification
```

---

# 64. Current Production Mental Model

When debugging VoyageAI, think in layers:

```text
LAYER 1 — Browser
React / Firebase Web SDK

LAYER 2 — Authentication
Firebase Auth / ID token

LAYER 3 — API
FastAPI / CORS / token verification

LAYER 4 — Agent
agents.py / LangGraph / deepagents / Gemini

LAYER 5 — Tools
travel APIs in tools.py

LAYER 6 — Persistence
Firestore via chat_helper.py / firebase.py

LAYER 7 — Infrastructure
Docker / Cloud Build / Artifact Registry / Cloud Run

LAYER 8 — Secrets
Secret Manager

LAYER 9 — Observability
LangSmith / Cloud Logging / Cloud Monitoring
```

This layered model should be used when diagnosing failures so that an authentication problem is not mistaken for an agent problem, or an API/tool error is not mistaken for a Cloud Run deployment error.

---

# 65. Maintenance Note

This README is a project-specific reference built from the current VoyageAI deployment architecture and the documented commands used for the project.

Google Cloud and Firebase CLI syntax, IAM requirements, pricing, quotas, billing behavior, and product capabilities can change. Before reproducing infrastructure months later, verify the current official Google/Firebase documentation for the specific command or configuration.

