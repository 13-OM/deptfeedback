import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-key")
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() == "true"
    DEPARTMENT_NAME = os.getenv("DEPARTMENT_NAME", "Computer Engineering")
