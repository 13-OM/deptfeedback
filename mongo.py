import os
from datetime import datetime, timezone
from functools import lru_cache
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

_client = None
_db = None


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGO_URI is not configured. Add it to .env or Render Environment Variables.")
        _client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        db_name = os.getenv("MONGO_DB_NAME", "deptfeedback")
        _db = _client[db_name]
        _ensure_indexes(_db)
    return _db


def _ensure_indexes(db):
    db.users.create_index([("username", ASCENDING), ("role", ASCENDING)], unique=True)
    db.students.create_index("enrollment_no", unique=True)
    db.faculty.create_index("faculty_code", unique=True)
    db.subjects.create_index([("subject_code", ASCENDING), ("semester", ASCENDING), ("academic_year", ASCENDING)], unique=True)
    db.feedback_forms.create_index([("subject_id", ASCENDING), ("academic_year", ASCENDING)], unique=True)
    db.feedback_responses.create_index("anonymous_reference", unique=True)
    db.feedback_answers.create_index([("response_id", ASCENDING), ("question_id", ASCENDING)], unique=True)
    db.submission_tracking.create_index([("student_id", ASCENDING), ("feedback_form_id", ASCENDING)], unique=True)


def next_id(collection):
    doc = get_db().counters.find_one_and_update(
        {"_id": collection}, {"$inc": {"value": 1}}, upsert=True, return_document=True
    )
    return int(doc["value"])


def oid(value):
    try:
        return ObjectId(value)
    except Exception:
        return None
