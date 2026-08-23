"""
Módulo redes: Rama OBRERA de la colmena — Community Manager autónomo.

Prepara calendarios y piezas por canal; nunca publica (gate de la Directora).
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]