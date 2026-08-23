# redes/agente.py
"""
RAMA REDES — Community Manager autónomo.

Obrero de la colmena: cura y prepara calendarios editoriales. PREPARA y PROGRAMA
borradores; NUNCA publica (la emisión requiere gate de la Directora).
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
            print(f"\n[MCP Error] Rama Redes: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP de la Rama Redes no inicializado"})
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


@tool("consultar_calendario_tool")
def consultar_calendario_tool(
    periodo_dias: Annotated[int, "Número de días del calendario"],
    plataformas: Annotated[str, "Plataformas separadas por coma"] = "instagram,facebook",
) -> str:
    """Genera un esqueleto de calendario editorial para N días."""
    return mcp_client.call_tool("consultar_calendario", {"periodo_dias": periodo_dias, "plataformas": plataformas})


@tool("validar_hashtags_tool")
def validar_hashtags_tool(
    hashtags: Annotated[str, "Hashtags separados por coma"],
) -> str:
    """Valida el formato de una lista de hashtags."""
    return mcp_client.call_tool("validar_hashtags", {"hashtags": hashtags})


@tool("detectar_tendencias_tool")
def detectar_tendencias_tool(
    categoria: Annotated[str, "Categoría del negocio"] = "",
) -> str:
    """Detecta tendencias vigentes por categoría."""
    return mcp_client.call_tool("detectar_tendencias", {"categoria": categoria})


@tool("programar_post_tool")
def programar_post_tool(
    canal: Annotated[str, "Canal (instagram/facebook/tiktok)"],
    hora: Annotated[str, "Hora de programación (HH:MM)"],
    contenido: Annotated[str, "Contenido del post"],
) -> str:
    """Construye el objeto de programación de un post (no publica)."""
    return mcp_client.call_tool("programar_post", {"canal": canal, "hora": hora, "contenido": contenido})


def setup_crew(modo: str = "local") -> Crew:
    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(RAMA_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_redes = cargar_prompt("redes.md", "Eres el Community Manager de la agencia.")

    cm = Agent(
        role="Community Manager Autónomo (Rama Redes)",
        goal=("Curar contenido y preparar calendarios editoriales por canal, validando "
              "hashtags y detectando tendencias. Solo PREPARA; nunca publica."),
        backstory=prompt_redes,
        llm=get_llm(ESTRATEGIA),
        tools=[consultar_calendario_tool, validar_hashtags_tool, detectar_tendencias_tool, programar_post_tool],
        verbose=True,
        allow_delegation=False,
    )

    tarea = Task(
        description=(
            "Prepara un plan de redes para: marca='{marca}', audiencia='{audiencia}', "
            "plataformas='{plataformas}', periodo_dias='{periodo_dias}', objetivo='{objetivo}'.\n\n"
            "Pasos:\n"
            "1. consultar_calendario para el calendario editorial.\n"
            "2. detectar_tendencias para elegir temas vigentes.\n"
            "3. Propondría 2-3 piezas por canal con su copy; validar_hashtags.\n"
            "4. programar_post para cada pieza (queda PENDIENTE de aprobación; no publicas).\n\n"
            "Responde en JSON estricto: {plan_calendario, piezas:[{canal, fecha, copy, hashtags, requiere_aprobacion:true}], tendencias}."
        ),
        expected_output="JSON estricto con el plan de redes, sin markdown envolvente.",
        agent=cm,
    )

    return Crew(agents=[cm], tasks=[tarea], verbose=True, memory=False)


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