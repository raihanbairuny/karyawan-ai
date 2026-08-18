"""
Karyawan AI — Database Models
Definisi tabel: Task, Employee, ActivityLog
"""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Index
from database import Base


def utcnow():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def generate_id():
    """Generate a short UUID for primary keys."""
    return str(uuid.uuid4())


class TaskStatus(str, PyEnum):
    """Status lifecycle of a task."""
    PENDING = "pending"
    WORKING = "working"
    DONE = "done"
    ERROR = "error"
    NEEDS_DECISION = "needs_decision"


class Task(Base):
    """
    Menyimpan setiap perintah yang diberikan ke Karyawan AI.
    Lifecycle: PENDING → WORKING → DONE / ERROR / NEEDS_DECISION
    """
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=generate_id)
    employee_name = Column(String, nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    image_data = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    status = Column(String, default=TaskStatus.PENDING, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Fitur Database Agent (Write Access)
    proposed_query = Column(Text, nullable=True)
    target_db = Column(String, nullable=True)
    affected_rows_json = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_tasks_employee_status", "employee_name", "status"),
    )


class Employee(Base):
    """
    Data setiap Karyawan AI.
    Di-seed saat aplikasi pertama kali dijalankan.
    """
    __tablename__ = "employees"

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)
    emoji = Column(String, default="🤖")
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    total_tasks = Column(Integer, default=0)
    current_task_id = Column(String, nullable=True)


class ActivityLog(Base):
    """
    Catatan aktivitas setiap Karyawan AI.
    Digunakan untuk Activity Feed di dashboard.
    """
    __tablename__ = "activity_logs"

    id = Column(String, primary_key=True, default=generate_id)
    employee_name = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    detail = Column(Text)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)

class CronJob(Base):
    """
    Tugas rutin/terjadwal untuk Karyawan AI.
    """
    __tablename__ = "cron_jobs"

    id = Column(String, primary_key=True, default=generate_id)
    employee_name = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    cron_expression = Column(String, nullable=False) # e.g. "0 8 * * *"
    is_active = Column(Boolean, default=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
