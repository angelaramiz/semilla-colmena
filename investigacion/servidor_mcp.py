# investigacion/servidor_mcp.py
"""
Servidor MCP de la RAMA INVESTIGACIÓN (Analista de Mercado y Competencia).

Herramientas de apoyo para el agente (solo LECTURA; no alteran nada):
- buscar_mercado        : dossier de mercado (placeholder; integrar APIs de datos reales).
- analizar_competencia  : perfil de competidores (placeholder).
- detectar_tendencias   : tendencias de muestra.

La rama PRODUCE dossiers e informes; no ejecuta acciones.
"""
import os
import sys
import json

from fastmcp import FastMCP
from dotenv import load_dotenv

ORQ_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ORQ_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

mcp = FastMCP("RamaInvestigacion")


def _log(msg: str):
    print(f"[INVESTIGACION] {msg}", file=sys.stderr)
    sys.stderr.flush()


@mcp.tool()
def buscar_mercado(tema: str, ciudad: str = "") -> str:
    """Dossier de mercado: tamaño, audiencia y canales clave. (Placeholder.)"""
    return json.dumps({
        "tema": tema, "ciudad": ciudad or "general",
        "audiencia_objetivo": "por confirmar con datos de la API",
        "canales_clave": ["Google", "Instagram", "TikTok", "Email"],
        "competidores_detectados": 3,
        "fuente": "placeholder — conectar SerpAPI/Google Places para datos reales",
    }, ensure_ascii=False)


@mcp.tool()
def analizar_competencia(categoria: str, ciudad: str = "") -> str:
    """Perfil de competidores directos. (Placeholder.)"""
    return json.dumps({
        "categoria": categoria, "ciudad": ciudad or "general",
        "competidores": [
            {"nombre": f"Competidor 1 de {categoria}", "rating": 4.5, "resenas": 120, "presencia": ["instagram", "web"]},
            {"nombre": f"Competidor 2 de {categoria}", "rating": 4.2, "resenas": 80, "presencia": ["facebook"]},
            {"nombre": f"Competidor 3 de {categoria}", "rating": 4.0, "resenas": 45, "presencia": ["google_maps"]},
        ],
        "fuente": "placeholder — usar Google Places/SerpAPI para datos reales",
    }, ensure_ascii=False)


@mcp.tool()
def detectar_tendencias(categoria: str = "") -> str:
    """Tendencias de muestra por categoría. (Placeholder.)"""
    return json.dumps({
        "categoria": categoria or "general",
        "tendencias": [
            {"tema": "personalización y experiencia local", "madurez": "creciente"},
            {"tema": "sostenibilidad y transparencia", "madurez": "creciente"},
            {"tema": "comercio conversacional (WhatsApp)", "madurez": "estable"},
        ],
        "fuente": "placeholder",
    }, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP de la Rama Investigación iniciado (stdio)")
    mcp.run()