# orquestador/agente.py
"""
TRONCO: Agente Orquestador de la agencia autónoma.

Recibe la instrucción de la Directora Humana, la clasifica (rutina/media/critica),
delega a las ramas especializadas y, si es crítica, solicita aprobación antes de ejecutar.

Patrón idéntico a primer_contacto/agente.py (CrewAI + PersistentMCPClient + FastMCP).
"""
import asyncio
import json
import os
import sys
import threading
from typing import Any, Annotated, cast
from io import TextIOBase

from mcp import ClientSession, StdioServerParameters
from mcp.types import TextContent

from crewai import Agent, Task, Crew
from crewai.tools import tool
from dotenv import load_dotenv

from core.llm_router import get_llm, ESTRATEGIA
from core.clasificador import clasificar_instruccion

load_dotenv()

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        cast(TextIOBase, sys.stdout).reconfigure(encoding="utf-8", errors="replace")
        cast(TextIOBase, sys.stderr).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ORQ_DIR = os.path.dirname(os.path.abspath(__file__))


# --- Cliente MCP persistente (coordinación con el Tronco) ---
class PersistentMCPClient:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._start_loop, daemon=True)
        self.session = None
        self.ready_event = threading.Event()
        self.thread.start()
        self.ready_event.wait(timeout=15)

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run_mcp_server())

    async def _run_mcp_server(self):
        from mcp.client.stdio import stdio_client
        servidor_path = os.path.join(ORQ_DIR, "servidor_mcp.py")
        env = os.environ.copy()
        env.setdefault("ARBOL_ID", os.getenv("ARBOL_ID", "local"))
        params = StdioServerParameters(command=sys.executable, args=[servidor_path], env=env)
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.session = session
                    self.loop.call_soon_threadsafe(self.ready_event.set)
                    while self.loop.is_running():
                        await asyncio.sleep(1)
        except Exception as e:
            print(f"\n[MCP Error] Tronco: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP del Tronco no inicializado"})
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(tool_name, arguments), self.loop
        )
        timeout = int(os.getenv("MCP_TOOL_TIMEOUT", "300"))  # delegación puede tardar
        try:
            result = future.result(timeout=timeout)
            if result.content and len(result.content) > 0:
                first = result.content[0]
                if isinstance(first, TextContent):
                    return first.text
                if hasattr(first, "text"):
                    return getattr(first, "text")
                return str(first)
            return json.dumps({"error": "Respuesta vacía del Tronco"})
        except Exception as e:
            return json.dumps({"error": f"Error en herramienta {tool_name}: {str(e)}"})


mcp_client = PersistentMCPClient()


# --- Herramientas para CrewAI ---
@tool("clasificar_instruccion_tool")
def clasificar_tool(
    instruccion: Annotated[str, "Instrucción de la Directora Humana"]
) -> str:
    """Clasifica la instrucción en rutina/media/critica y si requiere aprobación."""
    return json.dumps(clasificar_instruccion(instruccion), ensure_ascii=False)


@tool("solicitar_aprobacion_tool")
def solicitar_aprobacion_tool(
    tipo: Annotated[str, "Tipo de acción: publicar, enviar, responder, gasto, oferta, datos"],
    detalle: Annotated[str, "Descripción de la acción crítica"],
    borrador: Annotated[str, "Borrador/entregable a revisar por la Directora"] = "",
) -> str:
    """Registra una acción crítica en la cola de aprobación humana. NO ejecuta."""
    return mcp_client.call_tool("solicitar_aprobacion", {
        "tipo": tipo, "detalle": detalle, "borrador": borrador})


@tool("consultar_aprobacion_tool")
def consultar_aprobacion_tool(
    aprobacion_id: Annotated[int, "Id de la aprobación"]
) -> str:
    """Consulta el estado de una aprobación (pendiente/aprobada/rechazada)."""
    return mcp_client.call_tool("consultar_aprobacion", {"aprobacion_id": aprobacion_id})


@tool("guardar_borrador_tool")
def guardar_borrador_tool(
    nombre: Annotated[str, "Nombre del archivo de borrador"],
    contenido: Annotated[str, "Contenido del entregable"],
) -> str:
    """Guarda un borrador en /shared/borradores del árbol."""
    return mcp_client.call_tool("guardar_borrador", {"nombre": nombre, "contenido": contenido})


