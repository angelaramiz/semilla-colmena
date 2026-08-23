# orquestador/campana.py
"""
PIPELINE DE CAMPAÑA — orquestación ordenada de ramas (Flow de la colmena).

Encadena las etapas de una campaña pasando el contexto de cada una a la siguiente:

  1. INVESTIGACIÓN  → rama investigacion   → dossier de mercado
  2. PLANEACIÓN     → rama planeacion      → plan (KPIs, público, calendario, presupuesto)
  3. CREACIÓN       → ramas contenido+redes→ piezas + calendario editorial
  4. EXPOSICIÓN     → prepara programación + 🔴 GATE de aprobación (no emite)
  5. ANÁLISIS       → rama analitica       → reporte KPIs/ROI

Cada etapa usa ejecutar_rama (el mismo mecanismo de delegación del registro).
La etapa de exposición NUNCA emite: registra una aprobación para la Directora.
"""
import importlib
import json
import os

from core.registro_ramas import REGISTRO_RAMAS
from db import crear_aprobacion

ARBOL_ID = os.getenv("ARBOL_ID", "local")


def ejecutar_rama(rama: str, inputs: dict) -> str:
    """Ejecuta una rama y devuelve su entregable (JSON string)."""
    spec = REGISTRO_RAMAS[rama]
    mod = importlib.import_module(spec["modulo"])
    crew = getattr(mod, spec["funcion_crew"])()
    resultado = crew.kickoff(inputs=inputs)
    return getattr(mod, spec["funcion_extract"])(resultado)


def _preparar_exposicion(objetivo: str, piezas: str) -> dict:
    """Registra el gate de aprobación para la exposición. No emite nada."""
    borrador = piezas[:2000] if isinstance(piezas, str) else json.dumps(piezas, ensure_ascii=False)[:2000]
    aprob = crear_aprobacion(
        ARBOL_ID,
        tipo="publicar",
        detalle=f"Exponer campaña: {objetivo}",
        borrador=borrador,
    )
    return {"estado": "pendiente_aprobacion", "aprobacion": aprob}


def ejecutar_campana(objetivo: str, inputs: dict | None = None) -> dict:
    """Ejecuta la campaña completa (5 etapas en orden)."""
    inputs = inputs or {}
    ciudad = inputs.get("ciudad", "")
    marca = inputs.get("marca", "")
    plataformas = inputs.get("plataformas", "instagram")
    audiencia = inputs.get("audiencia", "")
    tono = inputs.get("tono", "profesional")
    presupuesto = inputs.get("presupuesto", 0)
    periodo_dias = int(inputs.get("periodo_dias", 7))
    metricas_json = inputs.get("metricas_json", "{}")

    resultados = {}

    # 1) INVESTIGACIÓN
    dossier = ejecutar_rama("investigacion", {
        "tema": objetivo, "ciudad": ciudad, "categoria": inputs.get("categoria", "")})
    resultados["1_investigacion"] = dossier

    # 2) PLANEACIÓN (recibe el dossier)
    plan = ejecutar_rama("planeacion", {
        "objetivo": objetivo, "dossier_json": dossier, "ciudad": ciudad,
        "presupuesto": str(presupuesto), "plataformas": plataformas, "periodo_dias": str(periodo_dias)})
    resultados["2_planeacion"] = plan

    # 3) CREACIÓN: contenido (piezas) + redes (calendario editorial)
    piezas = ejecutar_rama("contenido", {
        "tema": objetivo, "marca": marca, "audiencia": audiencia,
        "plataformas": plataformas, "tono": tono})
    resultados["3_creacion_contenido"] = piezas
    calendario = ejecutar_rama("redes", {
        "marca": marca, "audiencia": audiencia, "plataformas": plataformas,
        "periodo_dias": str(periodo_dias), "objetivo": objetivo})
    resultados["3_creacion_redes"] = calendario

    # 4) EXPOSICIÓN: prepara + GATE (no emite)
    exposicion = _preparar_exposicion(objetivo, piezas)
    resultados["4_exposicion"] = exposicion

    # 5) ANÁLISIS (retroalimenta la siguiente campaña)
    analisis = ejecutar_rama("analitica", {
        "objetivo": objetivo, "periodo": inputs.get("periodo", "post-campana"),
        "metricas_json": metricas_json})
    resultados["5_analisis"] = analisis

    return {
        "objetivo": objetivo,
        "etapas": resultados,
        "estado": "pendiente_aprobacion",
        "proximo_paso": "la Directora aprueba la etapa de exposición (publicar)",
    }


if __name__ == "__main__":
    import sys
    objetivo = sys.argv[1] if len(sys.argv) > 1 else "Lanzamiento de campaña"
    print(json.dumps(ejecutar_campana(objetivo), ensure_ascii=False, indent=2))