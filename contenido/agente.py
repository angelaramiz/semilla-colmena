# contenido/agente.py
"""
RAMA CONTENIDO — Copywriter y Estratega de Contenido Multiformato.

Obrero de la colmena: produce borradores de contenido por plataforma y audiencia.
Solo PRODUCE; nunca publica (el Tronco + gate de la Directora deciden la publicación).
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
            print(f"\n[MCP Error] Rama Contenido: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP de la Rama Contenido no inicializado"})
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(tool_name, arguments), self.loop
        )
        try:
            result = future.result(timeout=60)
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


@tool("generar_brief_tool")
def generar_brief_tool(
    tema: Annotated[str, "Tema del contenido"],
    marca: Annotated[str, "Nombre de la marca"],
    audiencia: Annotated[str, "Audiencia objetivo"] = "",
    plataformas: Annotated[str, "Plataformas separadas por coma"] = "instagram",
) -> str:
    """Genera el esqueleto de un brief de contenido."""
    return mcp_client.call_tool("generar_brief", {
        "tema": tema, "marca": marca, "audiencia": audiencia, "plataformas": plataformas})


@tool("adaptar_tono_tool")
def adaptar_tono_tool(
    texto: Annotated[str, "Texto a transformar"],
    tono: Annotated[str, "Tono deseado"],
) -> str:
    """Devuelve guía para adaptar un texto a un tono."""
    return mcp_client.call_tool("adaptar_tono", {"texto": texto, "tono": tono})


@tool("reutilizar_contenido_tool")
def reutilizar_contenido_tool(
    pieza: Annotated[str, "Pieza base"],
    plataformas: Annotated[str, "Plataformas separadas por coma"],
) -> str:
    """Mapea una pieza para reutilizarla en varias plataformas."""
    return mcp_client.call_tool("reutilizar_contenido", {"pieza": pieza, "plataformas": plataformas})


@tool("revisar_ortografia_tool")
def revisar_ortografia_tool(
    texto: Annotated[str, "Texto a validar"],
) -> str:
    """Validación básica del texto (longitud, repeticiones, emojis)."""
    return mcp_client.call_tool("revisar_ortografia", {"texto": texto})


@tool("guardar_borrador_tool")
def guardar_borrador_tool(
    nombre: Annotated[str, "Nombre del archivo de borrador"],
    contenido: Annotated[str, "Contenido del entregable"],
) -> str:
    """Guarda el borrador en /shared/borradores (no publica)."""
    return mcp_client.call_tool("guardar_borrador", {"nombre": nombre, "contenido": contenido})


def setup_crew(modo: str = "local") -> Crew:
    """Crea el Crew de la Rama Contenido: un Copywriter que razona con OpenRouter."""

    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(RAMA_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_contenido = cargar_prompt("contenido.md",
                                     "Eres el Copywriter de la agencia de marketing.")

    copywriter = Agent(
        role="Copywriter y Estratega de Contenido Multiformato",
        goal=("Producir borradores de contenido (captions, posts, guiones, emails, blogs) "
              "para la marca, por plataforma y audiencia, conservando la voz de marca."),
        backstory=prompt_contenido,
        llm=get_llm(ESTRATEGIA),   # redacción creativa -> OpenRouter
        tools=[generar_brief_tool, adaptar_tono_tool, reutilizar_contenido_tool,
               revisar_ortografia_tool, guardar_borrador_tool],
        verbose=True,
        allow_delegation=False,
    )

    tarea_contenido = Task(
        description=(
            "Crea contenido para: tema='{tema}', marca='{marca}', audiencia='{audiencia}', "
            "plataformas='{plataformas}', tono='{tono}'.\n\n"
            "Pasos:\n"
            "1. generar_brief para estructurar el encargo.\n"
            "2. Redacta las piezas por plataforma con el tono pedido.\n"
            "3. revisar_ortografia y corrige.\n"
            "4. guardar_borrador cada pieza (nunca publicar).\n\n"
            "Responde en JSON estricto: {plataformas, piezas:[{plataforma, texto}], tono, pendiente_aprobacion:false}."
        ),
        expected_output="JSON estricto con las piezas por plataforma, sin markdown envolvente.",
        agent=copywriter,
    )

    return Crew(agents=[copywriter], tasks=[tarea_contenido], verbose=True, memory=False)


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