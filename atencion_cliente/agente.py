# atencion_cliente/agente.py
"""
RAMA ATENCIÓN AL CLIENTE — Agente de Soporte y Relaciones.

Obrero de la colmena: clasifica mensajes, responde consultas rutinarias y
escala quejas. Las QUEJAS/confidenciales requieren aprobación de la Directora.
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

from core.llm_router import get_llm, ESTRATEGIA, RUTINA

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
            print(f"\n[MCP Error] Rama Atención al Cliente: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP de la Rama Atención no inicializado"})
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


@tool("clasificar_mensaje_tool")
def clasificar_mensaje_tool(mensaje: Annotated[str, "Mensaje del cliente"]) -> str:
    """Clasifica un mensaje: consulta, queja, venta u otro."""
    return mcp_client.call_tool("clasificar_mensaje", {"mensaje": mensaje})


@tool("buscar_base_conocimiento_tool")
def buscar_base_conocimiento_tool(tema: Annotated[str, "Tema a buscar"]) -> str:
    """Busca una respuesta en la base de conocimiento."""
    return mcp_client.call_tool("buscar_base_conocimiento", {"tema": tema})


@tool("proponer_respuesta_tool")
def proponer_respuesta_tool(mensaje: Annotated[str, "Mensaje a responder"]) -> str:
    """Esboza una respuesta empática para consultas rutinarias."""
    return mcp_client.call_tool("proponer_respuesta", {"mensaje": mensaje})


@tool("escalar_queja_tool")
def escalar_queja_tool(mensaje: Annotated[str, "Mensaje de la queja"],
                       cliente: Annotated[str, "Cliente"] = "") -> str:
    """Registra una queja para escalar (requiere aprobación humana)."""
    return mcp_client.call_tool("escalar_queja", {"mensaje": mensaje, "cliente": cliente})


def setup_crew(modo: str = "local") -> Crew:
    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join(RAMA_DIR, "system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_ate = cargar_prompt("atencion_cliente.md", "Eres el Agente de Soporte de la agencia.")

    soporte = Agent(
        role="Agente de Soporte y Relaciones (Rama Atención al Cliente)",
        goal=("Clasificar mensajes, responder consultas rutinarias con empatía y "
              "escalar quejas. NUNCA responde quejas sin aprobación de la Directora."),
        backstory=prompt_ate,
        llm=get_llm(ESTRATEGIA),
        tools=[clasificar_mensaje_tool, buscar_base_conocimiento_tool, proponer_respuesta_tool, escalar_queja_tool],
        verbose=True,
        allow_delegation=False,
    )

    tarea = Task(
        description=(
            "Atiende al cliente: '{cliente}'.\nMensaje: '{mensaje}'\n\n"
            "Pasos:\n"
            "1. clasificar_mensaje.\n"
            "2. Si es consulta rutinaria: buscar_base_conocimiento y proponer_respuesta "
            "(borrador, no enviar aún).\n"
            "3. Si es QUEJA: escalar_queja (requiere aprobación humana) y NO respondas directamente.\n\n"
            "Responde en JSON estricto: {clasificacion, respuesta_borrador, escalada, requiere_aprobacion}."
        ),
        expected_output="JSON estricto con la gestión del mensaje, sin markdown envolvente.",
        agent=soporte,
    )

    return Crew(agents=[soporte], tasks=[tarea], verbose=True, memory=False)


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