"""
Módulo orquestador: El TRONCO de la agencia autónoma.

Recibe la instrucción de la Directora Humana, la clasifica (rutina/media/critica),
delega a las ramas y consolida el entregable, solicitando aprobación para lo crítico.

Estructura:
- agente.py: CrewAI (Tronco) + clasificación determinista
- servidor_mcp.py: herramientas de coordinación (cola de aprobación, borradores)
- system_prompts/orquestador.md: backstory del Tronco

Uso:
    from orquestador.agente import clasificar, setup_crew
    print(clasificar("publica la campaña"))   # → critica + gate
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result, clasificar

__all__ = ["setup_crew", "extract_crew_result", "clasificar"]