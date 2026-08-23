# agente.py
import asyncio
import json
import os
import sys
from typing import cast, Any, Annotated
from io import TextIOBase

from mcp import ClientSession, StdioServerParameters
from mcp.types import TextContent

from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from dotenv import load_dotenv

load_dotenv()

# 🛡️ Forzar UTF-8 en Windows para evitar crashes con emojis en subprocess
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        cast(TextIOBase, sys.stdout).reconfigure(encoding="utf-8", errors="replace")  # type: ignore
        cast(TextIOBase, sys.stderr).reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass

# --- Configuración del LLM (Local o Cloud) ---
def get_local_llm(modo: str) -> LLM:
    """Retorna LLM configurado para Ollama con verificación CORRECTA de URLs"""
    
    # Separar URLs: nativa para healthcheck, OpenAI-compatible para CrewAI
    ollama_native = "http://localhost:11434"           # Para /api/tags
    ollama_compatible = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")  # Para CrewAI
    
    if modo == "produccion":
        model = "qwen3-coder-next:cloud"
    else:
        model = os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
    
    # Verificación usando la API NATIVA (endpoint correcto: /api/tags)
    try:
        import urllib.request
        urllib.request.urlopen(f"{ollama_native}/api/tags", timeout=3)
        print(f"✅ Ollama conectado | Modelo: {model}")
    except Exception as e:
        print(f"\n⚠️ CRÍTICO: No se puede conectar a Ollama en {ollama_native}")
        print(f"🔍 Error: {e}")
        print("👉 Verifica: curl http://localhost:11434/api/tags")
        import sys
        sys.exit(1)
        
    # Retornar configuración para CrewAI (usa URL OpenAI-compatible)
    return LLM(
        model=model,
        base_url=ollama_compatible,  # CrewAI necesita /v1
        api_key="not-needed",
        temperature=0.01,   # Llama 3.1: bajo para tool-calling estable
        top_p=0.9,
        timeout=120,
        max_tokens=2048
    )


import threading

# --- Conexión MCP Persistente y Segura ---
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
        from mcp.client.stdio import stdio_client, StdioServerParameters
        params = StdioServerParameters(command="python", args=["servidor_mcp.py"])
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.session = session
                    self.loop.call_soon_threadsafe(self.ready_event.set)
                    # Mantener conexión abierta mientras el loop corra
                    while self.loop.is_running():
                        await asyncio.sleep(1)
        except Exception as e:
            print(f"\n[MCP Error] Fallo al iniciar servidor: {e}")
            self.loop.call_soon_threadsafe(self.ready_event.set)

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self.session:
            return json.dumps({"error": "Servidor MCP no inicializado correctamente"})
            
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(tool_name, arguments), self.loop
        )
        try:
            result = future.result(timeout=60)
            if result.content and len(result.content) > 0:
                first_item = result.content[0]
                if isinstance(first_item, TextContent):
                    return first_item.text
                elif hasattr(first_item, 'text'):
                    return getattr(first_item, 'text')
                return str(first_item)
            return json.dumps({"error": "Respuesta vacía del servidor MCP"})
        except Exception as e:
            return json.dumps({"error": f"Error en herramienta {tool_name}: {str(e)}"})

# Instancia global (se inicializa solo una vez)
mcp_client = PersistentMCPClient()


# --- Herramientas para CrewAI ---
@tool("buscar_negocio_huella")
def buscar_negocio_tool(
    nombre: Annotated[str, "Nombre exacto del negocio a auditar"],
    ciudad: Annotated[str, "Ciudad y estado, ej: 'Monterrey, Nuevo León'"]
) -> str:
    """Busca la información digital pública de un negocio local en Google Maps"""
    return mcp_client.call_tool("buscar_negocio", {"nombre": nombre, "ciudad": ciudad})


@tool("verificar_redes_huella")
def verificar_redes_tool(
    nombre_negocio: Annotated[str, "Nombre exacto del negocio para buscar en Instagram/Facebook. NO incluir ciudad, NO incluir teléfono, NO incluir dirección."]
) -> str:
    """Verifica si existen perfiles públicos de Instagram y Facebook para el negocio (solo requiere el nombre)"""
    return mcp_client.call_tool("verificar_redes", {"nombre_negocio": nombre_negocio})

@tool("buscar_competidores_huella")
def buscar_competidores_tool(
    categoria: Annotated[str, "Categoría del negocio (ej. 'dentista', 'restaurante')"],
    ciudad: Annotated[str, "Ciudad"]
) -> str:
    """Busca competidores directos en la ciudad para análisis comparativo"""
    return mcp_client.call_tool("buscar_competidores", {"categoria": categoria, "ciudad": ciudad})

