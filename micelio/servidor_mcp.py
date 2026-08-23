# micelio/servidor_mcp.py
"""
MICELIO — Servidor MCP del agente local de mantenimiento (tejido conectivo).

El micelio es el "tejido" que conecta y mantiene los árboles de la colmena:
- Se conecta a los árboles locales y puede leer/modificar sus archivos de estructura.
- Responde al ÁRBOL COMANDANTE (mantenimiento, actualizaciones, reparación).
- Mantiene el sistema: actualiza componentes, repara, propaga cambios.

Herramientas:
- salud_estructura      : verifica que la estructura de archivos del árbol está completa.
- version_componentes   : versión git y ramas presentes.
- actualizar_componentes: actualiza el código (git fetch+reset+uv sync).
- reparar_estructura    : re-crea /shared, DB y manifiesto.
- sincronizar_manifiesto: regenera el manifiesto Trinity desde .env.
- aplicar_parche        : modifica un archivo de estructura (con respaldo).
"""
import os
import sys
import json
import subprocess

from fastmcp import FastMCP
from dotenv import load_dotenv

from core.permisos import rol_tiene_micelio, es_conservante
from core.mision import resumen_mision, mision_json
from db import crear_aprobacion, listar_aprobaciones, resolver_aprobacion

# Raíz del proyecto = parent de micelio/
MICELIO_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(MICELIO_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

ARBOL_ID = os.getenv("ARBOL_ID", "local")
ARBOL_ROL = os.getenv("ARBOL_ROL", "comandante").lower()
mcp = FastMCP("MicelioMantenimiento")


def _deny(herramienta: str):
    return json.dumps({
        "error": 403,
        "detalle": f"el rol '{ARBOL_ROL}' no tiene permiso para '{herramienta}' (solo el CONSERVANTE accede a estructura/código)",
        "rol": ARBOL_ROL,
    }, ensure_ascii=False)


def _requiere(herramienta: str):
    return None if rol_tiene_micelio(ARBOL_ROL, herramienta) else _deny(herramienta)


def _autorizado_para_modificar() -> bool:
    """¿El micelio puede modificar la estructura?
    Solo si (a) el rol es CONSERVANTE (jerarquía más alta) o (b) hay una aprobación
    de mantenimiento aprobada para este árbol. El comandante/heredero NO modifica."""
    if es_conservante(ARBOL_ROL):
        return True
    # Buscar una aprobación de tipo 'mantenimiento' aprobada reciente para este árbol
    try:
        for a in listar_aprobaciones(ARBOL_ID, "aprobada"):
            if a.get("tipo") == "mantenimiento":
                return True
    except Exception:
        pass
    return False


def _deny_autorizacion(herramienta: str):
    return json.dumps({
        "error": 403,
        "detalle": (f"'{herramienta}' requiere autorización del árbol CONSERVANTE. "
                    f"Usa solicitar_permiso_mantenimiento y espera la aprobación. "
                    f"(rol actual: {ARBOL_ROL})"),
        "rol": ARBOL_ROL,
    }, ensure_ascii=False)

ARCHIVOS_CRITICOS = [
    "main.py", "db.py", "auth.py", "web_server.py", "comandante_web.py",
    "core/llm_router.py", "core/clasificador.py", "core/registro_ramas.py",
    "core/manifiesto.py", "orquestador/agente.py", "contenido/agente.py",
    "redes/agente.py", "analitica/agente.py", "investigacion/agente.py",
    "atencion_cliente/agente.py", "planeacion/agente.py",
]


def _log(msg: str):
    print(f"[MICELIO] {msg}", file=sys.stderr)
    sys.stderr.flush()


def _es_tree(ruta: str):
    return os.path.isfile(os.path.join(PROJECT_ROOT, ruta))


@mcp.tool()
def salud_estructura() -> str:
    """Verifica que la estructura de archivos del árbol está completa."""
    e = _requiere("salud_estructura")
    if e:
        return e
    faltantes = [f for f in ARCHIVOS_CRITICOS if not _es_tree(f)]
    dirs = ["shared/borradores", "shared/memoria", "shared/aprobaciones", "shared/reportes"]
    dirs_faltantes = [d for d in dirs if not os.path.isdir(os.path.join(PROJECT_ROOT, d))]
    env_ok = os.path.exists(os.path.join(PROJECT_ROOT, ".env"))
    return json.dumps({
        "arbol_id": ARBOL_ID,
        "archivos_ok": len(ARCHIVOS_CRITICOS) - len(faltantes), "archivos_totales": len(ARCHIVOS_CRITICOS),
        "faltantes": faltantes, "dirs_faltantes": dirs_faltantes,
        "env_presente": env_ok,
        "ok": not faltantes and not dirs_faltantes and env_ok,
    }, ensure_ascii=False)


def _sh(cmd_list: list) -> str:
    try:
        r = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f"error:{e}"


@mcp.tool()
def version_componentes() -> str:
    """Devuelve la versión git y las ramas de la colmena presentes."""
    e = _requiere("version_componentes")
    if e:
        return e
    version = _sh(["git", "rev-parse", "--short", "HEAD"])
    rama = _sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    ramas = [d for d in os.listdir(PROJECT_ROOT)
             if os.path.isdir(os.path.join(PROJECT_ROOT, d))
             and os.path.exists(os.path.join(PROJECT_ROOT, d, "agente.py"))]
    return json.dumps({"arbol_id": ARBOL_ID, "version_git": version or "n/a", "rama": rama or "n/a",
                       "ramas_presentes": sorted(ramas)}, ensure_ascii=False)


@mcp.tool()
def actualizar_componentes(rama_git: str = "main", con_uv_sync: bool = True) -> str:
    """Actualiza el código del árbol (git fetch+reset hard + uv sync opcional)."""
    e = _requiere("actualizar_componentes")
    if e:
        return e
    out = _sh(["git", "fetch", "origin"])
    out += "\n" + _sh(["git", "reset", "--hard", f"origin/{rama_git}"])
    if con_uv_sync and os.path.exists(os.path.join(PROJECT_ROOT, "pyproject.toml")):
        out += "\n" + _sh(["uv", "sync"]) if os.environ.get("PATH", "").find("uv") >= 0 else "\n[sin uv]"
    _log(f"Actualización ejecutada ({rama_git})")
    return json.dumps({"arbol_id": ARBOL_ID, "rama": rama_git, "salida": out[:500],
                       "ok": True}, ensure_ascii=False)


@mcp.tool()
def reparar_estructura() -> str:
    """Repara la estructura: crea /shared, inicializa la DB y regenera el manifiesto.
    Requiere autorización del CONSERVANTE (rol o aprobación de mantenimiento)."""
    if not _autorizado_para_modificar():
        return _deny_autorizacion("reparar_estructura")
    for d in ["shared/borradores", "shared/memoria", "shared/aprobaciones", "shared/reportes"]:
        os.makedirs(os.path.join(PROJECT_ROOT, d), exist_ok=True)
    from db import init_db
    init_db()
    from core.manifiesto import guardar_manifiesto
    import os as _os
    guardar_manifiesto(os.path.join(PROJECT_ROOT, "manifiesto.yaml"),
                       _os.getenv("ARBOL_ID", "local"), rol=_os.getenv("ARBOL_ROL", "obrero"),
                       heredero_de=_os.getenv("ARBOL_HEREDERO_DE", ""))
    return json.dumps({"arbol_id": ARBOL_ID, "reparado": True,
                       "acciones": ["shared", "DB", "manifiesto"]}, ensure_ascii=False)


@mcp.tool()
def sincronizar_manifiesto() -> str:
    """Regenera el manifiesto Trinity desde el .env del árbol. Requiere autorización del CONSERVANTE."""
    if not _autorizado_para_modificar():
        return _deny_autorizacion("sincronizar_manifiesto")
    try:
        from core.manifiesto import guardar_manifiesto
        ruta = guardar_manifiesto(os.path.join(PROJECT_ROOT, "manifiesto.yaml"),
                                  ARBOL_ID, rol=os.getenv("ARBOL_ROL", "obrero"),
                                  heredero_de=os.getenv("ARBOL_HEREDERO_DE", ""))
        return json.dumps({"arbol_id": ARBOL_ID, "manifiesto": ruta, "ok": True}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def aplicar_parche(ruta_relativa: str, contenido: str, respaldar: bool = True) -> str:
    """Modifica un archivo de estructura. Con respaldo (.bak) por defecto.
    ⚠️ Requiere autorización del CONSERVANTE (rol o aprobación de mantenimiento)."""
    if not _autorizado_para_modificar():
        return _deny_autorizacion("aplicar_parche")
    destino = os.path.normpath(os.path.join(PROJECT_ROOT, ruta_relativa))
    if not destino.startswith(PROJECT_ROOT):
        return json.dumps({"error": "ruta fuera del proyecto"}, ensure_ascii=False)
    try:
        if respaldar and os.path.exists(destino):
            with open(destino, "r", encoding="utf-8") as f:
                with open(destino + ".bak", "w", encoding="utf-8") as b:
                    b.write(f.read())
        with open(destino, "w", encoding="utf-8") as f:
            f.write(contenido)
        _log(f"Parche aplicado: {ruta_relativa}")
        return json.dumps({"arbol_id": ARBOL_ID, "archivo": ruta_relativa, "respaldo": respaldar, "ok": True},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# --- MISIÓN y DIAGNÓSTICOS -------------------------------------------------
@mcp.tool()
def mision() -> str:
    """Muestra el objetivo principal de la colmena (misión del micelio y su árbol)."""
    return mision_json()


@mcp.tool()
def diagnostico_self() -> str:
    """Diagnóstico del propio micelio: puede importar, DB, grafo, rol y misión."""
    import importlib
    resultados = {}
    for mod in ["core.llm_router", "core.permisos", "db", "core.mision"]:
        try:
            importlib.import_module(mod)
            resultados[mod] = "ok"
        except Exception as e:
            resultados[mod] = f"error:{e}"
    try:
        from db import init_db
        init_db()
        db_ok = True
    except Exception as e:
        db_ok = str(e)
    try:
        codegraph_ok = os.path.exists(os.path.join(PROJECT_ROOT, ".codegraph", "codegraph.db"))
    except Exception:
        codegraph_ok = False
    return json.dumps({
        "arbol_id": ARBOL_ID, "rol": ARBOL_ROL,
        "imports": resultados, "db": db_ok,
        "codegraph": codegraph_ok,
        "mision": resumen_mision(),
        "sano": all(v == "ok" for v in resultados.values()) and db_ok is True,
    }, ensure_ascii=False)


@mcp.tool()
def diagnostico_arbol() -> str:
    """Diagnóstico del ÁRBOL ASIGNADO: estructura, DB, shared, y conectividad a la red."""
    info = json.loads(salud_estructura())
    conect = json.loads(verificar_conectividad())
    return json.dumps({
        "arbol_id": ARBOL_ID,
        "estructura": info,
        "conectividad": conect,
        "en_buena_salud": info.get("ok", False) and conect.get("en_red", False),
    }, ensure_ascii=False)


@mcp.tool()
def verificar_conectividad() -> str:
    """Comprueba que el árbol está en la red privada y comunicado (tailscale/inventario)."""
    en_red = False
    detalle = "sin herramienta de red detectada"
    # Tailscale
    import shutil
    if shutil.which("tailscale") or shutil.which("tailscale.exe"):
        r = _sh(["tailscale", "status"]) if sys.platform != "win32" else _sh(["tailscale", "status"])
        if r and "Logged out" not in r:
            en_red = True
            detalle = r[:200]
        else:
            detalle = "tailscale presente pero no conectado"
    # Inventario de árboles conocidos (local)
    arboles = []
    try:
        from db import listar_arboles as _lista
        arboles = [a["arbol_id"] for a in _lista()]
    except Exception:
        pass
    return json.dumps({
        "arbol_id": ARBOL_ID,
        "en_red_privada": en_red,
        "detalle": detalle,
        "arboles_conocidos": arboles,
        "comunicado_con_arboles": len(arboles) > 0 or en_red,
    }, ensure_ascii=False)


@mcp.tool()
def solicitar_permiso_mantenimiento(descripcion: str) -> str:
    """Solicita al árbol CONSERVANTE permiso para ejecutar mantenimiento.
    No modifica nada hasta que el conservante apruebe."""
    try:
        res = crear_aprobacion(ARBOL_ID, tipo="mantenimiento", detalle=descripcion)
        _log(f"Solicitud de mantenimiento #{res['id']} enviada al conservante")
        return json.dumps({"arbol_id": ARBOL_ID, "aprobacion": res,
                           "estado": "pendiente_conservante",
                           "mision": resumen_mision()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP del Micelio iniciado (stdio)")
    mcp.run()