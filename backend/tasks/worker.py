"""
Karyawan AI — Celery Worker Tasks
Background task untuk menjalankan agent AI.
"""

from datetime import datetime, timezone
from celery_app import celery_app
from database import SessionLocal
from models import Task, Employee, ActivityLog, TaskStatus
from agents import get_agent


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def execute_agent_task(self, task_id: str):
    """
    Menjalankan agent AI untuk mengerjakan sebuah task.
    Dipanggil oleh Celery worker di background.

    Flow:
    1. Ambil task dari database
    2. Update status → WORKING
    3. Panggil agent.think() dengan prompt dari task
    4. Simpan hasil → status DONE
    5. Jika error → status ERROR, retry hingga 2x
    """
    db = SessionLocal()
    try:
        # 1. Ambil task
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"error": f"Task {task_id} not found"}

        # 2. Update status ke WORKING
        task.status = TaskStatus.WORKING
        task.started_at = datetime.now(timezone.utc)

        # Update employee current task
        employee = db.query(Employee).filter(
            Employee.name == task.employee_name
        ).first()
        if employee:
            employee.current_task_id = task_id

        # Log: mulai bekerja
        db.add(ActivityLog(
            employee_name=task.employee_name,
            action="started",
            detail=f"Mulai mengerjakan: {task.prompt[:100]}",
        ))
        db.commit()

        # 3. Jalankan agent dengan kapabilitas Database
        agent = get_agent(task.employee_name)
        if not agent:
            task.status = TaskStatus.ERROR
            task.error_message = f"Agent '{task.employee_name}' tidak terdaftar"
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"error": task.error_message}

        from database_tools import get_database_schema, execute_sql_query
        import json

        # Ambil schema untuk context AI
        schema_timesheet = get_database_schema("timesheet")
        schema_datahandling = get_database_schema("datahandling")
        
        context = "=== DATABASE SCHEMAS ===\n"
        if schema_timesheet.get("success"):
            context += f"Database 'timesheet':\n{json.dumps(schema_timesheet['data'], indent=2)}\n\n"
        if schema_datahandling.get("success"):
            context += f"Database 'datahandling':\n{json.dumps(schema_datahandling['data'], indent=2)}\n\n"
            
        context += """
        ATURAN PENGGUNAAN DATABASE:
        - Anda memiliki akses untuk menjalankan query SQL secara langsung.
        - Output HARUS selalu berupa JSON murni dengan skema:
        {
            "thought": "analisa Anda",
            "action": "reply" atau "execute_sql" atau "propose_write",
            "target_db": "timesheet" atau "datahandling" atau null,
            "sql_query": "query SQL Anda" atau null,
            "select_query": "wajib diisi HANYA jika action=propose_write. Berisi query SELECT untuk melihat data apa yang akan terhapus/terubah",
            "response": "jawaban akhir untuk user (hanya jika action = reply)"
        }
        - Jika Anda butuh membaca data, gunakan action "execute_sql" dengan query SELECT.
        - Jika Anda butuh MENGUBAH data (INSERT/UPDATE/DELETE), gunakan action "propose_write".
        """

        max_loops = 3
        loop = 0
        conversation_history = task.prompt
        
        while loop < max_loops:
            loop += 1
            raw_result = agent.think(conversation_history, context=context, json_mode=True)
            
            try:
                ai_decision = json.loads(raw_result)
            except Exception as e:
                task.result = f"Error parsing AI response: {raw_result}"
                task.status = TaskStatus.ERROR
                break

            action = ai_decision.get("action")
            
            if action == "reply":
                task.result = ai_decision.get("response")
                task.status = TaskStatus.DONE
                break
                
            elif action == "execute_sql":
                target_db = ai_decision.get("target_db")
                query = ai_decision.get("sql_query")
                
                if not query.upper().lstrip().startswith("SELECT"):
                    task.result = "AI mencoba melakukan WRITE menggunakan execute_sql (ditolak). Harus propose_write."
                    task.status = TaskStatus.ERROR
                    break
                    
                sql_res = execute_sql_query(target_db, query)
                conversation_history += f"\n\nSystem: Hasil dari query {query}:\n{json.dumps(sql_res)[:2000]}"
                
            elif action == "propose_write":
                target_db = ai_decision.get("target_db")
                query = ai_decision.get("sql_query")
                select_query = ai_decision.get("select_query")
                
                # Buat query SELECT untuk melihat data yang akan terdampak
                affected_rows_res = {"error": "No select_query provided"}
                if select_query:
                    affected_rows_res = execute_sql_query(target_db, select_query)
                
                task.proposed_query = query
                task.target_db = target_db
                task.affected_rows_json = json.dumps(affected_rows_res.get("data", []))
                
                task.status = TaskStatus.NEEDS_DECISION
                task.result = f"AI mengusulkan perubahan pada database {target_db}:\n```sql\n{query}\n```\nAlasan: {ai_decision.get('thought')}"
                break
            else:
                task.result = f"Unknown action: {action}"
                task.status = TaskStatus.ERROR
                break

        if task.status != TaskStatus.NEEDS_DECISION:
            task.completed_at = datetime.now(timezone.utc)

        # Update employee stats
        if employee:
            if task.status == TaskStatus.DONE:
                employee.total_tasks = (employee.total_tasks or 0) + 1
            employee.current_task_id = None

        # Log: selesai / butuh konfirmasi
        db.add(ActivityLog(
            employee_name=task.employee_name,
            action="completed" if task.status == TaskStatus.DONE else "needs_decision",
            detail=f"Task status: {task.status.value}",
        ))
        db.commit()

        return {"task_id": task_id, "status": task.status.value}

    except Exception as e:
        db.rollback()

        # Update task status ke ERROR
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.ERROR
                task.error_message = str(e)[:500]
                task.completed_at = datetime.now(timezone.utc)

                # Reset employee current task
                employee = db.query(Employee).filter(
                    Employee.name == task.employee_name
                ).first()
                if employee:
                    employee.current_task_id = None

                # Log: error
                db.add(ActivityLog(
                    employee_name=task.employee_name,
                    action="error",
                    detail=f"Error: {str(e)[:200]}",
                ))
                db.commit()
        except Exception:
            db.rollback()

        # Retry jika masih bisa
        raise self.retry(exc=e)

    finally:
        db.close()
