"""
Módulo atencion_cliente: Rama OBRERA de la colmena — Soporte y Relaciones.

Responde consultas rutinarias y escala quejas (que requieren aprobación humana).
"""

__version__ = "0.1.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]