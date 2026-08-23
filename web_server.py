# web_server.py
import os
import sys
import json
import uuid
import asyncio
from typing import Generator, Optional, List
from fastapi import FastAPI, Query, HTTPException, Depends, status
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from db import init_db, get_db, User, listar_aprobaciones, resolver_aprobacion
from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_approved_user,
    get_admin_user,
    get_directora_user,
)

# Asegurar encoding UTF-8 en Windows para subprocesses
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

app = FastAPI(title="Digital Footprint Auditor Web Service")

# Inicializar DB en el arranque del servidor
@app.on_event("startup")
def startup_event():
    init_db()

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carpeta para almacenar los reportes web
WEB_REPORTES_DIR = os.path.abspath("reportes_web")
os.makedirs(WEB_REPORTES_DIR, exist_ok=True)

# --- MODELOS PYDANTIC PARA API ---
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    status: str

    class Config:
        from_attributes = True

# --- ENDPOINTS DE AUTENTICACIÓN ---

@app.post("/api/auth/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    # Verificar si el usuario ya existe
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario o correo ya está registrado"
        )
        
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role="user",
        status="pending"  # Los nuevos usuarios entran como pendientes
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/auth/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos"
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# --- ENDPOINTS DE ADMINISTRACIÓN (PROTEGIDOS CON ADMIN) ---

@app.get("/api/admin/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    return db.query(User).order_by(User.created_at.desc()).all()

@app.post("/api/admin/users/{user_id}/approve", response_model=UserResponse)
def approve_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.status = "approved"
    db.commit()
    db.refresh(user)
    return user

@app.post("/api/admin/users/{user_id}/reject", response_model=UserResponse)
def reject_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.status = "rejected"
    db.commit()
    db.refresh(user)
    return user

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="No se puede eliminar a un administrador")
    db.delete(user)
    db.commit()
    return {"message": "Usuario eliminado correctamente"}

# --- ENDPOINTS DE APROBACIÓN HUMANA (GATES) -----------------------------
# Solo la Directora Humana (rol directora_humana o admin) aprueba lo crítico.

class AprobacionResponse(BaseModel):
    id: int
    arbol_id: str
    tipo: str
    detalle: str
    borrador: str
    estado: str
    feedback: str
    created_at: object = None

    class Config:
        from_attributes = True

@app.get("/api/aprobaciones")
def obtener_aprobaciones(
    estado: str = Query("pendiente", description="estado: pendiente|aprobada|rechazada"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_directora_user),
):
    arbol_id = os.getenv("ARBOL_ID", "local")
    return listar_aprobaciones(arbol_id, estado)

@app.post("/api/aprobaciones/{aprobacion_id}/aprobar")
def aprobar(aprobacion_id: int, feedback: Optional[str] = "",
            db: Session = Depends(get_db),
            current_user: User = Depends(get_directora_user)):
    res = resolver_aprobacion(aprobacion_id, "aprobada", feedback)
    if not res:
        raise HTTPException(status_code=404, detail="Aprobación no encontrada")
    return res

@app.post("/api/aprobaciones/{aprobacion_id}/rechazar")
def rechazar(aprobacion_id: int, feedback: Optional[str] = "",
             db: Session = Depends(get_db),
             current_user: User = Depends(get_directora_user)):
    res = resolver_aprobacion(aprobacion_id, "rechazada", feedback)
    if not res:
        raise HTTPException(status_code=404, detail="Aprobación no encontrada")
    return res

# --- LÓGICA DE AUDITORÍA (SSE) ---

async def ejecutar_auditoria_sse(
    negocio: str, 
    ciudad: str, 
    modo: str, 
    sitio: str = "", 
    ig: str = "", 
    fb: str = "",
    modelo_negocio: str = "",
    contexto: str = ""
) -> Generator[str, None, None]:
    
    report_id = str(uuid.uuid4())
    output_filename = f"reporte_{report_id}.json"
    output_path = os.path.join(WEB_REPORTES_DIR, output_filename)
    
    cmd = [sys.executable, "main.py", "--cli", "-n", negocio, "-c", ciudad, "-m", modo, "-o", output_path]
    if sitio:
        cmd.extend(["--sitio", sitio])
    if ig:
        cmd.extend(["--ig", ig])
    if fb:
        cmd.extend(["--fb", fb])
    if modelo_negocio:
        cmd.extend(["--modelo-negocio", modelo_negocio])
    if contexto:
        cmd.extend(["--contexto", contexto])
        
    yield f"data: {json.dumps({'type': 'status', 'message': f'Iniciando auditoría para {negocio} en {ciudad}...'}, ensure_ascii=False)}\n\n"
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=os.environ.copy()
        )
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            decoded = line.decode('utf-8', errors='replace').rstrip()
            if decoded.strip():
                yield f"data: {json.dumps({'type': 'log', 'message': decoded}, ensure_ascii=False)}\n\n"
                
        await process.wait()
        
        if os.path.exists(output_path):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    reporte_data = json.load(f)
                yield f"data: {json.dumps({'type': 'result', 'report_id': report_id, 'report': reporte_data}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Error al leer el reporte generado: {e}'}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': 'La auditoría terminó pero no se generó el archivo de reporte JSON.'}, ensure_ascii=False)}\n\n"
            
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Error en el proceso de auditoría: {str(e)}'}, ensure_ascii=False)}\n\n"

@app.get("/api/audit-stream")
def audit_stream(
    negocio: str = Query(..., description="Nombre del negocio"),
    ciudad: str = Query(..., description="Ciudad y estado"),
    modo: str = Query("local", description="Modo: local o produccion"),
    sitio: str = Query("", description="Sitio web opcional"),
    ig: str = Query("", description="Instagram opcional"),
    fb: str = Query("", description="Facebook opcional"),
    modelo_negocio: str = Query("", description="Modelo de negocio opcional"),
    contexto: str = Query("", description="Contexto adicional opcional"),
    token: str = Query(..., description="Token JWT para autorización"),
    db: Session = Depends(get_db)
):
    """Endpoint protegido por JWT. Ejecuta la auditoría y hace streaming de los logs en vivo vía SSE"""
    try:
        user = get_current_user(token, db)
        get_approved_user(user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado o acceso bloqueado por administrador"
        )
        
    return StreamingResponse(
        ejecutar_auditoria_sse(negocio, ciudad, modo, sitio, ig, fb, modelo_negocio, contexto),
        media_type="text/event-stream"
    )

@app.get("/api/reports/{report_id}")
def obtener_reporte(report_id: str, current_user: User = Depends(get_approved_user)):
    """Permite obtener un reporte previamente guardado por su ID. Protegido para aprobados."""
    file_path = os.path.join(WEB_REPORTES_DIR, f"reporte_{report_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return FileResponse(file_path)

# Servir frontend estático. Debe montarse al final para no interferir con las APIs.
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Escucha en todas las interfaces de red en el puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
