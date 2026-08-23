"""
Módulo micelio: agente local de mantenimiento de la colmena (tejido conectivo).

Conecta los árboles, mantiene la estructura, actualiza componentes y responde
al árbol comandante.
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]