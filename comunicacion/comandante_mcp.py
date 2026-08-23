# comunicacion/comandante_mcp.py
"""
COMANDANTE — MCP del árbol PRINCIPAL.

Controla, diagnostica y propaga upgrades a los árboles HIJO por canal privado
(Tailscale o SSH, puerto 22). Cada árbol hijo está registrado en el inventario
(tabla arboles_remotos) y es alcanzable por hostname de Tailscale / IP + SSH.

Herramientas:
- registrar_arbol    : dar de alta un árbol hijo en el inventario.
- listar_arboles     : inventario de árboles conocidos.
- ping_arbol         : comprobar conectividad SSH (actualiza estado online/offline).
- estado_arbol       : diagnóstico remoto (hostname, versión git, servicio, uptime).
- ejecutar_comando   : ejecutar un comando de control en un árbol hijo.
- propagar_upgrade   : upgrade basado en git (fetch + reset hard + uv sync) en el hijo.
- propagar_archivo   : copiar un archivo (scp) del principal al hijo.

TRANSPORTE: usa los binarios del sistema `ssh`, `scp` (OpenSSH). Requiere que el
Comandante tenga las llaves SSH configuradas (ssh-agent o ~/.ssh/config) para cada hijo.
"""
import os
import sys
import json
import subprocess

from fastmcp import FastMCP
from dotenv import load_dotenv

from db import (
    registrar_arbol as db_registrar,
    listar_arboles as db_listar,
    buscar_arbol,
    marcar_estado,
    exportar_inventario as db_exportar_inventario,
    importar_inventario as db_importar_inventario,
)

load_dotenv()

# En modo DRY_RUN no se ejecuta nada real (para pruebas y revisión de comandos).
DRY_RUN = os.getenv("COMANDANTE_DRY_RUN", "0") == "1"

mcp = FastMCP("ComandanteArboles")

SSH_TIMEOUT = int(os.getenv("SSH_TIMEOUT", "25"))


def _log(msg: str):
    print(f"[COMANDANTE] {msg}", file=sys.stderr)
    sys.stderr.flush()


def _ssh_target(a: dict) -> str:
    return f"{a['usuario']}@{a['host']}"


def _ssh_cmd(a: dict, remote: str) -> list:
    return [
        "ssh", "-p", str(a["puerto"]),
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new",
        _ssh_target(a), remote,
    ]


def _scp_cmd(a: dict, local: str, remote_path: str) -> list:
    return [
        "scp", "-P", str(a["puerto"]),
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        local, f"{_ssh_target(a)}:{remote_path}",
    ]


def _run(cmd: list, timeout: int = SSH_TIMEOUT) -> dict:
    """Ejecuta un comando del sistema. Devuelve dict con ok/rc/stdout/stderr."""
    if DRY_RUN:
        return {"ok": True, "dry_run": True, "cmd": " ".join(cmd),
                "stdout": "", "stderr": "(dry run)"}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "rc": r.returncode,
                "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    except FileNotFoundError:
        return {"ok": False, "error": "ssh/scp no disponible en el PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout tras {timeout}s"}


@mcp.tool()
def registrar_arbol(arbol_id: str, host: str, usuario: str = "root",
                    puerto: int = 22, canal: str = "ssh",
                    nombre: str = "", repo_dir: str = ".") -> str:
    """Registra o actualiza un árbol hijo en el inventario del Comandante.
    `host` debe ser alcanzable por el canal privado (hostname de Tailscale o IP)."""
    try:
        res = db_registrar(arbol_id, host, usuario, puerto, canal, nombre, repo_dir)
        _log(f"Árbol registrado: {arbol_id} @ {host}:{puerto} ({canal})")
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def listar_arboles() -> str:
    """Inventario de árboles conocidos y su último estado."""
    return json.dumps(db_listar(), ensure_ascii=False)


@mcp.tool()
def ping_arbol(arbol_id: str) -> str:
    """Comprueba conectividad SSH con un árbol hijo y actualiza su estado."""
    a = buscar_arbol(arbol_id)
    if not a:
        return json.dumps({"error": f"árbol no registrado: {arbol_id}"}, ensure_ascii=False)
    r = _run(_ssh_cmd(a, "echo pong"))
    if r.get("ok"):
        marcar_estado(arbol_id, "online", r.get("stdout", ""))
    else:
        marcar_estado(arbol_id, "offline", r.get("error") or r.get("stderr") or "")
    return json.dumps({"arbol_id": arbol_id, "r": r, "estado": "online" if r.get("ok") else "offline"},
                      ensure_ascii=False)


