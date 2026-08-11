"""
Karyawan AI — Tasks Router
Endpoint untuk melihat dan mengelola task.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Task, TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("")
async def list_tasks(
    employee: str = Query(None, description="Filter berdasarkan nama karyawan"),
    status: str = Query(None, description="Filter berdasarkan status"),
    limit: int = Query(20, ge=1, le=100, description="Jumlah task yang diambil"),
    db: Session = Depends(get_db),
):
    """Mengambil daftar task dengan filter opsional."""
    query = db.query(Task)

    if employee:
        query = query.filter(Task.employee_name == employee.lower())
    if status:
        query = query.filter(Task.status == status)

    tasks = query.order_by(Task.created_at.desc()).limit(limit).all()

    return [
        {
            "id": task.id,
            "employee_name": task.employee_name,
            "prompt": task.prompt,
            "result": task.result,
            "status": task.status,
            "error_message": task.error_message,
            "affected_rows_json": task.affected_rows_json,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
        for task in tasks
    ]


@router.get("/{task_id}")
async def get_task(task_id: str, db: Session = Depends(get_db)):
    """Mengambil detail satu task beserta hasilnya."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")

    return {
        "id": task.id,
        "employee_name": task.employee_name,
        "prompt": task.prompt,
        "result": task.result,
        "status": task.status,
        "error_message": task.error_message,
        "affected_rows_json": task.affected_rows_json,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    """Menghapus task (hanya yang sudah selesai atau error)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")

    if task.status == TaskStatus.WORKING:
        raise HTTPException(
            status_code=400,
            detail="Tidak bisa menghapus task yang sedang dikerjakan",
        )

    db.delete(task)
    db.commit()
    return {"message": f"Task {task_id[:8]}... berhasil dihapus"}
