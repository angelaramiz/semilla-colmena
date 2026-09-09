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
import socket
import subprocess
import urllib.request
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from micelio import servidor_mcp as mic
from db import listar_aprobaciones, resolver_aprobacion, listar_arboles
from core import procesos as _proc

_CONS_PROCS_DIR = os.path.abspath("reportes_web")
from core.auto_open import abrir_navegador_si_local

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


@app.get("/api/procesos")
def api_procesos(x_conservante_token: str | None = Header(default=None)):
    """Procesos en ejecución con fases (pestaña global).
    El Conservante no ejecuta auditorías: aquí verás sus operaciones propias
    (parches, upgrades) y el estado de los árboles va en 🌳 Árboles."""
    _authorize(x_conservante_token)
    return {"procesos": _proc.listar(_CONS_PROCS_DIR)}


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


def _ping_host(ip: str, timeout: float = 2.0) -> bool:
    """Verifica si un host responde por ping (TCP port 22 o ICMP fallback)."""
    if not ip:
        return False
    try:
        sock = socket.create_connection((ip, 22), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, OSError):
        pass
    try:
        r = subprocess.run(["ping", "-n", "1", "-w", "1500", ip],
                           capture_output=True, timeout=timeout + 1)
        return r.returncode == 0
    except Exception:
        return False


def _consultar_supabase_arboles() -> list:
    """Consulta la tabla arboles_remotos en Supabase."""
    supa_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supa_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
    if not supa_url or not supa_key:
        return []
    try:
        url = f"{supa_url}/rest/v1/arboles_remotos?select=*&order=created_at.desc"
        req = urllib.request.Request(url, headers={
            "apikey": supa_key,
            "Authorization": f"Bearer {supa_key}",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return []


@app.get("/api/arboles/estado")
def api_arboles_estado(x_conservante_token: str | None = Header(default=None)):
    """Devuelve la lista de árboles con su estado de conexión en tiempo real."""
    _authorize(x_conservante_token)
    arboles = _consultar_supabase_arboles()
    resultado = []
    for a in arboles:
        ip = a.get("ip_tailscale") or a.get("host") or ""
        conectado = _ping_host(ip) if ip else False
        resultado.append({
            "id": a.get("id"),
            "arbol_id": a.get("arbol_id", "?"),
            "nombre": a.get("nombre", ""),
            "rol": a.get("rol", ""),
            "ip": ip,
            "hostname": a.get("hostname", ""),
            "estado_db": a.get("estado", "desconocido"),
            "conectado": conectado,
            "created_at": a.get("created_at", ""),
            "updated_at": a.get("updated_at", ""),
        })
    return resultado


@app.get("/api/token")
def api_token():
    """Devuelve si el token está configurado (solo accesible desde localhost)."""
    # Solo responde si la petición viene de localhost (el panel es local)
    return {"configured": bool(TOKEN), "hint": TOKEN[:8] + "..." if TOKEN else ""}


@app.on_event("startup")
def _startup():
    # Auto-apertura del panel (opt-in por AUTO_OPEN_BROWSER, solo localhost).
    # No toca index(): la inyección de token sigue intacta en el GET /.
    _puerto = int(os.getenv("CONSERVANTE_WEB_PORT", "8002"))
    abrir_navegador_si_local(f"http://127.0.0.1:{_puerto}/", host="127.0.0.1")


@app.get("/")
def index():
    # Inyectar token en el HTML para auto-asignarlo (solo localhost, panel local)
    html_path = os.path.join(STATIC_DIR, "index.html")
    if TOKEN and os.path.exists(html_path):
        from fastapi.responses import HTMLResponse
        html = open(html_path, encoding="utf-8").read()
        # Inyectar token como valor por defecto del input + localStorage
        html = html.replace(
            'id="token" placeholder="X-Conservante-Token"',
            f'id="token" placeholder="X-Conservante-Token" value="{TOKEN}"'
        )
        return HTMLResponse(content=html)
    return FileResponse(html_path)


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