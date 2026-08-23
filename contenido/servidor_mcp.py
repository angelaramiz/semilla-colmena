# contenido/servidor_mcp.py
"""
Servidor MCP de la RAMA CONTENIDO (Copywriter multiformato).

Herramientas de apoyo deterministas que el agente usa junto con su LLM:
- generar_brief       : esqueleto de brief por plataforma y audiencia.
- adaptar_tono        : guía de tono para transformar un texto.
- reutilizar_contenido: mapeo multi-canal de una pieza.
- revisar_ortografia  : validación básica (longitud, posibles erratas, emojis).
- guardar_borrador    : persiste el entregable en /shared/borradores.

La rama SOLO produce borradores; nunca publica (eso lo decide el Tronco + Directora).
"""
import os
import sys
import json
import re

from fastmcp import FastMCP
from dotenv import load_dotenv

# Raíz del proyecto (se ejecuta como subproceso)
ORQ_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ORQ_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

SHARED_DIR = os.getenv("SHARED_DIR", os.path.abspath("shared"))
BORRADORES_DIR = os.path.join(SHARED_DIR, "borradores")
os.makedirs(BORRADORES_DIR, exist_ok=True)

ARBOL_ID = os.getenv("ARBOL_ID", "local")

mcp = FastMCP("RamaContenido")

TONOS = ["empatico", "profesional", "divertido", "urgente", "inspirador", "tecnicamente riguroso"]


def _log(msg: str):
    print(f"[CONTENIDO] {msg}", file=sys.stderr)
    sys.stderr.flush()


@mcp.tool()
def generar_brief(tema: str, marca: str, audiencia: str = "", plataformas: str = "instagram") -> str:
    """Genera el esqueleto de un brief de contenido por tema, marca y plataformas."""
    plataformas_list = [p.strip() for p in plataformas.split(",") if p.strip()]
    return json.dumps({
        "tema": tema,
        "marca": marca,
        "audiencia": audiencia or "por definir",
        "plataformas": plataformas_list,
        "estructura": {
            "gancho": "Frase inicial que atrapa la atención",
            "desarrollo": "2-3 ideas clave / beneficios",
            "cierre": "Llamada a la acción (CTA) clara",
        },
        "longitud_sugerida_por_plataforma": {
            "instagram": "caption 60-220 caracteres + hashtags",
            "facebook": "post 80-150 palabras",
            "tiktok": "guion 15-30 segundos",
            "email": "asunto 5-7 palabras + cuerpo 100-200 palabras",
            "blog": "titulo + 300-800 palabras",
        },
    }, ensure_ascii=False)


@mcp.tool()
def adaptar_tono(texto: str, tono: str) -> str:
    """Devuelve guía para transformar un texto a un tono específico.
    Los tonos válidos: empatico, profesional, divertido, urgente, inspirador, tecnicamente riguroso."""
    if tono.lower() not in TONOS:
        tono = "profesional"
    return json.dumps({
        "tono": tono,
        "texto_original": texto,
        "instrucciones": [
            f"Reescribe manteniendo el mensaje pero con tono {tono}.",
            "Adapta el vocabulario, el ritmo y la emoción al tono indicado.",
            "No inventes datos ni promesas que no estén en el original.",
        ],
    }, ensure_ascii=False)


@mcp.tool()
def reutilizar_contenido(pieza: str, plataformas: str) -> str:
    """Mapea una pieza base para su reutilización en varias plataformas."""
    plataformas_list = [p.strip() for p in plataformas.split(",") if p.strip()]
    return json.dumps({
        "pieza_base": pieza,
        "plan_de_reutilizacion": {
            p: f"Adapta '{pieza[:60]}…' al formato de {p} (longitud y CTA propios)"
            for p in plataformas_list
        },
    }, ensure_ascii=False)


@mcp.tool()
def revisar_ortografia(texto: str) -> str:
    """Validación básica: longitud, posibles erratas (repeticiones) y emojis."""
    palabras = len(re.findall(r"\w+", texto))
    dobles = re.findall(r"\b(\w{2,})\s+\1\b", texto.lower())
    emojis = len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", texto))
    return json.dumps({
        "palabras": palabras,
        "posibles_repeticiones": dobles[:5],
        "emojis": emojis,
        "parece_vacio": len(texto.strip()) < 10,
        "ok": len(texto.strip()) >= 10,
    }, ensure_ascii=False)


@mcp.tool()
def guardar_borrador(nombre: str, contenido: str) -> str:
    """Guarda el borrador en /shared/borradores del árbol (no lo publica)."""
    try:
        ruta = os.path.join(BORRADORES_DIR, f"{ARBOL_ID}_{nombre}")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        _log(f"Borrador guardado: {ruta}")
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
    _log("🚀 Servidor MCP de la Rama Contenido iniciado (stdio)")
    mcp.run()