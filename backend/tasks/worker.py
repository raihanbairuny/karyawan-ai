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

        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from database_tools import get_database_schema, execute_sql_query
        from ssh_tools import APP_CONFIGS, get_app_logs, read_remote_file
        import json

        # Ambil schema untuk context AI
        schema_timesheet = get_database_schema("timesheet")
        schema_datahandling = get_database_schema("datahandling")
        
        context = "=== DATABASE SCHEMAS ===\n"
        if schema_timesheet.get("success"):
            context += f"Database 'timesheet':\n{json.dumps(schema_timesheet['data'], indent=2)}\n\n"
        if schema_datahandling.get("success"):
            context += f"Database 'datahandling':\n{json.dumps(schema_datahandling['data'], indent=2)}\n\n"
            
        from agents import get_all_agents
        all_agents = get_all_agents()
        roster_str = ""
        for ag_name, ag_obj in all_agents.items():
            if ag_name != task.employee_name:
                roster_str += f"- {ag_name}: {ag_obj.role}\n"

        context += f"""
        === DAFTAR APLIKASI SERVER (APP_ID) ===
        {list(APP_CONFIGS.keys())}
        
        === REKAN KERJA (UNTUK DELEGASI) ===
        Jika ada bagian tugas yang BUKAN spesialisasi Anda, Anda WAJIB menggunakan action 'delegate_task' ke rekan yang tepat.
        Daftar rekan kerja:
        {roster_str}
        
        === ATURAN PENGGUNAAN ALAT (TOOLS) ===
        Anda memiliki akses ke Database dan Server VPS secara langsung.
        Output HARUS selalu berupa JSON murni dengan skema:
        {{
            "thought": "Analisa Anda (wajib diisi)",
            "action": "Pilih salah satu: reply | execute_sql | propose_write | get_server_logs | read_remote_file | propose_code_edit | delegate_task",
            
            // Parameter khusus Database (isi jika pakai alat DB):
            "target_db": "timesheet" atau "datahandling" atau null,
            "sql_query": "query SQL Anda" atau null,
            "select_query": "query SELECT khusus untuk action=propose_write",
            
            // Parameter khusus Server DevOps (isi jika pakai alat Server):
            "app_id": "Pilih salah satu ID dari daftar aplikasi di atas",
            "lines": 50, // Jumlah baris log untuk get_server_logs
            "filepath": "Path relatif file untuk read_remote_file & propose_code_edit",
            "new_code": "Kode penuh baru (pengganti) untuk propose_code_edit",
            
            // Parameter khusus Kolaborasi (isi jika action = delegate_task):
            "target_agent": "Nama agen dari Daftar Rekan Kerja di atas",
            "delegate_prompt": "Instruksi/pesan spesifik yang ingin Anda sampaikan ke agen tersebut",
            
            "response": "jawaban akhir untuk user (hanya jika action = reply)"
        }}
        
        PANDUAN DATABASE:
        1. Jika Anda mencari string (seperti nama karyawan), SELALU gunakan "ILIKE '%nama%'" agar pencarian fleksibel, JANGAN gunakan = 'nama'.
        2. Perhatikan struktur tabel dan join kolom yang benar (contoh: hr_employee dan timesheet_timesheet harus di-join).
        3. JANGAN PERNAH menggunakan parameter (seperti $1, $2, atau ?). Masukkan nilai secara TERCETAK/LITERAL ke dalam query SQL (contoh: gunakan ILIKE '%Budi%' BUKAN ILIKE $1).
        
        PANDUAN DEVOPS:
        1. Jika user melaporkan error aplikasi, JANGAN menebak. Langsung gunakan action "get_server_logs" dengan "app_id" yang sesuai.
        2. Jika dari log Anda menemukan nama file yang bermasalah, gunakan action "read_remote_file" untuk membaca kodenya.
        3. Jika Anda sudah tahu solusinya, gunakan action "propose_code_edit" untuk memperbaiki kodenya. User akan diminta persetujuan.
        
        PENTING:
        Pastikan output Anda murni JSON yang valid! JANGAN pernah lupakan koma (,) antar properti, terutama setelah "thought". Usahakan teks dalam "thought" singkat saja agar tidak memicu JSON syntax error.
        """

        max_loops = 5
        loop = 0
        
        # Ambil riwayat percakapan sebelumnya untuk konteks
        history_text = ""
        try:
            recent_tasks = db.query(Task).filter(
                Task.id != task_id,
                Task.status == TaskStatus.DONE
            ).order_by(Task.created_at.desc()).limit(3).all()
            
            if recent_tasks:
                history_text = "=== RIWAYAT PERCAKAPAN SEBELUMNYA SEBAGAI KONTEKS ===\n"
                for t in reversed(recent_tasks):
                    history_text += f"User: {t.prompt}\nAI ({t.employee_name}): {t.result[:500]}...\n\n"
                history_text += "=== PERTANYAAN/PERINTAH SAAT INI ===\n"
        except Exception:
            db.rollback()
            pass
            
        conversation_history = history_text + task.prompt
        
        while loop < max_loops:
            loop += 1
            raw_result = agent.think(
                conversation_history, 
                context=context, 
                json_mode=True, 
                image_data=task.image_data
            )
            
            # Strip markdown json block if Gemini hallucinates it
            raw_result_clean = raw_result.strip()
            if raw_result_clean.startswith("```json"):
                raw_result_clean = raw_result_clean[7:]
            elif raw_result_clean.startswith("```"):
                raw_result_clean = raw_result_clean[3:]
            if raw_result_clean.endswith("```"):
                raw_result_clean = raw_result_clean[:-3]
            raw_result_clean = raw_result_clean.strip()

            import re
            # Auto-fix missing comma between thought and action (common LLM hallucination)
            raw_result_clean = re.sub(r'"\s*\n\s*"action"', '",\n"action"', raw_result_clean)
            
            try:
                ai_decision = json.loads(raw_result_clean)
            except Exception as e:
                if loop < max_loops:
                    conversation_history += f"\n\nSystem: ERROR PARSING JSON: {str(e)}. Pastikan output Anda murni JSON yang valid. Gunakan \\n untuk newline, dan escape tanda kutip ganda (\\\"). JANGAN masukkan blok markdown di dalam string JSON. Coba lagi."
                    continue
                else:
                    task.result = f"Error parsing AI response: {raw_result_clean}"
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
                
                import re
                clean_query = re.sub(r'--.*?\n|/\*.*?\*/', '', str(query), flags=re.DOTALL).strip().upper() if query else ""
                
                is_safe_select = (
                    clean_query.startswith("SELECT") or 
                    clean_query.startswith("WITH") or 
                    clean_query.startswith("SHOW") or 
                    clean_query.startswith("EXPLAIN")
                )
                
                if not query or not is_safe_select:
                    task.result = "AI mencoba melakukan WRITE menggunakan execute_sql (ditolak) atau query kosong. Harus propose_write dan sertakan sql_query."
                    task.status = TaskStatus.ERROR
                    break
                    
                sql_res = execute_sql_query(target_db, query)
                conversation_history += f"\n\nSystem: Hasil dari query {query}:\n{json.dumps(sql_res)[:2000]}"
                
            elif action == "propose_write":
                target_db = ai_decision.get("target_db")
                query = ai_decision.get("sql_query")
                select_query = ai_decision.get("select_query")
                
                if not query:
                    task.result = "AI gagal menyertakan sql_query untuk propose_write."
                    task.status = TaskStatus.ERROR
                    break
                
                # Buat query SELECT untuk melihat data yang akan terdampak
                affected_rows_res = {"error": "No select_query provided"}
                if select_query:
                    affected_rows_res = execute_sql_query(target_db, select_query)
                
                task.proposed_query = query
                task.target_db = target_db
                task.affected_rows_json = json.dumps({"type": "db_write", "data": affected_rows_res.get("data", [])})
                
                task.status = TaskStatus.NEEDS_DECISION
                task.result = f"AI mengusulkan perubahan pada database {target_db}:\n```sql\n{query}\n```\nAlasan: {ai_decision.get('thought')}"
                break
                
            elif action == "get_server_logs":
                app_id = ai_decision.get("app_id")
                lines = int(ai_decision.get("lines", 50))
                res = get_app_logs(app_id, lines)
                output = res.get('data')
                if not output:
                    output = "(Log kosong / tidak ada output / tidak ditemukan)"
                if not res.get("success"):
                    output = f"ERROR GAGAL: {res.get('error', output)}"
                conversation_history += f"\n\nSystem: Log terbaru dari {app_id}:\n{output}"
                
            elif action == "read_remote_file":
                app_id = ai_decision.get("app_id")
                filepath = ai_decision.get("filepath")
                res = read_remote_file(app_id, filepath)
                content = res.get('data')
                if not content:
                    content = "(File kosong atau tidak ditemukan)"
                if not res.get("success"):
                    content = f"ERROR GAGAL BACA FILE: {res.get('error', content)}"
                # Limit length to avoid blowing up context window
                if len(content) > 10000:
                    content = content[:10000] + "\n...[TRUNCATED]..."
                conversation_history += f"\n\nSystem: Isi file {filepath} di {app_id}:\n{content}"
                
            elif action == "propose_code_edit":
                app_id = ai_decision.get("app_id")
                filepath = ai_decision.get("filepath")
                new_code = ai_decision.get("new_code")
                
                if not app_id or not filepath or not new_code:
                    task.result = "AI gagal menyertakan parameter lengkap untuk propose_code_edit."
                    task.status = TaskStatus.ERROR
                    break
                    
                # Ambil kode lama untuk ditampilkan ke user
                old_code_res = read_remote_file(app_id, filepath)
                old_code = old_code_res.get("data", "") if old_code_res.get("success") else "File baru / gagal dibaca"
                
                task.proposed_query = json.dumps({"filepath": filepath, "new_code": new_code})
                task.target_db = app_id  # Reuse target_db untuk app_id
                
                diff_data = {
                    "type": "code_edit",
                    "filepath": filepath,
                    "old_code": old_code,
                    "new_code": new_code
                }
                task.affected_rows_json = json.dumps(diff_data)
                
                task.status = TaskStatus.NEEDS_DECISION
                task.result = f"AI mengusulkan perbaikan kode (Autocoding) pada aplikasi {app_id}, file `{filepath}`.\nAlasan: {ai_decision.get('thought')}"
                break
                
            elif action == "delegate_task":
                target_agent = ai_decision.get("target_agent")
                delegate_prompt = ai_decision.get("delegate_prompt")
                
                if not target_agent or not delegate_prompt:
                    task.result = "AI gagal menyertakan target_agent atau delegate_prompt untuk mendelegasikan tugas."
                    task.status = TaskStatus.ERROR
                    break
                    
                target_agent = target_agent.lower()
                
                
                # Buat task baru untuk target_agent
                new_task = Task(
                    employee_name=target_agent,
                    prompt=f"Tugas delegasi dari @{task.employee_name}: {delegate_prompt}\n\n=== KONTEKS AWAL USER ===\n{task.prompt}",
                    image_data=task.image_data,  # Teruskan gambar jika ada
                    status=TaskStatus.PENDING,
                )
                db.add(new_task)
                
                # Log aktivitas handoff
                db.add(ActivityLog(
                    employee_name=task.employee_name,
                    action="delegate_task",
                    detail=f"Mendelegasikan tugas ke @{target_agent}: {delegate_prompt[:50]}...",
                ))
                
                db.commit()
                db.refresh(new_task)
                
                # Panggil worker secara asynchronous untuk task baru
                # (import diri sendiri / circular import dihindari dengan import lokal atau delay via celery)
                try:
                    from tasks.worker import execute_agent_task as local_execute
                    local_execute.delay(new_task.id)
                except Exception as e:
                    print(f"Error triggering delegated task: {e}")
                
                task.result = f"Saya telah mendelegasikan kelanjutan tugas ini kepada @{target_agent} dengan pesan:\n> {delegate_prompt}"
                task.status = TaskStatus.DONE
                break
                
            else:
                task.result = f"Unknown action: {action}"
                task.status = TaskStatus.ERROR
                break

        # Jika loop selesai tapi AI belum memanggil "reply" (misal: asyik execute_sql 3 kali berturut-turut)
        if task.status == TaskStatus.WORKING:
            task.status = TaskStatus.DONE
            task.result = f"⚠️ Sistem mencapai batas maksimal pemikiran ({max_loops} langkah) tanpa memberikan kesimpulan akhir. Berikut adalah jejak langkah terakhir:\n\n" + conversation_history[-1000:]
            
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
            detail=f"Task status: {task.status}",
        ))
        db.commit()

        return {"task_id": task_id, "status": task.status}

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
