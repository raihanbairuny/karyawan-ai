"""
Karyawan AI — Webhook Alerts (Self-Healing System)
Menerima alert dari sistem luar (misal: Sentry, Prometheus, custom error handler)
dan secara otomatis menugaskan agen (misal: Budi) untuk memperbaikinya.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models import Task, TaskStatus
from tasks.worker import execute_agent_task
import json

router = APIRouter(prefix="/api/webhook", tags=["Webhook"])

@router.post("/alert")
async def receive_alert(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint generic untuk menerima alert error.
    Payload bebas, akan dikonversi menjadi string JSON.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw_text": (await request.body()).decode('utf-8')}
        
    app_source = payload.get("app", payload.get("service", "unknown_app"))
    error_message = payload.get("message", payload.get("error", str(payload)))
    
    prompt = f"[AUTO-ALERT DARI SISTEM] Aplikasi '{app_source}' melaporkan error:\n```json\n{json.dumps(payload, indent=2)}\n```\n\nTolong segera periksa log server untuk aplikasi ini dan buatkan usulan perbaikan (propose_code_edit) jika memungkinkan!"
    
    # Tugaskan ke Budi (Spesialis DevOps/Error)
    assigned_agent = "budi"
    
    task = Task(
        employee_name=assigned_agent,
        prompt=prompt,
        status=TaskStatus.PENDING,
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    execute_agent_task.delay(task.id)
    
    return {"success": True, "message": "Alert received, Budi has been deployed.", "task_id": task.id}
