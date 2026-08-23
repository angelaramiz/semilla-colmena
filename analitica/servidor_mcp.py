# analitica/servidor_mcp.py
"""
Servidor MCP de la RAMA ANALÍTICA (Analista de KPIs).

Herramientas de apoyo deterministas para el agente:
- extraer_metricas  : parsea métricas (JSON) y las normaliza a tabla.
- calcular_roi      : calcula retorno sobre inversión.
- comparar_periodos : compara métricas de dos periodos.
- detectar_anomalias: detección básica de anomalías (desviación simple).

La rama genera REPORTES y recomendaciones; no modifica presupuesto ni campañas.
"""
import os
import sys
import json
import statistics

from fastmcp import FastMCP
from dotenv import load_dotenv

ORQ_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ORQ_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

mcp = FastMCP("RamaAnalitica")


def _log(msg: str):
    print(f"[ANALITICA] {msg}", file=sys.stderr)
    sys.stderr.flush()


@mcp.tool()
def extraer_metricas(metricas_json: str) -> str:
    """Normaliza métricas (JSON) a una tabla plana: alcance, impresiones, clics, conversiones, inversion."""
    try:
        datos = json.loads(metricas_json) if isinstance(metricas_json, str) else metricas_json
        if isinstance(datos, dict):
            datos = [datos]
        filas = []
        for d in datos:
            filas.append({
                "alcance": d.get("alcance", d.get("reach", 0)),
                "impresiones": d.get("impresiones", d.get("impressions", 0)),
                "clics": d.get("clics", d.get("clicks", 0)),
                "conversiones": d.get("conversiones", d.get("conversions", 0)),
                "inversion": d.get("inversion", d.get("spend", d.get("inversion", 0))),
            })
        return json.dumps({"total_filas": len(filas), "metricas": filas}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"métricas inválidas: {e}"}, ensure_ascii=False)


@mcp.tool()
def calcular_roi(inversion: float, ingresos: float) -> str:
    """Calcula el ROI y el CPA (costo por adquisición) a partir de inversión e ingresos."""
    roi = ((ingresos - inversion) / inversion * 100) if inversion else None
    return json.dumps({"inversion": inversion, "ingresos": ingresos,
                       "roi_pct": round(roi, 2) if roi is not None else None,
                       "rentable": roi is not None and roi > 0}, ensure_ascii=False)


@mcp.tool()
def comparar_periodos(actual_json: str, anterior_json: str) -> str:
    """Compara dos periodos de métricas y calcula la variación porcentual."""
    try:
        act = json.loads(actual_json) if isinstance(actual_json, str) else actual_json
        ant = json.loads(anterior_json) if isinstance(anterior_json, str) else anterior_json
        act = act if isinstance(act, dict) else (act[0] if act else {})
        ant = ant if isinstance(ant, dict) else (ant[0] if ant else {})
        campos = ["alcance", "impresiones", "clics", "conversiones", "inversion"]
        variacion = {}
        for c in campos:
            a, b = act.get(c, 0), ant.get(c, 0)
            variacion[c] = round(((a - b) / b * 100), 2) if b else None
        return json.dumps({"periodo_actual": act, "periodo_anterior": ant, "variacion_pct": variacion},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"comparación inválida: {e}"}, ensure_ascii=False)


@mcp.tool()
def detectar_anomalias(metricas_json: str, umbral: float = 1.5) -> str:
    """Detecta anomalías básicas en una serie de métricas (desviación respecto a la media)."""
    try:
        datos = json.loads(metricas_json) if isinstance(metricas_json, str) else metricas_json
        serie = datos if isinstance(datos, list) else [datos]
        valores = [float(d.get("conversiones", 0)) for d in serie if isinstance(d, dict)]
        if len(valores) < 3:
            return json.dumps({"anomalias": [], "nota": "serie demasiado corta"}, ensure_ascii=False)
        media = statistics.mean(valores)
        desv = statistics.pstdev(valores) or 1
        anomalias = [i + 1 for i, v in enumerate(valores) if abs(v - media) > umbral * desv]
        return json.dumps({"media": round(media, 2), "desv": round(desv, 2),
                           "indices_anomalos": anomalias}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP de la Rama Analítica iniciado (stdio)")
    mcp.run()