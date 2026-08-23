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

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db import init_db, listar_arboles as db_listar_arboles, registrar_arbol as db_registrar_arbol
from comunicacion.comandante_mcp import (
    ping_arbol, estado_arbol, ejecutar_comando, propagar_upgrade, propagar_archivo,
)

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


# --- Frontend -------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("COMANDANTE_WEB_PORT", "8001")))