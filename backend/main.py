"""
Karyawan AI — Main Application
FastAPI entry point dengan auto-seeding 9 Karyawan AI.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import engine, SessionLocal, Base
from models import Employee

# Import routers
from routers import command, employees, tasks, dashboard, servers, auth


# ============================================
# Data Seed: 9 Karyawan AI
# ============================================
EMPLOYEE_SEED = [
    {
        "name": "arif",
        "role": "Query Analyst",
        "emoji": "🔍",
        "description": "Menulis & mengoptimasi query SQL PostgreSQL",
    },
    {
        "name": "budi",
        "role": "Data Reporter",
        "emoji": "📊",
        "description": "Membuat laporan & rangkuman data dari database",
    },
    {
        "name": "citra",
        "role": "Code Reviewer",
        "emoji": "🐛",
        "description": "Me-review kode Python, cari bug, suggest improvement",
    },
    {
        "name": "dewi",
        "role": "Documentation Writer",
        "emoji": "📝",
        "description": "Membuat/update dokumentasi kode & API",
    },
    {
        "name": "eka",
        "role": "Test Engineer",
        "emoji": "🧪",
        "description": "Membuat unit test & test case untuk kode Python",
    },
    {
        "name": "fajar",
        "role": "ETL Specialist",
        "emoji": "🔄",
        "description": "Transform data, migrasi, cleaning, ETL pipeline",
    },
    {
        "name": "gita",
        "role": "Communication Assistant",
        "emoji": "📧",
        "description": "Draft email, follow-up klien, rangkum inbox",
    },
    {
        "name": "hana",
        "role": "Project Tracker",
        "emoji": "📋",
        "description": "Tracking deadline, to-do, reminder, timeline audit",
    },
    {
        "name": "indra",
        "role": "Security & Compliance",
        "emoji": "🛡️",
        "description": "Audit keamanan kode, cek kepatuhan, validasi data",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
    - Buat semua tabel di database (jika belum ada)
    - Seed 9 Karyawan AI (jika belum ada)
    """
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Seed employees
    db = SessionLocal()
    try:
        for emp_data in EMPLOYEE_SEED:
            existing = db.query(Employee).filter(
                Employee.name == emp_data["name"]
            ).first()
            if not existing:
                db.add(Employee(**emp_data))
        db.commit()
    finally:
        db.close()

    yield  # Application runs here

    # Shutdown (cleanup if needed)


# ============================================
# FastAPI App
# ============================================
app = FastAPI(
    title=settings.APP_NAME,
    description="Sistem Multi-Agent AI Employee Management — 9 Karyawan AI bekerja 24/7 untuk Anda.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS — allow access from any origin (browser HP)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(command.router)
app.include_router(employees.router)
app.include_router(tasks.router)
app.include_router(servers.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint untuk monitoring."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
