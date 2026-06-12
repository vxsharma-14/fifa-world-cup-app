"""Application configurations and idempotent database connection setup."""

import json
from types import SimpleNamespace
import firebase_admin
from firebase_admin import credentials
import streamlit as st

CONFIG = SimpleNamespace(
    DATABASE_URL="https://fifa-world-cup-apsj-default-rtdb.firebaseio.com/",  # Replace with actual URL
    ADMIN_EMAIL="admin@fifafantasy.com"
)

def initialize_db() -> None:
    """Initializes the Firebase Admin SDK securely using Streamlit secrets."""
    if not firebase_admin._apps:
        try:
            creds_dict = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred, {
                'databaseURL': CONFIG.DATABASE_URL
            })
        except KeyError:
            st.error("Critical Error: 'firebase_json' missing from Streamlit secrets.")