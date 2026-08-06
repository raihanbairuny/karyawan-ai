"""
Karyawan AI — Employees Router
Endpoint untuk manajemen karyawan AI.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Employee

router = APIRouter(prefix="/api/employees", tags=["Employees"])


@router.get("")
async def list_employees(db: Session = Depends(get_db)):
    """Mengambil daftar semua Karyawan AI."""
    employees = db.query(Employee).order_by(Employee.name).all()
    return [
        {
            "name": emp.name,
            "display_name": emp.name.capitalize(),
            "role": emp.role,
            "emoji": emp.emoji,
            "description": emp.description,
            "is_active": emp.is_active,
            "total_tasks": emp.total_tasks or 0,
        }
        for emp in employees
    ]


@router.get("/{name}")
async def get_employee(name: str, db: Session = Depends(get_db)):
    """Mengambil detail satu karyawan."""
    employee = db.query(Employee).filter(Employee.name == name.lower()).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    return {
        "name": employee.name,
        "display_name": employee.name.capitalize(),
        "role": employee.role,
        "emoji": employee.emoji,
        "description": employee.description,
        "is_active": employee.is_active,
        "total_tasks": employee.total_tasks or 0,
    }


@router.patch("/{name}/toggle")
async def toggle_employee(name: str, db: Session = Depends(get_db)):
    """Mengaktifkan/menonaktifkan karyawan."""
    employee = db.query(Employee).filter(Employee.name == name.lower()).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")

    employee.is_active = not employee.is_active
    db.commit()

    status = "diaktifkan" if employee.is_active else "dinonaktifkan"
    return {
        "message": f"{employee.emoji} {employee.name.capitalize()} telah {status}",
        "is_active": employee.is_active,
    }
