"""
Karyawan AI — Database Connection
SQLAlchemy engine, session factory, dan dependency injection untuk FastAPI.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
