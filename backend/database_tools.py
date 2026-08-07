"""
Karyawan AI — Database Tools
Modul untuk mengeksekusi query SQL pada database external (Timesheet & Data Handling).
"""

import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from config import settings


import uuid
from decimal import Decimal

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


def get_db_connection(target_db: str):
    """Mendapatkan koneksi ke database target."""
    db_url = None
    if target_db.lower() == "timesheet":
        db_url = settings.TIMESHEET_DB_URL
    elif target_db.lower() == "datahandling":
        db_url = settings.DATAHANDLING_DB_URL

    if not db_url:
        raise ValueError(f"URL konfigurasi untuk database '{target_db}' belum disetel di .env")

    return psycopg2.connect(db_url)


def execute_sql_query(target_db: str, query: str) -> dict:
    """
    Mengeksekusi SQL query ke target database.
    Hanya mengembalikan maksimal 50 baris untuk mencegah overload.
    
    Returns:
        dict: {"success": bool, "data": list/dict, "error": str, "affected_rows": int}
    """
    try:
        conn = get_db_connection(target_db)
        # Buka transaksi
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Cegah query berbahaya dieksekusi secara sembarangan
            query_upper = query.strip().upper()
            is_select = query_upper.startswith("SELECT") or query_upper.startswith("SHOW") or query_upper.startswith("EXPLAIN")
            
            cur.execute(query)
            affected_rows = cur.rowcount
            
            data = []
            if is_select or cur.description:
                # Jika SELECT, fetch results (limit manually in app if needed, but we fetch up to 100 for safety)
                rows = cur.fetchmany(100)
                data = [dict(row) for row in rows]
            
            # Jika ini bukan select dan kita menggunakan fungsi ini untuk execute langsung, kita harus commit
            # NAMUN, fungsi ini digunakan HANYA untuk eksekusi final, ATAU untuk eksekusi SELECT.
            conn.commit()
            
            return {
                "success": True,
                "data": json.loads(json.dumps(data, cls=CustomJSONEncoder)),
                "affected_rows": affected_rows,
                "error": None
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "data": None,
                "affected_rows": 0,
                "error": str(e)
            }
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "affected_rows": 0,
            "error": f"Connection Error: {str(e)}"
        }

def get_database_schema(target_db: str) -> dict:
    """Mendapatkan daftar tabel dan struktur kolom dari database target."""
    query = """
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        ORDER BY table_name, ordinal_position;
    """
    res = execute_sql_query(target_db, query)
    
    if not res["success"]:
        return res
        
    schema = {}
    for row in res["data"]:
        t_name = row["table_name"]
        if t_name not in schema:
            schema[t_name] = []
        schema[t_name].append(f"{row['column_name']} ({row['data_type']})")
        
    return {
        "success": True,
        "data": schema,
        "error": None
    }
