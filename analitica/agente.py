# analitica/agente.py
"""
RAMA ANALÍTICA — Analista de Datos y KPIs.

Obrero de la colmena: mide resultados, calcula ROI y detecta anomalías para
recomendar ajustes. Genera reportes; no modifica presupuesto ni campañas.
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
            print(f"\n[MCP Error] Rama Analítica: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP de la Rama Analítica no inicializado"})
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


@tool("extraer_metricas_tool")
def extraer_metricas_tool(metricas_json: Annotated[str, "Métricas en JSON"]) -> str:
    """Normaliza métricas JSON a una tabla plana."""
    return mcp_client.call_tool("extraer_metricas", {"metricas_json": metricas_json})


@tool("calcular_roi_tool")
def calcular_roi_tool(inversion: Annotated[float, "Inversión"], ingresos: Annotated[float, "Ingresos"]) -> str:
    """Calcula el ROI a partir de inversión e ingresos."""
    return mcp_client.call_tool("calcular_roi", {"inversion": inversion, "ingresos": ingresos})


@tool("comparar_periodos_tool")
def comparar_periodos_tool(actual_json: Annotated[str, "Métricas periodo actual"],
                           anterior_json: Annotated[str, "Métricas periodo anterior"]) -> str:
    """Compara métricas de dos periodos."""
    return mcp_client.call_tool("comparar_periodos", {"actual_json": actual_json, "anterior_json": anterior_json})


@tool("detectar_anomalias_tool")
def detectar_anomalias_tool(metricas_json: Annotated[str, "Serie de métricas en JSON"]) -> str:
    """Detecta anomalías básicas en una serie de métricas."""
    return mcp_client.call_tool("detectar_anomalias", {"metricas_json": metricas_json})


def setup_crew(modo: str = "local") -> Crew:
    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(RAMA_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_analitica = cargar_prompt("analitica.md", "Eres el Analista de Datos de la agencia.")

    analista = Agent(
        role="Analista de Datos y KPIs (Rama Analítica)",
        goal=("Medir resultados, calcular ROI, comparar periodos y detectar anomalías "
              "para recomendar ajustes. Solo genera reportes; no modifica presupuesto."),
        backstory=prompt_analitica,
        llm=get_llm(ESTRATEGIA),
        tools=[extraer_metricas_tool, calcular_roi_tool, comparar_periodos_tool, detectar_anomalias_tool],
        verbose=True,
        allow_delegation=False,
    )

    tarea = Task(
        description=(
            "Analiza las métricas de la campaña '{objetivo}' para el periodo '{periodo}'.\n"
            "Métricas (JSON): {metricas_json}\n\n"
            "Pasos:\n"
            "1. extraer_metricas para normalizar.\n"
            "2. calcular_roi con inversion e ingresos si están disponibles.\n"
            "3. Si hay periodo anterior, comparar_periodos.\n"
            "4. detectar_anomalias y comenta.\n"
            "5. Redacta el reporte con recomendaciones ACCIONABLES.\n\n"
            "Responde en JSON estricto: {kpis, roi, variacion, anomalias, recomendaciones}."
        ),
        expected_output="JSON estricto con el reporte de análisis, sin markdown envolvente.",
        agent=analista,
    )

    return Crew(agents=[analista], tasks=[tarea], verbose=True, memory=False)


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