@tool("buscar_presencia_web")
def buscar_presencia_web_tool(
    query: Annotated[str, "Nombre del negocio y ciudad"]
) -> str:
    """Busca menciones, noticias y reputación general del negocio en la web"""
    return mcp_client.call_tool("buscar_presencia_web", {"query": query})

def setup_crew(modo: str) -> Crew:
    # --- Cargar Contextos de Agentes (System Prompts) ---
    def cargar_prompt(nombre_archivo: str, default: str) -> str:
        ruta = os.path.join("system_prompts", nombre_archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return f.read().strip()
        return default

    prompt_investigador = cargar_prompt("investigador.md", "Eres un investigador digital implacable.")
    prompt_auditor = cargar_prompt("auditor.md", "Eres un Auditor de Huella Digital hiper-técnico para PYMES en México y LatAm.")
    prompt_analista = cargar_prompt("analista.md", "Eres un Analista de Competencia B2B despiadado.")
    prompt_supervisor = cargar_prompt("supervisor.md", "Eres el Director de Estrategia de una exitosa Agencia de Marketing.")

    # También cargamos las reglas de negocio generales (Score, etc.) si existen
    reglas_generales = ""
    ruta_reglas = os.path.join("context", "reglas_auditor.md")
    if os.path.exists(ruta_reglas):
        with open(ruta_reglas, "r", encoding="utf-8") as f:
            reglas_generales = f"\n\n--- REGLAS GENERALES Y SCORE ---\n{f.read()}"

    # --- Agentes ---
    llm = get_local_llm(modo)

    investigador_marca = Agent(
        role="Investigador de Identidad Corporativa",
        goal="Encontrar menciones, reputación y presencia general en la web para {negocio} en {ciudad}",
        backstory=prompt_investigador + reglas_generales,
        llm=llm,
        tools=[buscar_presencia_web_tool],
        verbose=True,
        allow_delegation=False
    )

    auditor_huella = Agent(
        role="Auditor de Huella Digital para PYMES",
        goal="Auditar técnicamente Google Maps y Redes Sociales de {negocio}",
        backstory=prompt_auditor + reglas_generales,
        llm=llm,
        tools=[buscar_negocio_tool, verificar_redes_tool],
        verbose=True,
        allow_delegation=False
    )

    analista_competencia = Agent(
        role="Analista de Competencia Local",
        goal="Analizar a 3 competidores directos de la categoría de {negocio} en {ciudad}",
        backstory=prompt_analista + reglas_generales,
        llm=llm,
        tools=[buscar_competidores_tool],
        verbose=True,
        allow_delegation=False
    )

    estratega_supervisor = Agent(
        role="Ingeniero de Automatización y Director Comercial",
        goal="Sintetizar la investigación, auditar hallazgos, compararlos con la competencia y generar un reporte triple JSON",
        backstory=prompt_supervisor + reglas_generales,
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    # --- Tareas ---
    tarea_investigacion = Task(
        description="Investiga la presencia web general (noticias, directorios) de '{negocio}' en '{ciudad}'. {recursos_extra} Retorna un resumen de reputación.",
        expected_output="Resumen de menciones web y reputación.",
        agent=investigador_marca
    )

    tarea_auditoria = Task(
        description="Audita '{negocio}' en '{ciudad}'. {recursos_extra}\n1. Usa Google Maps.\n2. Verifica Instagram y Facebook.\nAsigna un Score tentativo.",
        expected_output="Auditoría detallada de Mapas y Redes con puntos fuertes y débiles.",
        agent=auditor_huella
    )

    tarea_competencia = Task(
        description="Descubre qué categoría es '{negocio}' e investiga a 3 competidores directos en '{ciudad}'. Analiza sus ratings y reseñas.",
        expected_output="Perfil de los 3 mejores competidores locales.",
        agent=analista_competencia
    )

    tarea_supervision = Task(
        description=(
            "Revisa la investigación, la auditoría y el reporte de competencia.\n"
            "Redacta un reporte en JSON estricto dividido en 3 bloques:\n"
            "1. cliente_gancho: score (0-100), resumen_ejecutivo, puntos_dolor_urgentes (lista), plataformas_encontradas (objeto con instagram, facebook, sitio_web, google_maps como booleanos)\n"
            "2. interno_mercadologa: analisis_competencia, estrategia_recomendada, servicios_a_ofrecer (lista)\n"
            "3. interno_ingeniero: viabilidad_automatizacion, flujos_n8n_sugeridos (lista)\n"
        ),
        expected_output="JSON estricto con estructura: { 'cliente_gancho': {'plataformas_encontradas': {}}, 'interno_mercadologa': {}, 'interno_ingeniero': {} } sin markdown envolvente.",
        agent=estratega_supervisor,
        context=[tarea_investigacion, tarea_auditoria, tarea_competencia]
    )

    # Configuración de memoria dinámica condicional (Producción = True, Local = False)
    usar_memoria = True if modo == "produccion" else False
    
    # Configurar el embedder local y el LLM de memoria
    # El LLM de memoria de CrewAI usa LiteLLM (OpenAI por defecto). Al sobreescribir las variables
    # enviamos las peticiones de memoria ("gpt-4o-mini" fallback) hacia Ollama (Qwen).
    if usar_memoria:
        os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"
        os.environ["OPENAI_API_KEY"] = "NA"
        
        # Mapear gpt-4o-mini y gpt-4o a nuestro modelo para evitar fallos de conexión (Error 404)
        try:
            import importlib
            litellm = importlib.import_module("litellm")
            mem_model = "qwen3-coder-next:cloud" if modo == "produccion" else os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
            litellm.model_alias_map["gpt-4o-mini"] = mem_model
            litellm.model_alias_map["gpt-4o"] = mem_model
            print(f"🧠 Memoria configurada | Mapeo LiteLLM gpt-4o-mini -> {mem_model}")
        except Exception as e:
            print(f"⚠️ Error al configurar alias de memoria: {e}")
            
        embedder_config = {
            "provider": "ollama",
            "config": {
                "model_name": "nomic-embed-text"
            }
        }
    else:
        embedder_config = None

    return Crew(
        agents=[investigador_marca, auditor_huella, analista_competencia, estratega_supervisor],
        tasks=[tarea_investigacion, tarea_auditoria, tarea_competencia, tarea_supervision],
        verbose=True,
        memory=usar_memoria,
        embedder=embedder_config
    )



# --- Función helper para extraer resultado de CrewAI (compatible con múltiples versiones) ---
def extract_crew_result(output: Any) -> str:
    """Extrae el resultado textual de CrewAI de forma compatible con varias versiones"""
    # Intentar atributos comunes en orden de prioridad
    for attr in ["raw", "result", "output", "content"]:
        if hasattr(output, attr):
            value = getattr(output, attr)
            if isinstance(value, str):
                return value
            if value is not None:
                return str(value)
    
    # Fallback: convertir a string o JSON
    if isinstance(output, dict):
        return json.dumps(output, ensure_ascii=False, indent=2)
    return str(output)


if __name__ == "__main__":
    import argparse
    
    # 🛡️ Fix de encoding para Windows + subprocess
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
        try:
            cast(TextIOBase, sys.stdout).reconfigure(encoding="utf-8", errors="replace")  # type: ignore
            cast(TextIOBase, sys.stderr).reconfigure(encoding="utf-8", errors="replace")  # type: ignore
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Auditor de Huella Digital")
    parser.add_argument("--negocio", "-n", type=str, default=None)
    parser.add_argument("--ciudad", "-c", type=str, default=None)
    parser.add_argument("--sitio", type=str, default="")
    parser.add_argument("--ig", type=str, default="")
    parser.add_argument("--fb", type=str, default="")
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--modo", "-m", type=str, choices=["local", "produccion"], default="local")
    parser.add_argument("--interactive", "-i", action="store_true")
    args = parser.parse_args()

    # Modo interactivo opcional
    if args.interactive or not args.negocio or not args.ciudad:
        print("\n🔍 Modo Interactivo")
        if not args.negocio: 
            args.negocio = input("📛 Negocio: ").strip()
        if not args.ciudad: 
            args.ciudad = input("📍 Ciudad: ").strip()

    if not args.negocio or not args.ciudad:
        print("❌ Se requiere --negocio y --ciudad")
        sys.exit(1)

    recursos = []
    if args.sitio: recursos.append(f"Sitio Web: {args.sitio}")
    if args.ig: recursos.append(f"Instagram: {args.ig}")
    if args.fb: recursos.append(f"Facebook: {args.fb}")
    recursos_extra = f"Recursos provistos directamente por el cliente: {', '.join(recursos)}." if recursos else ""

    inputs = {"negocio": args.negocio, "ciudad": args.ciudad, "recursos_extra": recursos_extra}
    
    print(f"🔍 Iniciando auditoría para: {args.negocio} en {args.ciudad} (Modo: {args.modo.upper()})")
    print("-" * 60)
    
    crew = setup_crew(args.modo)

    try:
        resultado = crew.kickoff(inputs=inputs)
        reporte = extract_crew_result(resultado)
        
        print("\n" + "=" * 60)
        print("📋 REPORTE DE AUDITORÍA")
        print("=" * 60)
        print(reporte)
        print("\n[END_OF_JSON_REPORT]")
        
        if args.output:
            os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
            reporte_dict = json.loads(reporte) if isinstance(reporte, str) else reporte
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(reporte_dict, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Guardado en: {args.output}")
            
    except KeyboardInterrupt:
        print("\n⚠️ Cancelado por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)