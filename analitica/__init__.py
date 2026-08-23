"""
Módulo analitica: Rama OBRERA de la colmena — Analista de Datos y KPIs.

Genera reportes y recomendaciones; no modifica presupuesto ni campañas.
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]