# web_server.py
import os
import sys
import json
import uuid
import asyncio
import time
import platform
import shutil
import subprocess
import glob
from typing import Generator, Optional, List
from fastapi import FastAPI, Query, HTTPException, Depends, status, Request
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
from core.auto_open import abrir_navegador_si_local

try:
    import psutil as _psutil
except Exception:
    _psutil = None

_ARBOL_BOOT = time.time()

# --- Modo de acceso al panel ---
# Por arquitectura las cuentas viven en los árboles PRINCIPALES; el obrero es
# consola de operaciones y opera abierto. `PANEL_ABIERTO` lo fuerza:
# true/1/yes/on = abierto siempre; false/0/no/off = siempre con login.
# Por defecto (auto): abierto solo si ARBOL_ROL == "obrero".
# NUNCA abre: /api/admin/*, /api/aprobaciones* (Directora) ni /api/auth/me.
def _panel_abierto() -> bool:
    v = os.getenv("PANEL_ABIERTO", "").strip().lower()
    if v in ("true", "1", "yes", "on", "si"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    return os.getenv("ARBOL_ROL", "") == "obrero"


def get_approved_user_optional(request: Request, db: Session = Depends(get_db)):
    """Auth opcional: en panel abierto permite invitado (None); si no, exige aprobado.

    Los endpoints de gating (/api/aprobaciones, /api/admin) NO usan esta
    dependencia: siempre exigen rol. Ver seguridad.md.
    """
    if _panel_abierto():
        return None
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Se requiere iniciar sesión")
    user = get_current_user(token, db)
    return get_approved_user(user)

# Asegurar encoding UTF-8 en Windows para subprocesses
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

app = FastAPI(title="Digital Footprint Auditor Web Service")

# Inicializar DB en el arranque del servidor
@app.on_event("startup")
def startup_event():
    init_db()
    # Auto-apertura del panel (opt-in por AUTO_OPEN_BROWSER, solo localhost).
    # El host se pasa explícito: la URL de apertura siempre es local; la
    # guarda anti-remoto real es el flag (default false).
    abrir_navegador_si_local("http://127.0.0.1:8000/", host="127.0.0.1")

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
    _tarea_inicio(report_id, negocio, ciudad)
    
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
                _tarea_fin(report_id, "completada")
                yield f"data: {json.dumps({'type': 'result', 'report_id': report_id, 'report': reporte_data}, ensure_ascii=False)}\n\n"
            except Exception as e:
                _tarea_fin(report_id, "error")
                yield f"data: {json.dumps({'type': 'error', 'message': f'Error al leer el reporte generado: {e}'}, ensure_ascii=False)}\n\n"
        else:
            _tarea_fin(report_id, "error")
            yield f"data: {json.dumps({'type': 'error', 'message': 'La auditoría terminó pero no se generó el archivo de reporte JSON.'}, ensure_ascii=False)}\n\n"
            
    except Exception as e:
        _tarea_fin(report_id, "error")
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
    token: str = Query("", description="Token JWT (opcional si el panel opera abierto)"),
    db: Session = Depends(get_db)
):
    """Ejecuta la auditoría con streaming SSE. En panel abierto (obrero) no exige login."""
    if _panel_abierto():
        user = None  # invitado: consola de operaciones sin cuentas
    else:
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
def obtener_reporte(report_id: str, request: Request, current_user: User = Depends(get_approved_user_optional)):
    """Reporte por ID. En panel abierto (obrero) no exige login; si hay token se valida."""
    file_path = os.path.join(WEB_REPORTES_DIR, f"reporte_{report_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return FileResponse(file_path)

# --- PANEL DEL ÁRBOL (localhost): identidad, métricas y tareas --------------
# Endpoints abiertos solo para la máquina local (el propio árbol). No requieren
# auth: el panel vive en localhost y muestra el estado del sistema.

def _mem_windows():
    """RAM por ctypes (funciona sin psutil). Retorna (total_mb, disp_mb) o None."""
    try:
        import ctypes
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = MS(); ms.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return ms.ullTotalPhys // (1024 * 1024), ms.ullAvailPhys // (1024 * 1024)
    except Exception:
        return None

_cpu_prev = {"idle": None, "kernel": None, "user": None, "t": None}

def _cpu_windows_delta():
    """CPU % por delta de GetSystemTimes (sin psutil). Primera llamada retorna None."""
    try:
        import ctypes
        class FT(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]
        def _to_int(ft):
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        idle, kernel, user = FT(), FT(), FT()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        now = time.time()
        i, k, u = _to_int(idle), _to_int(kernel), _to_int(user)
        p = _cpu_prev
        if p["idle"] is None:
            p.update(idle=i, kernel=k, user=u, t=now)
            return None
        total_d = (k - p["kernel"]) + (u - p["user"])
        idle_d = i - p["idle"]
        p.update(idle=i, kernel=k, user=u, t=now)
        if total_d <= 0:
            return 0.0
        return round((1.0 - idle_d / total_d) * 100.0, 1)
    except Exception:
        return None


@app.get("/api/arbol/info")
def arbol_info():
    """Identidad del árbol: id, rol, uptime, versión git, plataforma."""
    info = {
        "arbol_id": os.getenv("ARBOL_ID", "local"),
        "arbol_rol": os.getenv("ARBOL_ROL", ""),
        "arbol_nombre": os.getenv("ARBOL_NOMBRE", ""),
        "uptime_s": int(time.time() - _ARBOL_BOOT),
        "plataforma": platform.system() + " " + platform.release(),
        "hostname": platform.node(),
        "python": platform.python_version(),
        "cpu_nucleos": os.cpu_count() or 0,
        "git_rama": "", "git_head": "",
        "auth_requerida": not _panel_abierto(),
    }
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, timeout=5, cwd=os.path.dirname(os.path.abspath(__file__)))
        if r.returncode == 0:
            info["git_rama"] = r.stdout.strip()
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5, cwd=os.path.dirname(os.path.abspath(__file__)))
        if r.returncode == 0:
            info["git_head"] = r.stdout.strip()
    except Exception:
        pass
    return info


