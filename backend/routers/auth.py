"""
Karyawan AI — Authentication Router
Menghandle login dan JWT token generation dengan mengecek ke database Server 1 (authz).
"""

import hashlib
import jwt
import psycopg2
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
from config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

def verify_password_in_external_db(username: str, plain_password: str) -> bool:
    """Verifikasi password ke tabel authz di Server 1."""
    if not settings.TIMESHEET_DB_URL:
        # Fallback jika URL DB tidak di set
        return False
        
    try:
        # Hashing password dengan SHA-256 (sesuai format di tabel authz 64 chars)
        hashed_input = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
        
        conn = psycopg2.connect(settings.TIMESHEET_DB_URL)
        cur = conn.cursor()
        
        # Cek apakah user ada dan is_active = true
        cur.execute(
            "SELECT password FROM authz WHERE username = %s AND is_active = 't'", 
            (username,)
        )
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if row:
            db_password = row[0]
            # Bandingkan hash
            return hashed_input == db_password
            
        return False
    except Exception as e:
        print(f"Auth Error: {e}")
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency untuk memvalidasi token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    return username


@router.post("/login", response_model=Token)
async def login(req: LoginRequest):
    # Untuk development / backup login jika DB server 1 mati
    if (req.username == "admin@parkerrussell.co.id" and req.password == "admin123") or (req.username == "tes1" and req.password == "tes123"):
        access_token = create_access_token(
            data={"sub": req.username},
            expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "token_type": "bearer"}
        
    # Autentikasi ke database Server 1
    is_valid = verify_password_in_external_db(req.username, req.password)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau Password salah!",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(
        data={"sub": req.username},
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}
