"""
Karyawan AI — Configuration
Membaca environment variables dari file .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://karyawan:karyawan_secret_2026@postgres:5432/karyawan_ai",
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-secret-key-change-me")

    # Gemini Model Configuration
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # App Info
    APP_NAME: str = "Karyawan AI"
    APP_VERSION: str = "1.0.0"

    # Server Management
    SERVER1_IP: str | None = os.getenv("SERVER1_IP")
    SERVER1_PORT: int = int(os.getenv("SERVER1_PORT", "22"))
    SERVER2_IP: str | None = os.getenv("SERVER2_IP")
    SERVER2_PORT: int = int(os.getenv("SERVER2_PORT", "22"))

    # Authentication
    JWT_SECRET: str = os.getenv("SECRET_KEY", "fallback-secret-2026")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours
    TIMESHEET_DB_URL: str | None = os.getenv("TIMESHEET_DB_URL")
    DATAHANDLING_DB_URL: str | None = os.getenv("DATAHANDLING_DB_URL")

    class Config:
        env_file = ".env"


settings = Settings()
