"""
Karyawan AI — Dashboard Router
Endpoint untuk statistik dan overview dashboard.
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Task, Employee, ActivityLog, TaskStatus
from routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["Dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """
    Mengambil semua data yang dibutuhkan dashboard dalam satu request.

    Returns:
        - stats: jumlah task per status
        - employees: daftar karyawan beserta status terkini
        - recent_activity: 20 aktivitas terakhir
    """
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    # === STATS ===
    working_count = db.query(func.count(Task.id)).filter(
        Task.status == TaskStatus.WORKING
    ).scalar() or 0

    done_24h_count = db.query(func.count(Task.id)).filter(
        Task.status == TaskStatus.DONE,
        Task.completed_at >= last_24h,
    ).scalar() or 0

    needs_decision_count = db.query(func.count(Task.id)).filter(
        Task.status == TaskStatus.NEEDS_DECISION,
    ).scalar() or 0

    error_count = db.query(func.count(Task.id)).filter(
        Task.status == TaskStatus.ERROR,
    ).scalar() or 0

    total_tasks = db.query(func.count(Task.id)).scalar() or 0

    # === EMPLOYEES ===
    employees = db.query(Employee).order_by(Employee.name).all()
    employee_list = []
    for emp in employees:
        # Cek apakah sedang mengerjakan task
        current_task = None
        if emp.current_task_id:
            task = db.query(Task).filter(Task.id == emp.current_task_id).first()
            if task:
                current_task = {
                    "id": task.id,
                    "prompt": task.prompt[:80],
                    "status": task.status,
                }

        # Ambil task terakhir yang selesai
        last_task = db.query(Task).filter(
            Task.employee_name == emp.name,
            Task.status == TaskStatus.DONE,
        ).order_by(Task.completed_at.desc()).first()

        employee_list.append({
            "name": emp.name,
            "display_name": emp.name.capitalize(),
            "role": emp.role,
            "emoji": emp.emoji,
            "description": emp.description,
            "is_active": emp.is_active,
            "total_tasks": emp.total_tasks or 0,
            "current_task": current_task,
            "status": "working" if current_task else "idle",
            "last_completed": last_task.completed_at.isoformat() if last_task and last_task.completed_at else None,
        })

    # === RECENT ACTIVITY ===
    activities = db.query(ActivityLog).order_by(
        ActivityLog.timestamp.desc()
    ).limit(20).all()

    activity_list = [
        {
            "id": act.id,
            "employee_name": act.employee_name,
            "action": act.action,
            "detail": act.detail,
            "timestamp": act.timestamp.isoformat() if act.timestamp else None,
        }
        for act in activities
    ]

    return {
        "stats": {
            "working": working_count,
            "done_24h": done_24h_count,
            "needs_decision": needs_decision_count,
            "error": error_count,
            "total": total_tasks,
        },
        "employees": employee_list,
        "recent_activity": activity_list,
    }
