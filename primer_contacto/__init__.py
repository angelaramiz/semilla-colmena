"""
Módulo primer_contacto: Departamento de Investigación Previa para Primer Contacto con Clientes

Este paquete contiene 4 agentes especializados que trabajan en orquestación para
auditar la huella digital de una empresa local y generar una propuesta comercial.

Estructura:
- agente.py: Orquestador CrewAI con los 4 agentes
- servidor_mcp.py: Herramientas (tools) disponibles para agentes
- system_prompts/: Backstories de cada agente
- context/: Contexto y reglas globales

Uso:
    from primer_contacto.agente import setup_crew
    crew = setup_crew("local")
    resultado = crew.kickoff(inputs={"negocio": "...", "ciudad": "..."})
"""

__version__ = "1.0.0"
__author__ = "Agencia de Marketing"

from .agente import setup_crew, extract_crew_result, PersistentMCPClient

__all__ = ["setup_crew", "extract_crew_result", "PersistentMCPClient"]
