# auth.py
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import bcrypt
from db import get_db, User

# Configuración del JWT
# En producción DEBE definirse JWT_SECRET_KEY en .env. Si no, se genera uno
# efímero seguro al arrancar (los tokens se invalidan al reiniciar, pero no usa
# un default predecible publicado en el repo).
import secrets as _secrets
_SECRET = os.getenv("JWT_SECRET_KEY", "").strip()
if _SECRET:
    SECRET_KEY = _SECRET
else:
    SECRET_KEY = _secrets.token_hex(32)
    print("[SEGURIDAD] JWT_SECRET_KEY no definido en .env; usando secreto efímero. "
          "Defínelo para mantener sesiones entre reinicios.", file=sys.stderr)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 días para comodidad

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def crear_usuario(db: Session, username: str, email: str, password: str,
                  role: str = "user", status: str = "approved") -> User:
    """Crea un usuario nuevo. Lanza ValueError si el username o email ya existen."""
    existente = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existente:
        raise ValueError(f"Ya existe un usuario con ese username/email: {username}")
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        role=role,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Obtener usuario a partir del token JWT
def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales de acceso",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# Dependencia para requerir que el usuario esté aprobado
def get_approved_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role == "admin":
        return current_user  # El admin siempre tiene acceso
        
    if current_user.status != "approved":
        status_msg = "Tu cuenta está pendiente de aprobación por el administrador."
        if current_user.status == "rejected":
            status_msg = "Tu solicitud de acceso ha sido rechazada."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=status_msg
        )
    return current_user

# Dependencia para requerir rol de administrador
def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador para realizar esta acción."
        )
    return current_user

# Dependencia para la Directora Humana (admin o directora_humana)
# Es el ÚNICO rol autorizado a aprobar/rechazar acciones críticas (gates).
def get_directora_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "directora_humana"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo la Directora Humana puede aprobar acciones críticas."
        )
    return current_user
