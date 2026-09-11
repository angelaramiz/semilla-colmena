# investigacion/agente.py
"""
RAMA INVESTIGACIÓN — Analista de Mercado y Competencia.

Obrero de la colmena: investiga audiencia, competencia y tendencias. Solo lectura;
produce dossiers e informes.
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
            print(f"\n[MCP Error] Rama Investigación: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP de la Rama Investigación no inicializado"})
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


@tool("buscar_mercado_tool")
def buscar_mercado_tool(tema: Annotated[str, "Tema de mercado"], ciudad: Annotated[str, "Ciudad"] = "") -> str:
    """Devuelve un dossier de mercado para un tema y ciudad."""
    return mcp_client.call_tool("buscar_mercado", {"tema": tema, "ciudad": ciudad})


@tool("analizar_competencia_tool")
def analizar_competencia_tool(categoria: Annotated[str, "Categoría"],
                              ciudad: Annotated[str, "Ciudad"] = "") -> str:
    """Devuelve un perfil de competidores directos."""
    return mcp_client.call_tool("analizar_competencia", {"categoria": categoria, "ciudad": ciudad})


@tool("detectar_tendencias_tool")
def detectar_tendencias_tool(categoria: Annotated[str, "Categoría"] = "") -> str:
    """Detecta tendencias de muestra por categoría."""
    return mcp_client.call_tool("detectar_tendencias", {"categoria": categoria})


def setup_crew(modo: str = "local") -> Crew:
    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(RAMA_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_inv = cargar_prompt("investigacion.md", "Eres el Analista de Mercado de la agencia.")

    investigador = Agent(
        role="Analista de Mercado y Competencia (Rama Investigación)",
        goal=("Investigar audiencia, competencia y tendencias para fundamentar "
              "decisiones de marketing. Solo lectura; produce dossiers."),
        backstory=prompt_inv,
        llm=get_llm(ESTRATEGIA),
        tools=[buscar_mercado_tool, analizar_competencia_tool, detectar_tendencias_tool],
        verbose=True,
        allow_delegation=False,
    )

    tarea = Task(
        description=(
            "Investiga el mercado para: tema='{tema}', ciudad='{ciudad}', categoria='{categoria}'.\n\n"
            "Pasos:\n"
            "1. buscar_mercado para el dossier.\n"
            "2. analizar_competencia para el perfil comparativo.\n"
            "3. detectar_tendencias para oportunidades.\n"
            "4. Sintetiza el informe con oportunidades y riesgos.\n\n"
            "Responde en JSON estricto: {dossier_mercado, competencia, tendencias, oportunidades, riesgos}."
        ),
        expected_output="JSON estricto con el informe de investigación, sin markdown envolvente.",
        agent=investigador,
    )

    return Crew(agents=[investigador], tasks=[tarea], verbose=True, memory=False)


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