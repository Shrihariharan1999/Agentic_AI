import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


BASE_DIR = Path(__file__).resolve().parent

CREDENTIALS_FILE = (
    BASE_DIR
    / "voyageai-702fe-firebase-adminsdk-fbsvc-741fb3008d.json"
)

FIREBASE_PROJECT_ID = os.getenv(
    "FIREBASE_PROJECT_ID",
    "voyageai-702fe",
)


if not firebase_admin._apps:
    if os.getenv("K_SERVICE"):
        firebase_admin.initialize_app(
            options={
                "projectId": FIREBASE_PROJECT_ID,
            }
        )

    elif CREDENTIALS_FILE.exists():
        cred = credentials.Certificate(
            str(CREDENTIALS_FILE)
        )

        firebase_admin.initialize_app(
            cred,
            options={
                "projectId": FIREBASE_PROJECT_ID,
            }
        )

    else:
        firebase_admin.initialize_app(
            options={
                "projectId": FIREBASE_PROJECT_ID,
            }
        )


db = firestore.client()