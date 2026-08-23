# orquestador/servidor_mcp.py
"""
Servidor MCP del TRONCO (Orquestador).

Expone las herramientas de coordinación de la agencia:
- clasificar_instruccion : clasifica la tarea (rutina/media/critica) y decide gate.
- solicitar_aprobacion   : registra un entregable crítico en la cola humana.
- consultar_aprobacion   : lee el estado de una aprobación.
- resolver_aprobacion    : aprueba/rechaza (lo usa la Directora vía web).
- listar_aprobaciones    : cola pendiente de un árbol.
- guardar_borrador       : escribe un entregable en /shared/borradores.
"""
import os
import sys
import json
import importlib

# Asegurar que la raíz del proyecto esté en sys.path (se ejecuta como subproceso).
ORQ_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ORQ_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastmcp import FastMCP
from dotenv import load_dotenv

from db import crear_aprobacion, listar_aprobaciones, resolver_aprobacion
from core.clasificador import clasificar_instruccion_json
from core.registro_ramas import REGISTRO_RAMAS

load_dotenv()

# Carpeta compartida del árbol (existe por sembrar.sh)
SHARED_DIR = os.getenv("SHARED_DIR", os.path.abspath("shared"))
BORRADORES_DIR = os.path.join(SHARED_DIR, "borradores")
os.makedirs(BORRADORES_DIR, exist_ok=True)

ARBOL_ID = os.getenv("ARBOL_ID", "local")

mcp = FastMCP("TroncoOrquestador")


def _log(msg: str):
    print(f"[TRONCO] {msg}", file=sys.stderr)
    sys.stderr.flush()


# --- Clasificación determinista de complejidad ---------------------------
# Lógica central en core/clasificador.py (palabras que disparan gates).


@mcp.tool()
def clasificar_instruccion(instruccion: str) -> str:
    """Clasifica una instrucción de la Directora: rutina | media | critica.
    'rutina' -> Ollama local, sin aprobación.
    'media'  -> OpenRouter (razonamiento/creatividad), sin aprobación (borrador).
    'critica'-> OpenRouter + REQUIERE aprobación humana antes de ejecutar."""
    return clasificar_instruccion_json(instruccion)


@mcp.tool()
def solicitar_aprobacion(tipo: str, detalle: str, borrador: str = "") -> str:
    """Registra un entregable crítico en la cola de aprobación humana.
    El Tronco NO ejecuta la acción hasta que la Directora apruebe.
    Devuelve el id de la aprobación."""
    try:
        res = crear_aprobacion(ARBOL_ID, tipo, detalle, borrador)
        _log(f"Solicitud de aprobación #{res['id']} ({tipo}) registrada")
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        _log(f"Error en solicitar_aprobacion: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def consultar_aprobacion(aprobacion_id: int) -> str:
    """Consulta el estado de una aprobación: pendiente | aprobada | rechazada."""
    pendientes = listar_aprobaciones(ARBOL_ID)
    for a in pendientes:
        if a["id"] == aprobacion_id:
            return json.dumps(a, ensure_ascii=False)
    # También puede estar resuelta (se guarda en DB igualmente)
    todas = listar_aprobaciones(ARBOL_ID)
    for a in todas:
        if a["id"] == aprobacion_id:
            return json.dumps(a, ensure_ascii=False)
    return json.dumps({"error": "aprobacion no encontrada"}, ensure_ascii=False)


@mcp.tool()
def resolver_aprobacion(aprobacion_id: int, decision: str, feedback: str = "") -> str:
    """Aprueba ('aprobada') o rechaza ('rechazada') una aprobación pendiente."""
    try:
        res = resolver_aprobacion(aprobacion_id, decision, feedback)
        if res is None:
            return json.dumps({"error": "aprobacion no encontrada"}, ensure_ascii=False)
        return json.dumps(res, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        _log(f"Error en resolver_aprobacion: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def listar_aprobaciones_tool(estado: str = "pendiente") -> str:
    """Lista las aprobaciones del árbol, por estado (pendiente por defecto)."""
    try:
        return json.dumps(listar_aprobaciones(ARBOL_ID, estado or None), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def guardar_borrador(nombre: str, contenido: str) -> str:
    """Guarda un entregable (borrador) en /shared/borradores del árbol."""
    try:
        ruta = os.path.join(BORRADORES_DIR, f"{ARBOL_ID}_{nombre}")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        _log(f"Borrador guardado: {ruta}")
        return json.dumps({"ruta": ruta, "ok": True}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def delegar_rama(rama: str, inputs_json: str) -> str:
    """Delega trabajo a una rama obrera (ej. contenido). inputs_json es JSON con
    los campos que la rama consume (ver registro). Devuelve el entregable de la rama."""
    if rama not in REGISTRO_RAMAS:
        return json.dumps({
            "error": f"rama desconocida: {rama}",
            "disponibles": list(REGISTRO_RAMAS),
        }, ensure_ascii=False)
    try:
        inputs = json.loads(inputs_json) if isinstance(inputs_json, str) else inputs_json
    except Exception:
        return json.dumps({"error": "inputs_json inválido (no es JSON)"}, ensure_ascii=False)

    spec = REGISTRO_RAMAS[rama]
    try:
        mod = importlib.import_module(spec["modulo"])
        crew = getattr(mod, spec["funcion_crew"])()
        resultado = crew.kickoff(inputs=inputs)
        entregable = getattr(mod, spec["funcion_extract"])(resultado)
        _log(f"Delegación a rama '{rama}' completada")
        return entregable
    except Exception as e:
        _log(f"Error delegando a {rama}: {e}")
        return json.dumps({
            "error": f"la rama '{rama}' falló: {str(e)[:200]}",
            "sugerencia": "Revisa conectividad LLM (Ollama/OpenRouter) de la rama.",
        }, ensure_ascii=False)


@mcp.tool()
def ejecutar_campana(objetivo: str, inputs_json: str = "{}") -> str:
    """Ejecuta una CAMPAÑA completa: pipeline investigacion→planeacion→creacion→
    exposicion (gate)→analisis. inputs_json: {ciudad, marca, plataformas, audiencia,
    presupuesto, periodo_dias, ...}."""
    from orquestador.campana import ejecutar_campana as _camp
    try:
        inputs = json.loads(inputs_json) if isinstance(inputs_json, str) and inputs_json.strip() else {}
    except Exception:
        inputs = {}
    try:
        _log(f"Campaña iniciada: {objetivo}")
        return json.dumps(_camp(objetivo, inputs), ensure_ascii=False)
    except Exception as e:
        _log(f"Campaña falló: {e}")
        return json.dumps({"error": f"campaña falló: {str(e)[:200]}"}, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP del Tronco iniciado (stdio)")
    mcp.run()