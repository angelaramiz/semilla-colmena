# conservante_web.py
"""
CONSERVANTE — Panel web EXCLUSIVO del arquitecto/dev.

Acceso COMPLETO al micelio y a la estructura de los árboles (mantenimiento):
salud, versión, actualizar componentes, reparar estructura, sincronizar manifiesto
y aplicar parches.

Arranque:
    uv run uvicorn conservante_web:app --host 127.0.0.1 --port 8002

Auth: requiere el header `X-Conservante-Token` igual a `CONSERVANTE_WEB_TOKEN`.
Sin token definido, se niega el acceso por defecto (es un panel privilegiado).
"""
import os
import sys
import json

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from micelio import servidor_mcp as mic
from db import listar_aprobaciones, resolver_aprobacion, listar_arboles

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

app = FastAPI(title="Panel del Conservante — Arquitecto/Dev")

TOKEN = os.getenv("CONSERVANTE_WEB_TOKEN", "").strip()
STATIC_DIR = os.path.join(HERE, "conservante_web", "static")


def _authorize(x_conservante_token: str | None):
    # El conservante es privilegiado: si no hay token definido, se niega por defecto.
    if not TOKEN:
        raise HTTPException(status_code=503, detail="CONSERVANTE_WEB_TOKEN no configurado")
    if x_conservante_token != TOKEN:
        raise HTTPException(status_code=401, detail="Token de conservante inválido")


class ParcheBody(BaseModel):
    ruta_relativa: str
    contenido: str


def _codegraph_cmd() -> list:
    import shutil, sys
    if sys.platform == "win32":
        # En Windows el CLI es un shim .cmd en %APPDATA%\npm
        candidates = ["codegraph.cmd", "codegraph.exe", "codegraph"]
        for c in candidates:
            if shutil.which(c):
                return [c]
        # fallback: buscar en el dir npm de roaming
        npm_dir = os.path.join(os.environ.get("APPDATA", ""), "npm")
        for c in ("codegraph.cmd", "codegraph.exe"):
            p = os.path.join(npm_dir, c)
            if os.path.exists(p):
                return [p]
        return []
    return ["codegraph"] if shutil.which("codegraph") else []


@app.get("/api/codegraph")
def api_codegraph(q: str = "", x_conservante_token: str | None = Header(default=None)):
    """Consulta el grafo de código (CodeGraph) del árbol."""
    _authorize(x_conservante_token)
    cmd = _codegraph_cmd()
    if not cmd or not os.path.exists(os.path.join(HERE, ".codegraph", "codegraph.db")):
        return {"query": q, "ok": False, "error": "CodeGraph no disponible (ejecuta codegraph init)"}
    import subprocess
    try:
        r = subprocess.run(cmd + ["explore", q], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, cwd=HERE)
        return {"query": q, "ok": r.returncode == 0, "salida": (r.stdout or r.stderr)[:4000]}
    except Exception as e:
        return {"query": q, "ok": False, "error": str(e)}


@app.get("/api/arbol")
def api_arbol(x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    return json.loads(mic.salud_estructura())


@app.post("/api/reparar")
def api_reparar(x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    return json.loads(mic.reparar_estructura())


@app.post("/api/sincronizar")
def api_sincronizar(x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    return json.loads(mic.sincronizar_manifiesto())


@app.post("/api/actualizar")
def api_actualizar(x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    return json.loads(mic.actualizar_componentes())


@app.post("/api/parche")
def api_parche(body: ParcheBody, x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    return json.loads(mic.aplicar_parche(ruta_relativa=body.ruta_relativa, contenido=body.contenido))


@app.get("/api/arboles")
def api_arboles(x_conservante_token: str | None = Header(default=None)):
    """Lista los árboles de la colmena registrados en la nube (arboles_remotos)."""
    _authorize(x_conservante_token)
    return listar_arboles()


@app.get("/api/arboles/nuevos")
def api_arboles_nuevos(ultimo_id: int = 0, x_conservante_token: str | None = Header(default=None)):
    """Devuelve los árboles 'nacidos' después de ultimo_id (para notificar el nacimiento)."""
    _authorize(x_conservante_token)
    return [a for a in listar_arboles() if a.get("id", 0) > ultimo_id]


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# --- Autorización de mantenimiento (el CONSERVANTE es la jerarquía más alta) ---
# El micelio solicita permiso; el conservante aprueba/rechaza desde aquí.
@app.get("/api/mantenimiento/pendientes")
def mantenimiento_pendientes(x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    return listar_aprobaciones(os.getenv("ARBOL_ID", "local"), "pendiente")


@app.post("/api/mantenimiento/{aprobacion_id}/aprobar")
def mantenimiento_aprobar(aprobacion_id: int, x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    res = resolver_aprobacion(aprobacion_id, "aprobada", "autorizado por conservante")
    if not res:
        raise HTTPException(status_code=404, detail="solicitud no encontrada")
    return res


@app.post("/api/mantenimiento/{aprobacion_id}/rechazar")
def mantenimiento_rechazar(aprobacion_id: int, x_conservante_token: str | None = Header(default=None)):
    _authorize(x_conservante_token)
    res = resolver_aprobacion(aprobacion_id, "rechazada", "denegado por conservante")
    if not res:
        raise HTTPException(status_code=404, detail="solicitud no encontrada")
    return res


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("CONSERVANTE_WEB_PORT", "8002")))