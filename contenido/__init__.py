"""
Módulo contenido: Rama OBRERA de la colmena — Copywriter multiformato.

Produce borradores de contenido por plataforma y audiencia. Solo PRODUCE;
nunca publica (lo decide el Tronco + gate de la Directora).

Estructura:
- agente.py: CrewAI (Copywriter) + herramientas
- servidor_mcp.py: herramientas deterministas (brief, tono, reutilización, validación, borrador)
- system_prompts/contenido.md: backstory de la rama

Uso:
    from contenido.agente import setup_crew
    crew = setup_crew()
    resultado = crew.kickoff(inputs={"tema": "...", "marca": "..."})
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]