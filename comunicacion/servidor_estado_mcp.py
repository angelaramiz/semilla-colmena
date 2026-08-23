# comunicacion/servidor_estado_mcp.py
"""
AGENTE DE ESTADO — MCP que corre en cada árbol HIJO.

Expone el estado local del árbol (hostname, ARBOL_ID, versión git, servicio) y
permite aplicar un upgrade local vía git. El Comandante (árbol principal) lo
consulta/ejecuta a través del canal privado (SSH/Tailscale) invocando estos
mismos comandos de forma remota.

Herramientas:
- estado_local     : diagnóstico del propio árbol.
- aplicar_upgrade  : fetch + reset hard + uv sync del repo local.
"""
import os
import sys
import json
import socket
import subprocess

from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

REPO_DIR = os.getenv("REPO_DIR", os.path.abspath("."))
ARBOL_ID = os.getenv("ARBOL_ID", "local")

mcp = FastMCP("AgenteEstadoArbol")


def _sh(cmd: str) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=15).stdout.strip()
    except Exception:
        return "n/a"


@mcp.tool()
def estado_local() -> str:
    """Estado del árbol: hostname, ARBOL_ID, versión git, rama, servicio, uptime."""
    version = _sh(f"cd {REPO_DIR} && git rev-parse --short HEAD 2>/dev/null")
    rama = _sh(f"cd {REPO_DIR} && git rev-parse --abbrev-ref HEAD 2>/dev/null")
    return json.dumps({
        "hostname": socket.gethostname(),
        "arbol_id": ARBOL_ID,
        "version_git": version or "n/a",
        "rama": rama or "n/a",
        "servicio_orquestador": _sh("systemctl is-active orquestador 2>/dev/null"),
        "uptime": _sh("uptime -p"),
    }, ensure_ascii=False)


@mcp.tool()
def aplicar_upgrade(rama: str = "main", con_uv_sync: bool = True) -> str:
    """Aplica un upgrade local vía git (fetch + reset hard + uv sync opcional)."""
    cmd = (f"cd {REPO_DIR} && git fetch origin && git reset --hard origin/{rama}")
    if con_uv_sync:
        cmd += " && (command -v uv && uv sync || echo '[sin uv]')"
    cmd += " && echo UPGRADE_OK"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
    return json.dumps({
        "ok": r.returncode == 0,
        "rama": rama,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
    }, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    mcp.run()