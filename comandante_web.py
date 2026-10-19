# comandante_web.py
"""
Panel web del COMANDANTE (árbol principal) en localhost.

Opera sobre los árboles hijos (obreros) por canal privado (SSH/Tailscale):
listar, registrar, ping, diagnóstico, ejecutar comando, propagar upgrade y archivo.

Arranque:
    uv run uvicorn comandante_web:app --host 127.0.0.1 --port 8001

Auth: si se define COMANDANTE_WEB_TOKEN, todas las rutas API requieren el header
      `X-Comandante-Token`. Si no se define, el panel opera abierto en localhost.
"""
import os
import sys
import json
import shutil
import subprocess
import threading
import urllib.request
import getpass
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db import init_db, listar_arboles as db_listar_arboles, registrar_arbol as db_registrar_arbol
from db import crear_aprobacion as db_crear_aprobacion, listar_aprobaciones as db_listar_aprobaciones
from db import resolver_aprobacion as db_resolver_aprobacion
from comunicacion.comandante_mcp import (
    ping_arbol, estado_arbol, ejecutar_comando, propagar_upgrade, propagar_archivo,
)
from core.auto_open import abrir_navegador_si_local

# Asegurar sys.path para imports locales si se corre como `python comandante_web.py`
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

app = FastAPI(title="Panel del Comandante — Mente Colmena")

TOKEN = os.getenv("COMANDANTE_WEB_TOKEN", "").strip()
STATIC_DIR = os.path.join(HERE, "comandante_web", "static")


@app.on_event("startup")
def _startup():
    init_db()
    # Auto-apertura del panel (opt-in por AUTO_OPEN_BROWSER, solo localhost).
    _puerto = int(os.getenv("COMANDANTE_WEB_PORT", "8001"))
    abrir_navegador_si_local(f"http://127.0.0.1:{_puerto}/", host="127.0.0.1")


# --- Auth opcional --------------------------------------------------------
def _authorize(x_comandante_token: str | None):
    if TOKEN and x_comandante_token != TOKEN:
        raise HTTPException(status_code=401, detail="Token de comandante inválido")


# --- Modelos --------------------------------------------------------------
class ArbolRegistro(BaseModel):
    arbol_id: str
    host: str
    usuario: str = "root"
    puerto: int = 22
    canal: str = "ssh"
    nombre: str = ""
    repo_dir: str = "."

class ComandoBody(BaseModel):
    comando: str

class UpgradeBody(BaseModel):
    rama: str = "main"

class ArchivoBody(BaseModel):
    origen_local: str
    destino_remoto: str


class CampanaBody(BaseModel):
    objetivo: str
    ciudad: str = ""
    marca: str = ""
    plataformas: str = "instagram"
    audiencia: str = ""
    tono: str = "profesional"
    presupuesto: float = 0
    periodo_dias: int = 7