@app.get("/api/arbol/metricas")
def arbol_metricas():
    """Métricas del sistema: CPU %, RAM, disco. Usa psutil si existe."""
    cpu, ram_pct, ram_total, ram_disp = None, None, None, None
    if _psutil:
        try:
            cpu = round(_psutil.cpu_percent(interval=0.4), 1)
            m = _psutil.virtual_memory()
            ram_pct, ram_total, ram_disp = round(m.percent, 1), m.total // (1024*1024), m.available // (1024*1024)
        except Exception:
            pass
    else:
        cpu = _cpu_windows_delta()
        mem = _mem_windows() if sys.platform == "win32" else None
        if mem:
            ram_total, ram_disp = mem
            ram_pct = round((ram_total - ram_disp) / ram_total * 100.0, 1) if ram_total else None
        elif sys.platform != "win32":
            try:
                pagesz, phys, avail = os.sysconf("SC_PAGE_SIZE"), os.sysconf("SC_PHYS_PAGES"), os.sysconf("SC_AVPHYS_PAGES")
                ram_total, ram_disp = phys * pagesz // (1024*1024), avail * pagesz // (1024*1024)
                ram_pct = round((ram_total - ram_disp) / ram_total * 100.0, 1) if ram_total else None
            except Exception:
                pass
    try:
        d = shutil.disk_usage(os.path.abspath("."))
        disco = {"total_gb": round(d.total / (1024**3), 1), "usado_gb": round(d.used / (1024**3), 1),
                 "libre_gb": round(d.free / (1024**3), 1),
                 "pct": round(d.used / d.total * 100.0, 1) if d.total else None}
    except Exception:
        disco = None
    return {"cpu_pct": cpu, "cpu_nucleos": os.cpu_count() or 0,
            "ram_pct": ram_pct, "ram_total_mb": ram_total, "ram_disp_mb": ram_disp,
            "disco": disco, "uptime_s": int(time.time() - _ARBOL_BOOT),
            "psutil": bool(_psutil)}


