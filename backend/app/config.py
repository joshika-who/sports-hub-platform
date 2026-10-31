import os
import tempfile
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_serverless_or_readonly() -> bool:
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return True
    test_dir = os.path.dirname(os.path.dirname(__file__))
    return not os.access(test_dir, os.W_OK)


_USE_TMP = _is_serverless_or_readonly()
_TMP_ROOT = tempfile.gettempdir()
_DEFAULT_SQLITE_PATH = (
    os.path.join(_TMP_ROOT, "sportshub.db").replace("\\", "/")
    if _USE_TMP
    else "./sportshub.db"
)
_DEFAULT_UPLOAD_DIR = (
    os.path.join(_TMP_ROOT, "sportshub_uploads")
    if _USE_TMP
    else os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
)
_DEFAULT_CHROMA_DIR = (
    os.path.join(_TMP_ROOT, "sportshub_chroma")
    if _USE_TMP
    else os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_data")
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App & Auth
    APP_NAME: str = "Sports Hub Platform API"
    APP_ENV: str = "development"
    SECRET_KEY: str = "super-secret-jwt-key-change-in-production-9f8e7d6c5b4a3210"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    CORS_ORIGINS: List[str] = ["*"]

    # Database & Redis
    DATABASE_URL: str = f"sqlite:///{_DEFAULT_SQLITE_PATH}"
    REDIS_URL: str = ""

    # Uploads
    UPLOAD_DIR: str = _DEFAULT_UPLOAD_DIR

    # AI (Ollama + ChromaDB)
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:1b"
    OLLAMA_TIMEOUT_SECONDS: int = 8
    CHROMA_PERSIST_DIR: str = _DEFAULT_CHROMA_DIR

    # Payments (mock | live)
    PAYMENT_MODE: str = "mock"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = "whsec_test_secret"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = "rzp_whsec_test_secret"
    PHONEPE_MERCHANT_ID: str = "PGTESTPAYUAT"
    PHONEPE_SALT_KEY: str = "099eb0cd-02cf-4e2a-8aca-3e6c6aff0399"
    PHONEPE_SALT_INDEX: str = "1"
    PHONEPE_ENV: str = "UAT"

    # Notifications (mock | live)
    NOTIFY_MODE: str = "mock"
    FCM_PROJECT_ID: str = ""
    FCM_SERVICE_ACCOUNT_JSON: str = ""
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_BUNDLE_ID: str = "com.sportshub.app"
    APNS_AUTH_KEY_PATH: str = ""


settings = Settings()
try:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
except Exception:
    settings.UPLOAD_DIR = os.path.join(_TMP_ROOT, "sportshub_uploads")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
