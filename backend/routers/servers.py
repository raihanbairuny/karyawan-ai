"""
Karyawan AI — Servers Router
Endpoint untuk Server Management via SSH (Timesheet & IR App).
"""

import subprocess
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from config import settings
from routers.auth import get_current_user

router = APIRouter(prefix="/api/servers", tags=["Servers"], dependencies=[Depends(get_current_user)])


def run_ssh_command(ip: str, port: int, command: str) -> tuple[bool, str]:
    """Menjalankan perintah SSH ke remote server dan mengembalikan outputnya."""
    if not ip:
        return False, "IP Server belum dikonfigurasi di .env"

    cmd = [
        "ssh",
        "-i", "/root/.ssh/karyawan_ai",
        "-p", str(port),
        "-o", "StrictHostKeyChecking=no",  # Bypass host key verification
        f"root@{ip}",
        command
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout: Server tidak merespon dalam 15 detik"
    except Exception as e:
        return False, str(e)


@router.get("/status")
async def get_servers_status():
    """Mengambil status semua aplikasi di Server 1 dan Server 2."""
    apps = []

    # 1. Server 1 - Timesheet Prod (Docker)
    if settings.SERVER1_IP:
        ok, out = run_ssh_command(
            settings.SERVER1_IP, settings.SERVER1_PORT,
            "docker ps --format '{{.Names}}' | grep -q 'streamsheet' && echo 'up' || echo 'down'"
        )
        is_running = ok and 'up' in out
        apps.append({
            "id": "timesheet_prod",
            "name": "Timesheet Prod",
            "server": "Server 1",
            "type": "Docker:8899",
            "path": "/root/streamsheet_2/",
            "status": "up" if is_running else "down",
        })

    # 2. Server 1 - Timesheet Dev (tmux)
    if settings.SERVER1_IP:
        ok, out = run_ssh_command(
            settings.SERVER1_IP, settings.SERVER1_PORT,
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8502"
        )
        is_running = ok and (out.startswith('2') or out.startswith('3') or out.startswith('4'))
        apps.append({
            "id": "timesheet_dev",
            "name": "Timesheet Dev (apps)",
            "server": "Server 1",
            "type": "tmux:8502",
            "path": "/root/streamsheet/streamsheet_2/",
            "status": "up" if is_running else "down",
        })

    # 3. Server 1 - Aplikasi IR (tmux)
    if settings.SERVER1_IP:
        ok, out = run_ssh_command(
            settings.SERVER1_IP, settings.SERVER1_PORT,
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:5173"
        )
        is_running = ok and (out.startswith('2') or out.startswith('3') or out.startswith('4'))
        apps.append({
            "id": "ir_app",
            "name": "Aplikasi IR (quality)",
            "server": "Server 1",
            "type": "tmux:5173",
            "path": "/root/parkrussel-mvp-main/",
            "status": "up" if is_running else "down",
        })

    # 4. Server 2 - Data Handling (Podman)
    if settings.SERVER2_IP:
        ok, out = run_ssh_command(
            settings.SERVER2_IP, settings.SERVER2_PORT,
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8501"
        )
        is_running = ok and (out.startswith('2') or out.startswith('3') or out.startswith('4'))
        apps.append({
            "id": "data_handling",
            "name": "Data Handling",
            "server": "Server 2",
            "type": "Podman:8501",
            "path": "/root/auditflow/prod/",
            "status": "up" if is_running else "down",
        })
    else:
        apps.append({
            "id": "data_handling",
            "name": "Data Handling",
            "server": "Server 2",
            "type": "Podman",
            "path": "/root/datahandling/prod/",
            "status": "unknown (IP belum diset)",
        })

    return apps

@router.get("/health_metrics")
async def get_health_metrics():
    """Mengambil metric RAM, CPU, dan Disk dari server 1 & 2."""
    metrics = {"server1": None, "server2": None}
    
    def parse_metrics(ip, port):
        if not ip: return None
        try:
            # Get RAM
            ok, out_ram = run_ssh_command(ip, port, "free -m | grep Mem | awk '{print $3,$2}'")
            ram_used = ram_total = 0
            if ok and out_ram:
                parts = out_ram.strip().split()
                if len(parts) >= 2:
                    ram_used, ram_total = int(parts[0]), int(parts[1])
            
            # Get Disk
            ok, out_disk = run_ssh_command(ip, port, "df -h / | tail -1 | awk '{print $5}'")
            disk_pct = 0
            if ok and out_disk:
                disk_pct = int(out_disk.strip().replace('%', ''))
                
            return {
                "ram_used_mb": ram_used,
                "ram_total_mb": ram_total,
                "ram_percent": int((ram_used / ram_total) * 100) if ram_total > 0 else 0,
                "disk_percent": disk_pct
            }
        except Exception as e:
            print(f"Error parsing metrics for {ip}: {e}")
            return None

    metrics["server1"] = parse_metrics(settings.SERVER1_IP, settings.SERVER1_PORT)
    metrics["server2"] = parse_metrics(settings.SERVER2_IP, settings.SERVER2_PORT)
    
    return metrics

class ServerAction(BaseModel):
    app_id: str
    action: str  # "start", "restart", "recreate"


@router.post("/action")
async def execute_server_action(req: ServerAction):
    """Menjalankan aksi start/restart/recreate pada aplikasi."""
    if req.app_id == "timesheet_prod":
        cmd = "cd /root/streamsheet_2 && docker start 540355d3b182 9f3f8f912759 0a2303c172d7"
        ok, out = run_ssh_command(settings.SERVER1_IP, settings.SERVER1_PORT, cmd)

    elif req.app_id == "timesheet_dev":
        cmd = """
        tmux kill-session -t apps 2>/dev/null || true
        tmux new-session -d -s apps
        tmux send-keys -t apps 'cd /root/streamsheet/streamsheet_2' C-m
        tmux send-keys -t apps 'source /root/streamsheet/streamsheet/bin/activate' C-m
        tmux send-keys -t apps 'streamlit run manage.py --server.port 8502' C-m
        """
        ok, out = run_ssh_command(settings.SERVER1_IP, settings.SERVER1_PORT, cmd)

    elif req.app_id == "ir_app":
        cmd = """
        tmux kill-session -t quality 2>/dev/null || true
        tmux new-session -d -s quality
        tmux send-keys -t quality 'cd /root/parkrussel-mvp-main/backend' C-m
        tmux send-keys -t quality 'source venv/bin/activate' C-m
        tmux send-keys -t quality 'uvicorn main:app --reload --host 0.0.0.0 --port 8001' C-m
        tmux new-window -t quality -n frontend
        tmux send-keys -t quality:1 'cd /root/parkrussel-mvp-main/frontend' C-m
        tmux send-keys -t quality:1 'npm run dev' C-m
        """
        ok, out = run_ssh_command(settings.SERVER1_IP, settings.SERVER1_PORT, cmd)

    elif req.app_id == "data_handling":
        cmd = "podman start auditflow_prod_web auditflow_prod_db auditflow_dev_web auditflow_dev_db"
        ok, out = run_ssh_command(settings.SERVER2_IP, settings.SERVER2_PORT, cmd)

    else:
        raise HTTPException(status_code=400, detail="App ID tidak dikenal")

    if not ok:
        raise HTTPException(status_code=500, detail=f"Gagal eksekusi: {out}")

    return {"message": f"Aksi '{req.action}' untuk {req.app_id} berhasil dikirim.", "output": out}
