# planeacion/agente.py
"""
RAMA PLANEACIÓN — Estratega de Campañas.

Obrero de la colmena: traduce el dossier de investigación en un plan ejecutable
(KPIs, público, calendario editorial, presupuesto). Produce el plan; la exposición
queda en gate.
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

load_dotenv()

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        cast(TextIOBase, sys.stdout).reconfigure(encoding="utf-8", errors="replace")
        cast(TextIOBase, sys.stderr).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAMA_DIR = os.path.dirname(os.path.abspath(__file__))


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
        servidor_path = os.path.join(RAMA_DIR, "servidor_mcp.py")
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
            print(f"\n[MCP Error] Rama Planeación: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP de la Rama Planeación no inicializado"})
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(tool_name, arguments), self.loop
        )
        try:
            result = future.result(timeout=int(os.getenv("MCP_TOOL_TIMEOUT", "300")))
            if result.content and len(result.content) > 0:
                first = result.content[0]
                if isinstance(first, TextContent):
                    return first.text
                if hasattr(first, "text"):
                    return getattr(first, "text")
                return str(first)
            return json.dumps({"error": "Respuesta vacía"})
        except Exception as e:
            return json.dumps({"error": f"Error en herramienta {tool_name}: {str(e)}"})


mcp_client = PersistentMCPClient()


@tool("definir_kpis_tool")
def definir_kpis_tool(objetivo: Annotated[str, "Objetivo de la campaña"]) -> str:
    """Define KPIs sugeridos según el objetivo."""
    return mcp_client.call_tool("definir_kpis", {"objetivo": objetivo})


@tool("armar_calendario_tool")
def armar_calendario_tool(objetivo: Annotated[str, "Objetivo"],
                          periodo_dias: Annotated[int, "Días de campaña"],
                          plataformas: Annotated[str, "Plataformas (coma)"]) -> str:
    """Construye el calendario editorial por fases."""
    return mcp_client.call_tool("armar_calendario", {"objetivo": objetivo, "periodo_dias": periodo_dias, "plataformas": plataformas})


@tool("definir_publico_tool")
def definir_publico_tool(dossier_json: Annotated[str, "Dossier de investigación (JSON)"]) -> str:
    """Extrae el público objetivo del dossier."""
    return mcp_client.call_tool("definir_publico", {"dossier_json": dossier_json})


@tool("asignar_presupuesto_tool")
def asignar_presupuesto_tool(presupuesto: Annotated[float, "Presupuesto"],
                             plataformas: Annotated[str, "Plataformas (coma)"]) -> str:
    """Reparte el presupuesto por canal."""
    return mcp_client.call_tool("asignar_presupuesto", {"presupuesto": presupuesto, "plataformas": plataformas})


@tool("guardar_plan_tool")
def guardar_plan_tool(nombre: Annotated[str, "Nombre del archivo"], contenido: Annotated[str, "Contenido del plan"]) -> str:
    """Guarda el plan en /shared/borradores."""
    return mcp_client.call_tool("guardar_plan", {"nombre": nombre, "contenido": contenido})


def setup_crew(modo: str = "local") -> Crew:
    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(RAMA_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_plan = cargar_prompt("planeacion.md", "Eres el Estratega de Campañas de la agencia.")

    estratega = Agent(
        role="Estratega de Campañas (Rama Planeación)",
        goal=("Traducir el dossier de investigación en un plan de campaña ejecutable: "
              "KPIs, público objetivo, calendario editorial y reparto de presupuesto."),
        backstory=prompt_plan,
        llm=get_llm(ESTRATEGIA),
        tools=[definir_kpis_tool, armar_calendario_tool, definir_publico_tool,
               asignar_presupuesto_tool, guardar_plan_tool],
        verbose=True,
        allow_delegation=False,
    )

    tarea = Task(
        description=(
            "Elabora el PLAN de campaña para: objetivo='{objetivo}', ciudad='{ciudad}', "
            "presupuesto='{presupuesto}'.\nDossier de investigación (JSON): {dossier_json}\n\n"
            "Pasos:\n"
            "1. definir_kpis según el objetivo.\n"
            "2. definir_publico a partir del dossier.\n"
            "3. armar_calendario con las fases (teaser/lanzamiento/sostenimiento).\n"
            "4. asignar_presupuesto por canal.\n"
            "5. guardar_plan y devuelve el plan consolidado.\n\n"
            "Responde en JSON estricto: {objetivo, kpis, publico, calendario, presupuesto, canales}."
        ),
        expected_output="JSON estricto con el plan de campaña, sin markdown envolvente.",
        agent=estratega,
    )

    return Crew(agents=[estratega], tasks=[tarea], verbose=True, memory=False)


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