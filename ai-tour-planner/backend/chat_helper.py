import os
from dataclasses import dataclass
from datetime import datetime, timezone

from dotenv import load_dotenv
from google.cloud.firestore_v1.base_query import FieldFilter
from langchain_google_genai import ChatGoogleGenerativeAI

from .firebase import db as firestore_db

load_dotenv()


title_model = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
)


@dataclass
class ChatSessionRecord:
    id: str
    title: str
    user_id: str
    created_at: datetime
    updated_at: datetime


@dataclass
class MessageRecord:
    id: str
    session_id: str
    user_id: str
    role: str
    content: str
    created_at: datetime


def _now():
    return datetime.now(timezone.utc)


def _session_ref(session_id):
    return firestore_db.collection("chat_sessions").document(session_id)


def _message_collection():
    return firestore_db.collection("messages")


def generate_session_name(message):
    prompt = f"""
Generate a short chat title from this travel request.

User message:
{message}

Rules:
- 2 to 5 words
- No quotes
- No emojis
- Return only the title
"""

    result = title_model.invoke(prompt)
    content = getattr(result, "content", result)

    if isinstance(content, list):
        content = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )

    title = str(content).strip()

    return title or "New Chat"


def create_session(_db, session_id, user_id, first_message):
    now = _now()

    data = {
        "user_id": user_id,
        "title": "New Chat",
        "created_at": now,
        "updated_at": now,
    }

    _session_ref(session_id).set(data)

    return ChatSessionRecord(
        id=session_id,
        title=data["title"],
        user_id=user_id,
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def get_session(_db, session_id, user_id):
    ref = _session_ref(session_id)
    snapshot = ref.get()

    if not snapshot.exists:
        return None

    data = snapshot.to_dict()

    if data.get("user_id") != user_id:
        raise PermissionError("You do not have access to this session")

    return ChatSessionRecord(
        id=snapshot.id,
        title=data.get("title", "New Chat"),
        user_id=data.get("user_id"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )


def get_or_create_session(_db, session_id, user_id, first_message):
    session = get_session(
        _db,
        session_id,
        user_id,
    )

    if session:
        return session

    return create_session(
        _db,
        session_id,
        user_id,
        first_message,
    )


def save_message(_db, session_id, user_id, role, content):
    session = get_session(
        _db,
        session_id,
        user_id,
    )

    if not session:
        raise PermissionError("Session not found")

    now = _now()

    _message_collection().document().set(
        {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": now,
        }
    )

    _session_ref(session_id).update(
        {
            "updated_at": now,
        }
    )


def get_recent_chat(_db, session_id, user_id, turns=3):
    session = get_session(
        _db,
        session_id,
        user_id,
    )

    if not session:
        return []

    query = _message_collection().where(
        filter=FieldFilter(
            "session_id",
            "==",
            session_id,
        )
    )

    messages = []

    for doc in query.stream():
        data = doc.to_dict()

        if data.get("user_id") != user_id:
            continue

        if data.get("role") not in {"user", "assistant"}:
            continue

        messages.append(
            {
                "role": data.get("role"),
                "content": data.get("content", ""),
                "created_at": data.get("created_at"),
            }
        )

    messages.sort(
        key=lambda x: x.get("created_at")
        or datetime.min.replace(tzinfo=timezone.utc)
    )

    return [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in messages[-(turns * 2):]
    ]


def get_session_messages(_db, session_id, user_id):
    session = get_session(
        _db,
        session_id,
        user_id,
    )

    if not session:
        return []

    query = _message_collection().where(
        filter=FieldFilter(
            "session_id",
            "==",
            session_id,
        )
    )

    messages = []

    for doc in query.stream():
        data = doc.to_dict()

        if data.get("user_id") != user_id:
            continue

        messages.append(
            MessageRecord(
                id=doc.id,
                session_id=session_id,
                user_id=user_id,
                role=data.get("role"),
                content=data.get("content", ""),
                created_at=data.get("created_at"),
            )
        )

    messages.sort(key=lambda x: x.created_at)

    return messages


def get_all_sessions(_db, user_id):
    query = firestore_db.collection("chat_sessions").where(
        filter=FieldFilter(
            "user_id",
            "==",
            user_id,
        )
    )

    sessions = []

    for doc in query.stream():
        data = doc.to_dict()

        sessions.append(
            ChatSessionRecord(
                id=doc.id,
                title=data.get("title", "New Chat"),
                user_id=data.get("user_id"),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
            )
        )

    sessions.sort(
        key=lambda x: x.updated_at
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return sessions


def maybe_generate_session_title(session_id, user_id):
    session = get_session(
        None,
        session_id,
        user_id,
    )

    if not session:
        return None

    if session.title != "New Chat":
        return None

    messages = get_session_messages(
        None,
        session_id,
        user_id,
    )

    user_messages = [
        message.content
        for message in messages
        if message.role == "user"
    ]

    if len(user_messages) < 3:
        return None

    last_three = user_messages[-3:]

    prompt = f"""
Generate a short title for this travel planning conversation.

User messages:
1. {last_three[0]}
2. {last_three[1]}
3. {last_three[2]}

Rules:
- 2 to 5 words
- Concise
- Describe the overall travel topic
- No quotes
- No explanation
"""

    result = title_model.invoke(prompt)
    content = getattr(result, "content", result)

    if isinstance(content, list):
        content = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )

    title = str(content).strip()

    if not title:
        return None

    _session_ref(session_id).update(
        {
            "title": title,
        }
    )

    return title


def delete_session(_db, session_id, user_id):
    session_ref = _session_ref(session_id)

    session = get_session(
        _db,
        session_id,
        user_id,
    )

    if not session:
        return False

    query = _message_collection().where(
        filter=FieldFilter(
            "session_id",
            "==",
            session_id,
        )
    )

    batch = firestore_db.batch()
    count = 0

    for doc in query.stream():
        data = doc.to_dict()

        if data.get("user_id") != user_id:
            continue

        batch.delete(doc.reference)
        count += 1

        if count == 500:
            batch.commit()
            batch = firestore_db.batch()
            count = 0

    if count:
        batch.commit()

    session_ref.delete()

    return True