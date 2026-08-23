# micelio/agente.py
"""
MICELIO — Agente local de mantenimiento de la colmena.

Conexión con los árboles locales, mantenimiento de la estructura (actualizar
componentes, reparar, sincronizar manifiesto) y respuesta al árbol comandante.

A diferencia de las ramas de producción, el micelio ejecuta sus herramientas de
mantenimiento EN-PROCESO (import directo), porque opera sobre el propio sistema
local (git, archivos, DB). Evita así el subproceso MCP y sus limitaciones.
"""
import json
import os
import sys
from typing import Any, Annotated, cast
from io import TextIOBase

from crewai import Agent, Task, Crew
from crewai.tools import tool
from dotenv import load_dotenv

from core.llm_router import get_llm, ESTRATEGIA

# Import en-proceso de las herramientas de mantenimiento (sin subproceso MCP)
import micelio.servidor_mcp as _srv

load_dotenv()

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        cast(TextIOBase, sys.stdout).reconfigure(encoding="utf-8", errors="replace")
        cast(TextIOBase, sys.stderr).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MICELIO_DIR = os.path.dirname(os.path.abspath(__file__))


@tool("salud_estructura_tool")
def salud_estructura_tool() -> str:
    """Verifica que la estructura del árbol está completa."""
    return _srv.salud_estructura()


@tool("version_componentes_tool")
def version_componentes_tool() -> str:
    """Devuelve la versión git y las ramas presentes."""
    return _srv.version_componentes()


@tool("actualizar_componentes_tool")
def actualizar_componentes_tool(rama_git: Annotated[str, "Rama git a actualizar"] = "main") -> str:
    """Actualiza el código del árbol (git + uv sync)."""
    return _srv.actualizar_componentes(rama_git=rama_git)


@tool("reparar_estructura_tool")
def reparar_estructura_tool() -> str:
    """Repara /shared, DB y manifiesto."""
    return _srv.reparar_estructura()


@tool("sincronizar_manifiesto_tool")
def sincronizar_manifiesto_tool() -> str:
    """Regenera el manifiesto Trinity desde .env."""
    return _srv.sincronizar_manifiesto()


@tool("aplicar_parche_tool")
def aplicar_parche_tool(ruta_relativa: Annotated[str, "Ruta relativa del archivo"],
                        contenido: Annotated[str, "Nuevo contenido"]) -> str:
    """Modifica un archivo de estructura (con respaldo). Requiere autorización del conservante."""
    return _srv.aplicar_parche(ruta_relativa=ruta_relativa, contenido=contenido)


@tool("mision_tool")
def mision_tool() -> str:
    """Muestra el objetivo principal de la colmena (misión del micelio)."""
    return _srv.mision()


@tool("diagnostico_self_tool")
def diagnostico_self_tool() -> str:
    """Diagnóstico del propio micelio (imports, DB, grafo, rol)."""
    return _srv.diagnostico_self()


@tool("diagnostico_arbol_tool")
def diagnostico_arbol_tool() -> str:
    """Diagnóstico del árbol asignado (estructura + conectividad)."""
    return _srv.diagnostico_arbol()


@tool("verificar_conectividad_tool")
def verificar_conectividad_tool() -> str:
    """Comprueba que el árbol está en la red privada y comunicado con los árboles."""
    return _srv.verificar_conectividad()


@tool("solicitar_permiso_mantenimiento_tool")
def solicitar_permiso_mantenimiento_tool(descripcion: Annotated[str, "Descripción del mantenimiento"]) -> str:
    """Solicita al árbol CONSERVANTE permiso para ejecutar mantenimiento."""
    return _srv.solicitar_permiso_mantenimiento(descripcion=descripcion)


def setup_crew(modo: str = "local") -> Crew:
    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(MICELIO_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_micelio = cargar_prompt("micelio.md", "Eres el agente de mantenimiento del sistema.")

    micelio = Agent(
        role="Agente de Mantenimiento (Micelio de la Colmena)",
        goal=("Mantener y reparar la estructura de los árboles, actualizar componentes "
              "y responder al árbol comandante."),
        backstory=prompt_micelio,
        llm=get_llm(ESTRATEGIA),
        tools=[salud_estructura_tool, version_componentes_tool, actualizar_componentes_tool,
               reparar_estructura_tool, sincronizar_manifiesto_tool, aplicar_parche_tool,
               mision_tool, diagnostico_self_tool, diagnostico_arbol_tool,
               verificar_conectividad_tool, solicitar_permiso_mantenimiento_tool],
        verbose=True,
        allow_delegation=False,
    )

    tarea = Task(
        description=(
            "Instrucción de mantenimiento: '{instruccion}'\n\n"
            "OBJETIVO PRINCIPAL: siempre conectado y operando, siempre en buena salud, "
            "siempre en la red privada comunicado con los árboles. El micelio NO modifica "
            "nada sin autorización del árbol CONSERVANTE.\n\n"
            "1. mision para confirmar el objetivo principal.\n"
            "2. diagnostico_self + diagnostico_arbol para el estado.\n"
            "3. verificar_conectividad para confirmar red privada/comunicación.\n"
            "4. Si hay errores o el árbol no está comunicado: solicitar_permiso_mantenimiento "
            "al CONSERVANTE (NO modifiques antes).\n"
            "5. Solo tras la autorización del conservante: reparar / actualizar / parchear.\n\n"
            "Responde en JSON estricto: {diagnostico, acciones_ejecutadas, autorizacion_pendiente}."
        ),
        expected_output="JSON estricto con el diagnóstico y las acciones de mantenimiento, sin markdown envolvente.",
        agent=micelio,
    )

    return Crew(agents=[micelio], tasks=[tarea], verbose=True, memory=False)


def extract_crew_result(output: Any) -> str:
    for attr in ["raw", "result", "output", "content"]:
        if hasattr(output, attr):
            value = getattr(output, attr)
            if isinstance(value, str):
                return value
            if value is not None:
                return str(value)
    if isinstance(output, dict):
        return json.dumps(output, ensure_ascii=False, indent=2)
    return str(output)