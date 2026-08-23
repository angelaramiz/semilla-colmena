# planeacion/servidor_mcp.py
"""
Servidor MCP de la RAMA PLANEACIÓN (Estratega de Campañas).

Traduce el dossier de investigación en un plan ejecutable: KPIs, público,
calendario editorial y presupuesto. Es el "cerebro" de la campaña.

Herramientas:
- definir_kpis      : define KPIs según el objetivo.
- armar_calendario  : construye el calendario editorial de la campaña.
- definir_publico   : extrae el público objetivo del dossier.
- asignar_presupuesto: reparte el presupuesto por canal.
- guardar_plan      : persiste el plan en /shared.

La rama PRODUCE el plan; no ejecuta (la exposición queda en gate).
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

SHARED_DIR = os.getenv("SHARED_DIR", os.path.abspath("shared"))
PLANES_DIR = os.path.join(SHARED_DIR, "borradores")
os.makedirs(PLANES_DIR, exist_ok=True)

ARBOL_ID = os.getenv("ARBOL_ID", "local")

mcp = FastMCP("RamaPlaneacion")

KPIS_POR_OBJETIVO = {
    "ventas": ["conversiones", "ventas", "CPA", "ROI"],
    "notoriedad": ["alcance", "impresiones", "seguidores", "menciones"],
    "leads": ["leads", "CPL", "tasa de conversion", "costo por lead"],
    "fidelizacion": ["retencion", "recompra", "NPS", "churn"],
}


def _log(msg: str):
    print(f"[PLANEACION] {msg}", file=sys.stderr)
    sys.stderr.flush()


@mcp.tool()
def definir_kpis(objetivo: str) -> str:
    """Define KPIs sugeridos según el objetivo de la campaña."""
    o = objetivo.lower()
    kpis = KPIS_POR_OBJETIVO["ventas"]
    if any(k in o for k in ["notoriedad", "marca", "conocimiento"]):
        kpis = KPIS_POR_OBJETIVO["notoriedad"]
    elif any(k in o for k in ["lead", "registro", "cotizacion"]):
        kpis = KPIS_POR_OBJETIVO["leads"]
    elif any(k in o for k in ["fideliz", "recompra", "cliente"]):
        kpis = KPIS_POR_OBJETIVO["fidelizacion"]
    return json.dumps({"objetivo": objetivo, "kpis": kpis,
                       "recomendacion": "define metas numericas y plazos para cada KPI"},
                      ensure_ascii=False)


@mcp.tool()
def armar_calendario(objetivo: str, periodo_dias: int, plataformas: str) -> str:
    """Construye un calendario editorial por fase de campaña y plataforma."""
    plataformas_list = [p.strip() for p in plataformas.split(",") if p.strip()]
    dias = max(7, min(periodo_dias, 30))
    return json.dumps({
        "objetivo": objetivo,
        "periodo_dias": dias,
        "plataformas": plataformas_list,
        "fases": [
            {"fase": "teaser", "dias": "1-3", "tipo": "expectativa", "frecuencia": "1/dia"},
            {"fase": "lanzamiento", "dias": "4-7", "tipo": "anuncio + oferta", "frecuencia": "2/dia"},
            {"fase": "sostenimiento", "dias": "8+", "tipo": "contenido de valor", "frecuencia": "1/dia"},
        ],
    }, ensure_ascii=False)


@mcp.tool()
def definir_publico(dossier_json: str) -> str:
    """Extrae y define el público objetivo a partir del dossier de investigación."""
    try:
        dossier = json.loads(dossier_json) if isinstance(dossier_json, str) else dossier_json
        audiencia = dossier.get("audiencia_objetivo", dossier.get("tema", "por confirmar"))
    except Exception:
        audiencia = "por confirmar"
    return json.dumps({
        "publico_objetivo": audiencia,
        "segmentacion_sugerida": ["geografica", "demografica", "por interes"],
        "canales_recomendados": dossier.get("canales_clave", []) if isinstance(dossier, dict) else [],
    }, ensure_ascii=False)


@mcp.tool()
def asignar_presupuesto(presupuesto: float, plataformas: str) -> str:
    """Reparte un presupuesto por canal (sugerencia de 60/40)."""
    plataformas_list = [p.strip() for p in plataformas.split(",") if p.strip()] or ["instagram"]
    principal = plataformas_list[0]
    resto = plataformas_list[1:]
    reparto = {}
    if resto:
        reparto[principal] = round(presupuesto * 0.6, 2)
        restante = round(presupuesto * 0.4 / len(resto), 2)
        for p in resto:
            reparto[p] = restante
    else:
        reparto[principal] = presupuesto
    return json.dumps({"presupuesto_total": presupuesto, "reparto": reparto,
                       "nota": "ajusta segun datos de rendimiento (ver analitica)"},
                      ensure_ascii=False)


@mcp.tool()
def guardar_plan(nombre: str, contenido: str) -> str:
    """Guarda el plan de campaña en /shared/borradores del árbol."""
    try:
        ruta = os.path.join(PLANES_DIR, f"{ARBOL_ID}_{nombre}")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        _log(f"Plan guardado: {ruta}")
        return json.dumps({"ruta": ruta, "ok": True}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP de la Rama Planeación iniciado (stdio)")
    mcp.run()