@app.get("/api/arbol/modelos")
def arbol_modelos():
    """Modelos Ollama disponibles en este árbol."""
    modelos = []
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=4) as r:
            data = json.loads(r.read())
            for m in data.get("models", []):
                modelos.append({"nombre": m.get("name", "?"),
                                "tamano_gb": round((m.get("size") or 0) / (1024**3), 2),
                                "modificado": (m.get("modified_at") or "")[:10]})
    except Exception:
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            for ln in (r.stdout or "").splitlines()[1:]:
                parts = ln.split()
                if parts:
                    modelos.append({"nombre": parts[0], "tamano_gb": None, "modificado": ""})
        except Exception:
            pass
    return {"modelos": modelos, "ollama_url": os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")}


# --- Tareas de la estación: lo que el árbol está trabajando ---------------
# Registro persistente (JSON) de auditorías lanzadas desde este panel:
# en_curso al iniciar, completada/error al terminar. Es lo que muestra
# /api/arbol/tareas (trabajo de la estación, NO procesos del sistema).
TAREAS_ESTACION_FILE = os.path.join(WEB_REPORTES_DIR, "tareas_estacion.json")


def _leer_tareas_estacion() -> list:
    try:
        with open(TAREAS_ESTACION_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _guardar_tareas_estacion(tareas: list) -> None:
    try:
        tmp = TAREAS_ESTACION_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(tareas[-100:], fh, ensure_ascii=False)
        os.replace(tmp, TAREAS_ESTACION_FILE)
    except Exception:
        pass


def _tarea_inicio(report_id: str, negocio: str, ciudad: str) -> None:
    try:
        tareas = _leer_tareas_estacion()
        tareas.append({
            "id": f"aud-{report_id[:8]}", "tipo": "auditoria",
            "titulo": f"Auditoría: {negocio} en {ciudad}",
            "estado": "en_curso", "detalle": negocio,
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "report_id": report_id, "fin": None,
        })
        _guardar_tareas_estacion(tareas)
    except Exception:
        pass


def _tarea_fin(report_id: str, estado: str) -> None:
    try:
        tareas = _leer_tareas_estacion()
        for t in tareas:
            if t.get("report_id") == report_id and t.get("estado") == "en_curso":
                t["estado"] = estado
                t["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        _guardar_tareas_estacion(tareas)
    except Exception:
        pass


@app.get("/api/arbol/tareas")
def arbol_tareas(limite: int = Query(25, ge=1, le=100)):
    """Trabajo de la estación: auditorías (en curso/completadas) y gates."""
    tareas = []
    vistos = set()
    arbol_id = os.getenv("ARBOL_ID", "local")
    # 1. Auditorías registradas por este panel (en curso primero)
    try:
        for t in _leer_tareas_estacion():
            tareas.append({"id": t.get("id"), "tipo": "auditoria",
                           "titulo": t.get("titulo", "Auditoría"),
                           "estado": t.get("estado", "en_curso"),
                           "detalle": t.get("detalle", ""),
                           "fecha": t.get("fin") or t.get("fecha")})
            if t.get("report_id"):
                vistos.add(f"reporte_{t['report_id']}.json")
    except Exception:
        pass
    # 2. Gates: aprobaciones pendientes / historial
    try:
        for a in listar_aprobaciones(arbol_id, None)[:limite]:
            estado = {"pendiente": "pendiente", "aprobada": "completada", "rechazada": "rechazada"}.get(a.get("estado"), a.get("estado", "?"))
            tareas.append({"id": f"gate-{a.get('id')}", "tipo": "gate", "titulo": f"{a.get('tipo','tarea')}: {(a.get('detalle') or '')[:90]}",
                           "estado": estado, "detalle": a.get("feedback") or "", "fecha": a.get("created_at")})
    except Exception:
        pass
    # 3. Reportes en disco sin entrada registrada = trabajo completado
    try:
        archivos = sorted(glob.glob(os.path.join(WEB_REPORTES_DIR, "reporte_*.json")),
                          key=lambda f: os.path.getmtime(f), reverse=True)[:limite]
        for f in archivos:
            if os.path.basename(f) in vistos:
                continue
            titulo, negocio = os.path.basename(f), ""
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    rep = json.load(fh)
                    negocio = rep.get("negocio") or rep.get("business") or ""
                    titulo = f"Auditoría: {negocio or os.path.basename(f)}"
            except Exception:
                pass
            tareas.append({"id": f"rep-{titulo[-40:]}", "tipo": "auditoria", "titulo": titulo,
                           "estado": "completada", "detalle": negocio,
                           "fecha": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(f)))})
    except Exception:
        pass
    # en_curso primero, resto por fecha desc
    tareas.sort(key=lambda t: (0 if t.get("estado") == "en_curso" else 1, t.get("fecha") or ""))
    return {"arbol_id": arbol_id, "tareas": tareas[:limite], "total": len(tareas)}


def _repo_dir() -> str:
    """Directorio raíz del repo (donde vive web_server.py)."""
    return os.path.dirname(os.path.abspath(__file__))


def _git_head(repo: str) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10, cwd=repo)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


@app.post("/api/arbol/actualizar")
def arbol_actualizar():
    """Actualiza el código del árbol desde el repo (git pull --ff-only).

    Usa fast-forward only: jamás destruye cambios locales; si hay
    divergencia devuelve el error para resolución manual. Si el código
    cambió, el servicio debe reiniciarse para aplicar (reinicio_requerido).
    """
    repo = _repo_dir()
    antes = _git_head(repo)
    try:
        r = subprocess.run(["git", "pull", "--ff-only"],
                           capture_output=True, text=True, timeout=120, cwd=repo)
        salida = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()[:1500]
        despues = _git_head(repo)
        cambio = bool(antes and despues and antes != despues)
        return {"ok": r.returncode == 0, "salida": salida,
                "head_antes": antes, "head_despues": despues,
                "cambio": cambio, "reinicio_requerido": cambio}
    except Exception as e:
        return {"ok": False, "salida": str(e)[:500], "head_antes": antes,
                "head_despues": despues if 'despues' in dir() else antes,
                "cambio": False, "reinicio_requerido": False}

# Servir frontend estático. Debe montarse al final para no interferir con las APIs.
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Escucha en todas las interfaces de red en el puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
