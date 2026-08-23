"""
Módulo planeacion: Rama OBRERA de la colmena — Estratega de Campañas.

Traduce el dossier de investigación en un plan ejecutable (KPIs, público,
calendario, presupuesto). Produce el plan; la exposición queda en gate.
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]