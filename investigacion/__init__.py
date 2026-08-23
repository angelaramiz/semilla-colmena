"""
Módulo investigacion: Rama OBRERA de la colmena — Analista de Mercado y Competencia.

Solo lectura; produce dossiers e informes.
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]