# --- API ------------------------------------------------------------------
@app.get("/api/arboles")
def api_listar(x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    return db_listar_arboles()


@app.post("/api/arboles")
def api_registrar(body: ArbolRegistro, x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    return db_registrar_arbol(body.arbol_id, body.host, body.usuario, body.puerto,
                              body.canal, body.nombre, body.repo_dir)


@app.post("/api/arboles/{arbol_id}/ping")
def api_ping(arbol_id: str, x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    return json.loads(ping_arbol(arbol_id))


@app.post("/api/arboles/{arbol_id}/estado")
def api_estado(arbol_id: str, x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    return json.loads(estado_arbol(arbol_id))


@app.post("/api/arboles/{arbol_id}/comando")
def api_comando(arbol_id: str, body: ComandoBody, x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    return json.loads(ejecutar_comando(arbol_id, body.comando))


@app.post("/api/arboles/{arbol_id}/upgrade")
def api_upgrade(arbol_id: str, body: UpgradeBody, x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    return json.loads(propagar_upgrade(arbol_id, body.rama))


@app.post("/api/arboles/{arbol_id}/archivo")
def api_archivo(arbol_id: str, body: ArchivoBody, x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    return json.loads(propagar_archivo(arbol_id, body.origen_local, body.destino_remoto))


# --- Campañas (orquestador en segundo plano) ----------------------------------
# Lanza ejecutar_campana (5 etapas CrewAI, tarda decenas de minutos) en un hilo
# para no bloquear el panel. El resultado se guarda en shared/campanas/{id}.json.
# La etapa de exposición crea un gate en db.Aprobacion (solo lo aprueba la Directora).

_CAMPANAS: dict = {}
_CAMP_DIR = os.path.join(HERE, "shared", "campanas")


def _campana_guardar(job: dict):
    try:
        os.makedirs(_CAMP_DIR, exist_ok=True)
        with open(os.path.join(_CAMP_DIR, job["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(job, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


def _campana_run(job_id: str, objetivo: str, inputs: dict):
    from orquestador.campana import ejecutar_campana
    job = _CAMPANAS.get(job_id, {})
    try:
        job["estado"] = "en_curso"
        job["inicio"] = datetime.now().isoformat(timespec="seconds")
        res = ejecutar_campana(objetivo, inputs)
        job["estado"] = str(res.get("estado", "terminada"))
        job["resultado"] = res
        job["fin"] = datetime.now().isoformat(timespec="seconds")
    except Exception as e:
        job["estado"] = "error"
        job["error"] = str(e)[:500]
        job["fin"] = datetime.now().isoformat(timespec="seconds")
    _campana_guardar(job)


@app.post("/api/campanas")
def api_campana_lanzar(body: CampanaBody, x_comandante_token: str | None = Header(default=None)):
    """Lanza una campaña completa en segundo plano. Devuelve el id del trabajo."""
    _authorize(x_comandante_token)
    objetivo = (body.objetivo or "").strip()
    if not objetivo:
        raise HTTPException(status_code=400, detail="objetivo requerido")
    # Tope de historial: conserva activas, descarta terminadas más viejas.
    if len(_CAMPANAS) >= 20:
        viejas = sorted([j for j in _CAMPANAS.values() if j["estado"] not in ("en_curso", "en_cola")],
                        key=lambda j: j["id"])[:len(_CAMPANAS) - 19]
        for j in viejas:
            _CAMPANAS.pop(j["id"], None)
    job_id = uuid.uuid4().hex[:8]
    inputs = {"ciudad": body.ciudad, "marca": body.marca, "plataformas": body.plataformas,
              "audiencia": body.audiencia, "tono": body.tono, "presupuesto": body.presupuesto,
              "periodo_dias": body.periodo_dias, "metricas_json": "{}"}
    _CAMPANAS[job_id] = {"id": job_id, "objetivo": objetivo, "inputs": inputs,
                         "estado": "en_cola", "inicio": None, "fin": None}
    t = threading.Thread(target=_campana_run, args=(job_id, objetivo, inputs), daemon=True)
    t.start()
    return {"id": job_id, "estado": "en_cola", "objetivo": objetivo}


@app.get("/api/campanas")
def api_campanas_listar(x_comandante_token: str | None = Header(default=None)):
    """Lista trabajos (sin el resultado completo; ver detalle por id)."""
    _authorize(x_comandante_token)
    return [{k: j.get(k) for k in ("id", "objetivo", "estado", "inicio", "fin", "error")}
            for j in sorted(_CAMPANAS.values(), key=lambda j: j["id"], reverse=True)]


@app.get("/api/campanas/{job_id}")
def api_campana_detalle(job_id: str, x_comandante_token: str | None = Header(default=None)):
    """Detalle + resultado de una campaña."""
    _authorize(x_comandante_token)
    job = _CAMPANAS.get(job_id)
    if job is None:
        try:
            with open(os.path.join(_CAMP_DIR, job_id + ".json"), encoding="utf-8") as f:
                job = json.load(f)
        except Exception:
            raise HTTPException(status_code=404, detail="campaña no encontrada")
    return job


# --- Salud de sesión y reinicio seguro --------------------------------------
# Evita que un reinicio con descargas a medias o con Tailscale gestionado por
# otro usuario deje el árbol en conflicto (perfil/servicios). Solo lectura y
# parada de tareas secundarias; NUNCA detiene este propio panel.

_TAREAS_ARBOL = ["ArbolWeb", "ComandanteWeb", "OllamaServe", "OllamaBg"]


def _usuario_panel() -> str:
    try:
        return os.getenv("USERNAME") or os.getenv("USER") or getpass.getuser()
    except Exception:
        return "?"


def _tailscale_info() -> dict:
    """Quién controla el demonio Tailscale visible desde esta sesión."""
    import shutil as _sh
    if not _sh.which("tailscale"):
        return {"disponible": False, "controlado": False, "dueno": "", "detalle": "tailscale no en PATH"}
    try:
        r = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=10)
        txt = (r.stdout or "") + (r.stderr or "")
        import re as _re
        m = _re.search(r"already in use by ([^,\)\n]+)", txt)
        if m:
            return {"disponible": True, "controlado": False, "dueno": m.group(1).strip(),
                    "detalle": "demonio gestionado por otro usuario; no emitir up/login desde aquí"}
        if "100." in (r.stdout or ""):
            return {"disponible": True, "controlado": True, "dueno": _usuario_panel(),
                    "detalle": "conectado y controlable"}
        return {"disponible": True, "controlado": False, "dueno": "",
                "detalle": (txt.strip()[:200] or "sin estado")}
    except Exception as e:
        return {"disponible": False, "controlado": False, "dueno": "", "detalle": str(e)[:150]}


def _tareas_estado() -> dict:
    """Qué tareas programadas del árbol existen (Windows)."""
    info = {}
    if sys.platform != "win32":
        return info
    for t in _TAREAS_ARBOL:
        try:
            r = subprocess.run(["schtasks", "/Query", "/TN", t],
                               capture_output=True, timeout=10)
            info[t] = (r.returncode == 0)
        except Exception:
            info[t] = False
    return info


def _descargas_medias() -> list:
    """Instaladores parciales en TEMP (riesgo si se reinicia a medias)."""
    out = []
    tmp = os.getenv("TEMP") or os.getenv("TMP") or "/tmp"
    try:
        import glob as _glob
        for f in _glob.glob(os.path.join(tmp, "OllamaSetup*.exe")):
            try:
                sz = os.path.getsize(f)
                if sz > 1024 * 1024:
                    out.append({"archivo": os.path.basename(f),
                                "mb": round(sz / (1024 * 1024), 1)})
            except Exception:
                pass
    except Exception:
        pass
    return out


@app.get("/api/salud_sesion")
def api_salud_sesion(x_comandante_token: str | None = Header(default=None)):
    """Salud de sesión: usuario del panel, dueño de Tailscale, tareas, disco, Ollama."""
    _authorize(x_comandante_token)
    yo = _usuario_panel()
    ts = _tailscale_info()
    conflicto = bool(ts.get("dueno")) and ts["dueno"].lower() not in (yo.lower(), "")
    disco = None
    try:
        d = shutil.disk_usage(HERE)
        disco = {"libre_gb": round(d.free / (1024 ** 3), 1)}
    except Exception:
        pass
    ollama_ok = False
    try:
        with urllib.request.urlopen("http://localhost:11434/", timeout=3) as r:
            ollama_ok = (r.status == 200)
    except Exception:
        pass
    return {
        "usuario_panel": yo,
        "tailscale": ts,
        "conflicto_cuentas": conflicto,
        "tareas": _tareas_estado(),
        "descargas_medias": _descargas_medias(),
        "disco": disco,
        "ollama": ollama_ok,
    }


@app.post("/api/reinicio_seguro")
def api_reinicio_seguro(x_comandante_token: str | None = Header(default=None)):
    """Detiene descargas y servicios secundarios para un reinicio limpio.

    Detiene la tarea OllamaBg y el servicio ArbolWeb (:8000). NO toca este
    panel (ComandanteWeb) para no cortar la propia respuesta.
    """
    _authorize(x_comandante_token)
    acciones = []
    if sys.platform == "win32":
        for t in ("OllamaBg", "ArbolWeb"):
            try:
                r = subprocess.run(["schtasks", "/End", "/TN", t],
                                   capture_output=True, timeout=15)
                acciones.append(f"tarea {t}: detenida" if r.returncode == 0 else f"tarea {t}: sin cambios")
            except Exception as e:
                acciones.append(f"tarea {t}: error {str(e)[:80]}")
        # Matar solo el worker de web_server (nunca este proceso ni comandante_web)
        try:
            import psutil as _ps
            yo = os.getpid()
            for p in _ps.process_iter(["pid", "cmdline"]):
                try:
                    cmd = " ".join(p.info.get("cmdline") or [])
                    if p.info["pid"] != yo and "web_server" in cmd and "uvicorn" in cmd:
                        p.terminate()
                        acciones.append(f"proceso ArbolWeb pid {p.info['pid']}: terminado")
                except Exception:
                    pass
        except Exception as e:
            acciones.append(f"procesos: {str(e)[:80]}")
    else:
        acciones.append("plataforma no Windows: sin acciones")
    acciones.append("Listo: puedes reiniciar la máquina de forma segura.")
    return {"ok": True, "acciones": acciones}


# --- Frontend -------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/arboles")
def pagina_arboles():
    return FileResponse(os.path.join(STATIC_DIR, "arboles.html"))


@app.get("/campanas")
def pagina_campanas():
    return FileResponse(os.path.join(STATIC_DIR, "campanas.html"))


@app.get("/monitoreo")
def pagina_monitoreo():
    return FileResponse(os.path.join(STATIC_DIR, "monitoreo.html"))


# --- Monitoreo de ramas (tablero) --------------------------------------
PUENTE_URL = os.getenv("PUENTE_URL", "http://127.0.0.1:4210").rstrip("/")


def _puente_get(ruta: str, timeout: int = 15):
    try:
        req = urllib.request.Request(PUENTE_URL + ruta)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@app.get("/api/monitoreo")
def api_monitoreo(x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    estado = _puente_get("/estado")
    pendientes = []
    try:
        pendientes = db_listar_aprobaciones("agencia", estado="pendiente")
    except Exception:
        pendientes = []
    return {"puente": PUENTE_URL, "estado": estado, "gates_pendientes": pendientes}


class AprobacionBody(BaseModel):
    tipo: str = "gate"
    detalle: str = ""
    borrador: str = ""


class ResolverBody(BaseModel):
    decision: str = "aprobada"
    feedback: str = ""


@app.get("/api/aprobaciones")
def api_aprobaciones_listar(x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    try:
        return {"pendientes": db_listar_aprobaciones("agencia", estado="pendiente")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/api/aprobaciones")
def api_aprobacion_crear(body: AprobacionBody, x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    try:
        return db_crear_aprobacion("agencia", body.tipo, body.detalle, body.borrador)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.post("/api/aprobaciones/{aprobacion_id}/resolver")
def api_aprobacion_resolver(aprobacion_id: int, body: ResolverBody,
                            x_comandante_token: str | None = Header(default=None)):
    _authorize(x_comandante_token)
    if body.decision not in ("aprobada", "rechazada"):
        raise HTTPException(status_code=400, detail="decision: aprobada|rechazada")
    try:
        r = db_resolver_aprobacion(aprobacion_id, body.decision, body.feedback)
        if r is None:
            raise HTTPException(status_code=404, detail="no existe")
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("COMANDANTE_WEB_PORT", "8001")))