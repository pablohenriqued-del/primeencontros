import os
import time
import secrets
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stupefied-gauss-5.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def test_user(mongo_db):
    """Insert a fake user + session token directly into Mongo."""
    user_id = f"user_qa_{secrets.token_hex(5)}"
    token = f"test_token_{int(time.time()*1000)}_{secrets.token_hex(4)}"
    email = f"qa+{int(time.time()*1000)}@oasisrio.test"
    mongo_db.users.insert_one({
        "user_id": user_id, "email": email, "name": "QA Tester",
        "picture": "https://i.pravatar.cc/150", "created_at": "2026-01-01T00:00:00+00:00",
    })
    # store expires_at as ISO string to match backend's auth_session behavior
    from datetime import datetime, timezone, timedelta
    mongo_db.user_sessions.insert_one({
        "user_id": user_id, "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"user_id": user_id, "email": email, "token": token}
    # Teardown
    mongo_db.user_sessions.delete_many({"user_id": user_id})
    mongo_db.users.delete_many({"user_id": user_id})
    mongo_db.bookings.delete_many({"user_id": user_id})
    mongo_db.payment_transactions.delete_many({"user_id": user_id})


@pytest.fixture(scope="session")
def auth_client(api_client, test_user):
    api_client.headers.update({"Authorization": f"Bearer {test_user['token']}"})
    return api_client
