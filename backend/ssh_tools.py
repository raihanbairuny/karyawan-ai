"""
Karyawan AI — SSH Tools
Modul untuk menangani koneksi SSH, baca log server, baca file, dan autocoding via Git Branch.
"""

import subprocess
import base64
from config import settings

# Mapping ID aplikasi ke konfigurasi server
APP_CONFIGS = {
    "timesheet_prod": {
        "ip": settings.SERVER1_IP,
        "port": settings.SERVER1_PORT,
        "type": "docker",
        "container_name": "streamsheet_2-web-1", # Nama container di docker-compose
        "path": "/root/streamsheet_2"
    },
    "timesheet_dev": {
        "ip": settings.SERVER1_IP,
        "port": settings.SERVER1_PORT,
        "type": "tmux",
        "tmux_session": "apps",
        "path": "/root/streamsheet/streamsheet_2"
    },
    "ir_app": {
        "ip": settings.SERVER1_IP,
        "port": settings.SERVER1_PORT,
        "type": "tmux",
        "tmux_session": "quality",
        "path": "/root/parkrussel-mvp-main"
    },
    "data_handling": {
        "ip": settings.SERVER2_IP,
        "port": settings.SERVER2_PORT,
        "type": "podman",
        "container_name": "auditflow_prod_web",
        "path": "/root/auditflow/prod"
    }
}

def run_ssh_command(ip: str, port: int, command: str) -> tuple[bool, str]:
    """Menjalankan perintah SSH ke remote server dan mengembalikan outputnya."""
    if not ip:
        return False, "IP Server belum dikonfigurasi di .env"

    cmd = [
        "ssh",
        "-i", "/root/.ssh/karyawan_ai",
        "-p", str(port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5",
        "-o", "BatchMode=yes",
        f"root@{ip}",
        command
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout: Server tidak merespon dalam 30 detik"
    except Exception as e:
        return False, str(e)

def get_app_logs(app_id: str, lines: int = 50) -> dict:
    """Mengambil log dari aplikasi (docker, tmux, atau podman)."""
    cfg = APP_CONFIGS.get(app_id)
    if not cfg:
        return {"success": False, "error": f"App ID '{app_id}' tidak ditemukan. Gunakan salah satu dari: {list(APP_CONFIGS.keys())}"}
    
    ip = cfg["ip"]
    port = cfg["port"]
    app_type = cfg["type"]
    
    if app_type == "docker":
        container = cfg.get("container_name")
        if not container:
            return {"success": False, "error": "Konfigurasi container_name tidak ditemukan untuk docker"}
        cmd = f"docker logs --tail {lines} {container}"
    elif app_type == "podman":
        container = cfg.get("container_name")
        cmd = f"podman logs --tail {lines} {container}"
    elif app_type == "tmux":
        session = cfg["tmux_session"]
        cmd = f"tmux capture-pane -pt {session} -S -{lines}"
    else:
        return {"success": False, "error": "Tipe aplikasi tidak didukung"}
        
    ok, out = run_ssh_command(ip, port, cmd)
    return {"success": ok, "data": out if ok else out}

def read_remote_file(app_id: str, filepath: str) -> dict:
    """Membaca isi file kode di VPS."""
    cfg = APP_CONFIGS.get(app_id)
    if not cfg:
        return {"success": False, "error": f"App ID '{app_id}' tidak ditemukan"}
        
    ip = cfg["ip"]
    port = cfg["port"]
    base_path = cfg["path"]
    # Jika AI mengirimkan path absolut yang mengandung base_path, otomatis potong menjadi relatif
    if filepath.startswith(base_path):
        filepath = filepath[len(base_path):].lstrip("/")
        
    # Path traversal protection basic
    if ".." in filepath or filepath.startswith("/"):
        return {"success": False, "error": "Path harus relatif terhadap root aplikasi dan tidak boleh mengandung '..'"}
        
    full_path = f"{base_path}/{filepath}"
    
    cmd = f"cat {full_path}"
    ok, out = run_ssh_command(ip, port, cmd)
    return {"success": ok, "data": out if ok else out}

def apply_git_hotfix(app_id: str, filepath: str, new_content: str) -> dict:
    """Membuat branch hotfix baru di VPS, menyimpan kode, lalu push ke origin."""
    cfg = APP_CONFIGS.get(app_id)
    if not cfg:
        return {"success": False, "error": f"App ID '{app_id}' tidak ditemukan"}
        
    ip = cfg["ip"]
    port = cfg["port"]
    base_path = cfg["path"]
    # Jika AI mengirimkan path absolut yang mengandung base_path, otomatis potong menjadi relatif
    if filepath.startswith(base_path):
        filepath = filepath[len(base_path):].lstrip("/")
        
    # Base64 encode content to safely pass via SSH echo
    b64_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    full_path = f"{base_path}/{filepath}"
    
    bash_script = f"""
cd {base_path} || exit 1
if [ ! -d ".git" ]; then
    echo "Error: {base_path} is not a git repository"
    exit 1
fi

# Simpan perubahan lokal (jika ada) agar tidak hilang (Lebih aman dari reset --hard)
git stash
git checkout main || git checkout master || exit 1
git pull origin HEAD || true

# Create new branch
BRANCH_NAME="ai-hotfix-$(date +%s)"
git checkout -b $BRANCH_NAME || exit 1

# Write new content
echo "{b64_content}" | base64 -d > {filepath} || exit 1

# Commit and Push
git add {filepath} || exit 1
git commit -m "AI Hotfix for {filepath}" || exit 1
git push -u origin $BRANCH_NAME || exit 1

echo "Hotfix branch $BRANCH_NAME created and pushed successfully."
"""
    ok, out = run_ssh_command(ip, port, bash_script)
    return {"success": ok, "data": out if ok else out}
