from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from pydantic import BaseModel

from . import firebase
from .agents import run_tour_agent
from .chat_helper import (
    delete_session,
    get_all_sessions,
    get_or_create_session,
    get_recent_chat,
    get_session_messages,
    maybe_generate_session_title,
    save_message,
)

app = FastAPI(title="VoyageAI")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://voyageai-702fe.web.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    try:
        decoded_token = auth.verify_id_token(
            credentials.credentials
        )

        return decoded_token["uid"]

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token",
        )


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/chat")
def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    try:
        session = get_or_create_session(
            None,
            request.session_id,
            user_id,
            request.message,
        )

        history = get_recent_chat(
            None,
            request.session_id,
            user_id,
            turns=3,
        )

        save_message(
            None,
            request.session_id,
            user_id,
            "user",
            request.message,
        )

        title = maybe_generate_session_title(
            request.session_id,
            user_id,
        )

        result = run_tour_agent(
            message=request.message,
            chat_history=history,
            thread_id=request.session_id,
            max_tool_calls=15,
        )

        save_message(
            None,
            request.session_id,
            user_id,
            "assistant",
            result["response"],
        )

        return {
            "session_id": request.session_id,
            "session_name": title or session.title,
            "response": result["response"],
        }

    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this session",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@app.get("/sessions")
def sessions(
    user_id: str = Depends(get_current_user),
):
    session_records = get_all_sessions(
        None,
        user_id,
    )

    return {
        "sessions": [
            {
                "id": session.id,
                "name": session.title,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
            for session in session_records
        ]
    }


@app.get("/sessions/{session_id}/messages")
def session_messages(
    session_id: str,
    user_id: str = Depends(get_current_user),
):
    try:
        messages = get_session_messages(
            None,
            session_id,
            user_id,
        )

    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this session",
        )

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


@app.delete("/sessions/{session_id}")
def remove_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
):
    try:
        deleted = delete_session(
            None,
            session_id,
            user_id,
        )

    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this session",
        )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    return {
        "success": True,
        "session_id": session_id,
    }