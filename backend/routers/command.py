"""
Karyawan AI — Command Router
Endpoint untuk mengirim perintah ke Karyawan AI.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import Task, Employee, ActivityLog, TaskStatus
from agents import get_agent
from tasks.worker import execute_agent_task
from routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["Command"], dependencies=[Depends(get_current_user)])


class CommandRequest(BaseModel):
    """Schema untuk mengirim perintah ke karyawan."""
    employee_name: str = Field(..., description="Nama karyawan (lowercase)")
    prompt: str = Field(..., min_length=1, max_length=5000, description="Perintah untuk karyawan")


class CommandResponse(BaseModel):
    """Schema response setelah perintah dikirim."""
    task_id: str
    employee_name: str
    message: str


@router.post("/command", response_model=CommandResponse)
async def send_command(request: CommandRequest, db: Session = Depends(get_db)):
    """
    Mengirim perintah ke salah satu Karyawan AI.

    Flow:
    1. Validasi karyawan ada dan aktif
    2. Simpan task baru ke database (status: PENDING)
    3. Kirim task ke Celery worker (background)
    4. Return response ke user langsung (non-blocking)
    """
    name = request.employee_name.lower().strip()
    
    valid_names = ["budi", "arif", "dewi", "citra", "eka", "fajar", "gita", "hana", "indra"]
    
    if name == "auto":
        prompt_lower = request.prompt.lower()
        # Jika user menyebut nama agen di awal pesan (misal: "arif, tolong cek...")
        assigned = None
        for v in valid_names:
            if prompt_lower.startswith(f"{v},") or prompt_lower.startswith(f"{v} "):
                assigned = v
                break
                
        if assigned:
            name = assigned
        else:
            try:
                from google.genai import Client
                from config import settings
                from database import SessionLocal
                from models import Task
                
                db = SessionLocal()
                last_task = db.query(Task).filter(Task.status == 'done').order_by(Task.created_at.desc()).first()
                db.close()
                
                context_str = f"Tugas sebelumnya: {last_task.prompt}\n" if last_task else ""
                
                client = Client(api_key=settings.GEMINI_API_KEY)
                llm_prompt = f"Tentukan agen AI yang paling cocok mengerjakan tugas berikut. Jawab HANYA dengan 1 KATA (nama agen).\n\n- budi (Sistem Administrator / DevOps / Error Aplikasi / Server)\n- arif (Database Analyst / SQL / Semua urusan cek data di tabel database)\n- dewi (Data Engineer / Analytics)\n\nJika tugas meminta mengecek data, tabel, atau database, pilih 'arif'.\n\n{context_str}Tugas saat ini: {request.prompt}"
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=llm_prompt
                )
                predicted = response.text.strip().lower()
                
                assigned = "arif" # default fallback for data queries
                for v in valid_names:
                    if v in predicted:
                        assigned = v
                        break
                name = assigned
            except Exception as e:
                name = "arif" # fallback to Arif for general data tasks

    # Validasi agent ada
    agent = get_agent(name)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Karyawan '{name}' tidak ditemukan. "
                   f"Pilihan: arif, budi, citra, dewi, eka, fajar, gita, hana, indra",
        )

    # Validasi employee aktif di database
    employee = db.query(Employee).filter(Employee.name == name).first()
    if employee and not employee.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Karyawan '{name}' sedang tidak aktif (di-pause).",
        )

    # Buat task baru
    task = Task(
        employee_name=name,
        prompt=request.prompt,
        status=TaskStatus.PENDING,
    )
    db.add(task)

    # Log aktivitas
    db.add(ActivityLog(
        employee_name=name,
        action="task_created",
        detail=f"Perintah baru: {request.prompt[:100]}",
    ))

    db.commit()
    db.refresh(task)

    # Kirim ke Celery worker (background processing)
    execute_agent_task.delay(task.id)

    return CommandResponse(
        task_id=task.id,
        employee_name=name,
        message=f"{agent.emoji} {agent.display_name} mulai bekerja...",
    )


@router.post("/command/{task_id}/confirm")
async def confirm_task(task_id: str, db: Session = Depends(get_db)):
    """Mengkonfirmasi dan mengeksekusi query database yang diajukan AI."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or task.status != TaskStatus.NEEDS_DECISION:
        raise HTTPException(status_code=400, detail="Task tidak valid atau tidak menunggu konfirmasi")
        
    from database_tools import execute_sql_query
    import os
    import json
    
    action_type = "db_write"
    if task.affected_rows_json:
        try:
            parsed = json.loads(task.affected_rows_json)
            if isinstance(parsed, dict) and parsed.get("type") == "code_edit":
                action_type = "code_edit"
        except:
            pass
            
    if action_type == "code_edit":
        from ssh_tools import apply_git_hotfix
        payload = json.loads(task.proposed_query)
        res = apply_git_hotfix(task.target_db, payload["filepath"], payload["new_code"])
        
        if res.get("success"):
            task.status = TaskStatus.DONE
            task.result += f"\n\n**STATUS: DISETUJUI & DIEKSEKUSI**\nBerhasil memodifikasi kode di VPS.\n```text\n{res['data']}\n```"
        else:
            task.status = TaskStatus.ERROR
            task.result += f"\n\n**STATUS: GAGAL DIEKSEKUSI**\nError SSH: {res.get('data') or res.get('error')}"
    else:
        # Lakukan Backup CSV terlebih dahulu (Hanya untuk Database)
        if task.affected_rows_json:
            try:
                backup_dir = "backups"
                os.makedirs(backup_dir, exist_ok=True)
                import time
                backup_file = os.path.join(backup_dir, f"backup_{task.target_db}_{task_id}_{int(time.time())}.json")
                with open(backup_file, "w") as f:
                    f.write(task.affected_rows_json)
            except Exception as e:
                print(f"Warning: Failed to create backup file: {e}")
                
        # Eksekusi Query
        res = execute_sql_query(task.target_db, task.proposed_query)
        
        if res["success"]:
            task.status = TaskStatus.DONE
            task.result += f"\n\n**STATUS: DISETUJUI & DIEKSEKUSI**\nBerhasil mengubah {res['affected_rows']} baris."
        else:
            task.status = TaskStatus.ERROR
            task.result += f"\n\n**STATUS: GAGAL DIEKSEKUSI**\nError: {res['error']}"
        
    db.commit()
    return {"message": "Tindakan berhasil dieksekusi", "success": res.get("success", False)}


@router.post("/command/{task_id}/cancel")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """Membatalkan eksekusi query."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or task.status != TaskStatus.NEEDS_DECISION:
        raise HTTPException(status_code=400, detail="Task tidak valid atau tidak menunggu konfirmasi")
        
    task.status = TaskStatus.DONE
    task.result += "\n\n**STATUS: DIBATALKAN OLEH USER**"
    db.commit()
    
    return {"message": "Tindakan telah dibatalkan"}
