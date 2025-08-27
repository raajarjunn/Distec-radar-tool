from pymongo import MongoClient
from datetime import datetime, timezone

client = MongoClient("mongodb://localhost:27017/")
db = client["tech_tool_db"]
activities = db["activities"]

def log_activity(*, username: str, activity: str, logged_in: bool, meta: dict | None = None):
    activities.insert_one({
        "activity": activity,
        "username": username or "anonymous",
        "occurred_at": datetime.now(tz=timezone.utc),
        "logged_in": bool(logged_in),
        "meta": meta or {},
    })