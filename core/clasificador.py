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


def clasificar_instruccion(instruccion: str) -> dict:
    """Retorna dict con complejidad, modelo y si requiere aprobación."""
    texto = instruccion.lower()
    criticas = [k for k in CRITICAS if k in texto]
    medias = [k for k in MEDIAS if k in texto]

    if criticas:
        return {
            "complejidad": "critica",
            "modelo": "estrategia",
            "requiere_aprobacion": True,
            "categorias": criticas,
        }
    if medias:
        return {
            "complejidad": "media",
            "modelo": "estrategia",
            "requiere_aprobacion": False,
            "categorias": medias,
        }
    return {
        "complejidad": "rutina",
        "modelo": "rutina",
        "requiere_aprobacion": False,
        "categorias": [],
    }


def clasificar_instruccion_json(instruccion: str) -> str:
    """Versión JSON de clasificar_instruccion (para herramientas MCP)."""
    return json.dumps(clasificar_instruccion(instruccion), ensure_ascii=False)