@tool("delegar_rama_tool")
def delegar_rama_tool(
    rama: Annotated[str, "Nombre de la rama obrera (disponibles: contenido)"],
    inputs_json: Annotated[str, "Inputs para la rama en formato JSON"],
) -> str:
    """Delega el trabajo a una rama especializada y devuelve su entregable.
    Ramas disponibles: contenido. Para 'contenido', inputs: {tema, marca, audiencia, plataformas, tono}."""
    return mcp_client.call_tool("delegar_rama", {"rama": rama, "inputs_json": inputs_json})


@tool("ejecutar_campana_tool")
def ejecutar_campana_tool(
    objetivo: Annotated[str, "Objetivo de la campaña (ej. 'Lanzar presencia de Cafe X en Monterrey')"],
    inputs_json: Annotated[str, "Inputs en JSON: ciudad, marca, plataformas, audiencia, presupuesto, periodo_dias"] = "{}",
) -> str:
    """Ejecuta una campaña COMPLETA en pipeline (investigacion→planeacion→creacion→
    exposicion→analisis). Úsala cuando la instrucción sea una CAMPAÑA/lanzamiento."""
    return mcp_client.call_tool("ejecutar_campana", {"objetivo": objetivo, "inputs_json": inputs_json})


def setup_crew(modo: str = "local") -> Crew:
    """Crea el Crew del Tronco: un Orquestador que razona con OpenRouter."""

    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(ORQ_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_orquestador = cargar_prompt(
        "orquestador.md", "Eres el Director de Operaciones de una agencia de marketing autónoma.")

    llm_estrategia = get_llm(ESTRATEGIA)

    orquestador = Agent(
        role="Director de Operaciones de la Agencia (Tronco)",
        goal=("Recibir la instrucción de la Directora Humana, clasificarla, DELEGARLA "
              "a la rama especializada (contenido, etc.) y consolidar el entregable, "
              "solicitando aprobación para cualquier acción crítica."),
        backstory=prompt_orquestador,
        llm=llm_estrategia,
        tools=[clasificar_tool, delegar_rama_tool, ejecutar_campana_tool,
               solicitar_aprobacion_tool, consultar_aprobacion_tool, guardar_borrador_tool],
        verbose=True,
        allow_delegation=True,
    )

    tarea_orquestacion = Task(
        description=(
            "Instrucción de la Directora: '{instruccion}'\n\n"
            "Pasos:\n"
            "1. Llama a clasificar_instruccion_tool para conocer complejidad y gate.\n"
            "2. Si es una CAMPAÑA o lanzamiento (contiene 'campaña'/'lanza'/'lanzamiento'), "
            "usa ejecutar_campana_tool con el objetivo y los inputs disponibles "
            "(ciudad, marca, plataformas, audiencia, presupuesto). Usa el resultado devuelto.\n"
            "3. Si la tarea es de producción de contenido (redactar/copy/posts/guiones), "
            "DELEGA con delegar_rama_tool(rama='contenido', inputs_json={...tema, marca, "
            "audiencia, plataformas, tono...}) y usa el entregable devuelto.\n"
            "4. Si es 'rutina': procesa directamente (resumen/extracción/formateo).\n"
            "5. Si es 'critica': redacta el entregable Y llama a solicitar_aprobacion_tool "
            "con tipo, detalle y borrador. NUNCA ejecutes la acción final.\n\n"
            "Responde en JSON estricto con: clasificacion, entregable, aprobacion, proximos_pasos."
        ),
        expected_output=("JSON estricto: {'clasificacion': {...}, 'entregable': '...', "
                         "'aprobacion': {...|null}, 'proximos_pasos': [...]} sin markdown envolvente."),
        agent=orquestador,
    )

    return Crew(
        agents=[orquestador],
        tasks=[tarea_orquestacion],
        verbose=True,
        memory=False,
    )


def extract_crew_result(output: Any) -> str:
    """Extrae el resultado textual de CrewAI (compatible con varias versiones)."""
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


def clasificar(instruccion: str) -> dict:
    """Clasificación determinista (sin LLM). Útil para pruebas y gates en CLI."""
    return clasificar_instruccion(instruccion)