@mcp.tool()
def estado_arbol(arbol_id: str) -> str:
    """Diagnóstico remoto de un árbol hijo: hostname, ARBOL_ID, versión git, servicio."""
    a = buscar_arbol(arbol_id)
    if not a:
        return json.dumps({"error": f"árbol no registrado: {arbol_id}"}, ensure_ascii=False)
    remote = (
        f"cd {a['repo_dir']} && echo HOSTNAME=$(hostname) && "
        f"echo ARBOL_ID=$(grep -E '^ARBOL_ID=' .env | cut -d= -f2- 2>/dev/null) && "
        f"echo VERSION=$(git rev-parse --short HEAD 2>/dev/null) && "
        f"echo BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) && "
        f"echo SERVICIO=$(systemctl is-active orquestador 2>/dev/null || echo n/a) && "
        f"echo UPTIME=$(uptime -p)"
    )
    r = _run(_ssh_cmd(a, remote))
    marcar_estado(arbol_id, "online" if r.get("ok") else "offline",
                  r.get("stdout", "") or r.get("error", ""))
    return json.dumps({"arbol_id": arbol_id, "diagnostico": r}, ensure_ascii=False)


@mcp.tool()
def ejecutar_comando(arbol_id: str, comando: str) -> str:
    """Ejecuta un comando de control en un árbol hijo (diagnóstico / mantenimiento).
    ⚠️ Solo para acciones NO irreversibles o de diagnóstico."""
    a = buscar_arbol(arbol_id)
    if not a:
        return json.dumps({"error": f"árbol no registrado: {arbol_id}"}, ensure_ascii=False)
    r = _run(_ssh_cmd(a, comando))
    return json.dumps({"arbol_id": arbol_id, "comando": comando, "r": r}, ensure_ascii=False)


@mcp.tool()
def propagar_upgrade(arbol_id: str, rama: str = "main", con_uv_sync: bool = True) -> str:
    """Propaga un upgrade al árbol hijo vía git: fetch + reset hard + (opcional) uv sync.
    El hijo debe tener el repo clonado y la llave del principal con permisos de pull."""
    a = buscar_arbol(arbol_id)
    if not a:
        return json.dumps({"error": f"árbol no registrado: {arbol_id}"}, ensure_ascii=False)
    remote = (
        f"cd {a['repo_dir']} && git fetch origin && "
        f"git reset --hard origin/{rama} && "
    )
    if con_uv_sync:
        remote += "(command -v uv && uv sync || echo '[sin uv]') && "
    remote += "echo UPGRADE_OK"
    r = _run(_ssh_cmd(a, remote))
    if r.get("ok"):
        marcar_estado(arbol_id, "online", f"upgrade@{rama}")
    return json.dumps({"arbol_id": arbol_id, "rama": rama, "r": r}, ensure_ascii=False)


@mcp.tool()
def propagar_archivo(arbol_id: str, origen_local: str, destino_remoto: str) -> str:
    """Copia un archivo del árbol principal al hijo vía scp (ej. un system_prompt o config)."""
    a = buscar_arbol(arbol_id)
    if not a:
        return json.dumps({"error": f"árbol no registrado: {arbol_id}"}, ensure_ascii=False)
    if not os.path.exists(origen_local):
        return json.dumps({"error": f"archivo local no existe: {origen_local}"}, ensure_ascii=False)
    r = _run(_scp_cmd(a, origen_local, destino_remoto))
    if r.get("ok"):
        marcar_estado(arbol_id, "online", f"scp:{os.path.basename(origen_local)}")
    return json.dumps({"arbol_id": arbol_id, "origen": origen_local,
                       "destino": destino_remoto, "r": r}, ensure_ascii=False)


# --- FAILOVER: HEREDERO DEL COMANDANTE -----------------------------------
@mcp.tool()
def exportar_inventario() -> str:
    """Exporta el inventario completo de árboles (para que un HEREDERO asuma en failover)."""
    return json.dumps(db_exportar_inventario(), ensure_ascii=False)


@mcp.tool()
def importar_inventario(inventario: str) -> str:
    """Reemplaza el inventario local con el del comandante primario (el heredero asume el control)."""
    try:
        registros = json.loads(inventario) if isinstance(inventario, str) else inventario
        res = db_importar_inventario(registros)
        _log(f"Inventario importado: {res}")
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"inventario inválido: {e}"}, ensure_ascii=False)


@mcp.tool()
def reclamar_comandancia(inventario_primario: str = "") -> str:
    """Promueve ESTE nodo a comandante activo (failover del heredero).
    Si se pasa el inventario del primario, lo importa antes. Marca ARBOL_ROL=comandante."""
    try:
        if inventario_primario:
            db_importar_inventario(json.loads(inventario_primario))
        # Persistir el rol promovido en .env (este nodo pasa a ser comandante activo)
        env_path = os.path.abspath(".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env = f.read()
            if "ARBOL_ROL=" in env:
                import re
                env = re.sub(r"^ARBOL_ROL=.*$", "ARBOL_ROL=comandante", env, flags=re.M)
            else:
                env += "\nARBOL_ROL=comandante\n"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env)
        _log("⚠️  Comandancia reclamada: este nodo ahora es el comandante activo")
        return json.dumps({"ok": True, "nodo": "comandante",
                           "arboles": len(db_exportar_inventario())}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log(f"🚀 Comandante iniciado (ssh) | DRY_RUN={DRY_RUN}")
    mcp.run()