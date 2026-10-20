# core/clasificador.py
"""
Clasificación determinista de complejidad de la agencia.

Cada instrucción de la Directora se mapea a:
- 'rutina'  -> Ollama local, sin aprobación (scraping, resúmenes, formateo).
- 'media'   -> OpenRouter, sin aprobación (borradores, propuestas, creatividad).
- 'critica' -> OpenRouter + REQUIERE aprobación humana antes de ejecutar.
"""
import json

# Acciones irreversibles: SIEMPRE disparan un gate de aprobación.
CRITICAS = [
    "publicar", "publica", "publicar en", "publicar el post", "programa el post",
    "enviar", "envía", "manda el correo", "enviar la campaña", "lanzar la campaña",
    "campaña publicitaria", "respóndele la queja", "responder queja", "reclamo",
    "oferta pública", "descuento", "gasto", "presupuesto de ads", "comprar anuncios",
    "cambiar precio", "compartir datos",
]

# Razonamiento/creatividad (no irreversibles): usan OpenRouter, sin gate.
MEDIAS = [
    "propón", "propón 5", "idea", "ideas", "estrategia", "plan",
    "redacta", "redacta un", "copia", "texto para", "guion", "brief",
]

# TRABAJO DE RAMA: la instrucción pide PRODUCIR datos/borradores que la rama
# especializada fabrica (el Tronco DELEGA con delegar_rama_tool; nunca los
# "procesa localmente" ni paraphrasea la orden). Se evalúan ANTES de MEDIAS.
DELEGABLES = {
    "investigacion": [
        "investigar", "investiga", "investigación", "dossier", "estudio de",
        "competencia de", "competidores", "tendencias", "tendencia",
        "panorama", "huella digital", "auditar huella", "detectar tendencias",
    ],
    "planeacion": [
        "planea una campaña", "planifica una campaña", "plan de campaña",
        "kpi", "kpis", "calendario de campaña", "objetivos y kpis",
    ],
    "contenido": [
        "redacta", "escribe", "copy", "posts", "piezas", "guion", "tweet",
        "caption", "leguaje publicitario",
    ],
    "redes": [
        "calendario de publicaciones", "programa las publicaciones",
        "agenda de publicaciones", "cuando publicar",
    ],
    "analitica": [
        "métricas", "reporte de métricas", "analiza los resultados", "roi",
    ],
}
# Nota: 'atencion_cliente' llega por quejas; CRITICAS ya cubre "respóndele la
# queja"/"reclamo" con gate. La delegación a esa rama la decide el Tronco
# cuando la instrucción pide CONTESTAR al cliente (borrador de respuesta).


def clasificar_instruccion(instruccion: str) -> dict:
    """Retorna dict con complejidad, modelo, gate y rama_sugerida (si trae trabajo de rama)."""
    texto = instruccion.lower()
    criticas = [k for k in CRITICAS if k in texto]
    medias = [k for k in MEDIAS if k in texto]
    rama, rama_kw = None, []
    for nombre, keywords in DELEGABLES.items():
        hits = [k for k in keywords if k in texto]
        if hits:
            rama = nombre
            rama_kw = hits
            break

    if criticas:
        return {
            "complejidad": "critica",
            "modelo": "estrategia",
            "requiere_aprobacion": True,
            "categorias": criticas,
            "rama_sugerida": rama,
        }
    if rama:
        return {
            "complejidad": "media",
            "modelo": "estrategia",
            "requiere_aprobacion": False,
            "categorias": rama_kw,
            "rama_sugerida": rama,
        }
    if medias:
        return {
            "complejidad": "media",
            "modelo": "estrategia",
            "requiere_aprobacion": False,
            "categorias": medias,
            "rama_sugerida": None,
        }
    return {
        "complejidad": "rutina",
        "modelo": "rutina",
        "requiere_aprobacion": False,
        "categorias": [],
        "rama_sugerida": None,
    }


def clasificar_instruccion_json(instruccion: str) -> str:
    """Versión JSON de clasificar_instruccion (para herramientas MCP)."""
    return json.dumps(clasificar_instruccion(instruccion), ensure_ascii=False)