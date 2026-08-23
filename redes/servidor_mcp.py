# redes/servidor_mcp.py
"""
Servidor MCP de la RAMA REDES (Community Manager autónomo).

Herramientas de apoyo deterministas para el agente:
- consultar_calendario: esqueleto de calendario editorial.
- validar_hashtags    : validación básica de hashtags.
- detectar_tendencias : tendencias de muestra (placeholder; integrar API real después).
- programar_post      : construye el objeto de programación (NUNCA publica).

La rama PREPARA y PROGRAMA borradores; la publicación requiere gate de aprobación.
"""
import os
import sys
import json
import re

from fastmcp import FastMCP
from dotenv import load_dotenv

ORQ_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ORQ_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

mcp = FastMCP("RamaRedes")


def _log(msg: str):
    print(f"[REDES] {msg}", file=sys.stderr)
    sys.stderr.flush()


@mcp.tool()
def consultar_calendario(periodo_dias: int, plataformas: str = "instagram,facebook") -> str:
    """Genera un esqueleto de calendario editorial para N días y plataformas."""
    plataformas_list = [p.strip() for p in plataformas.split(",") if p.strip()]
    dias = max(1, min(periodo_dias, 30))
    return json.dumps({
        "periodo_dias": dias,
        "plataformas": plataformas_list,
        "sugerencia_frecuencia": {
            "instagram": "1 post + 3 stories/dia",
            "facebook": "1 post/dia",
            "tiktok": "1 video/dia",
        },
        "calendario": [
            {"dia": d, "hora_sugerida": "12:00", "plataforma": plataformas_list[0] if plataformas_list else "instagram",
             "tipo": "contenido", "pendiente_aprobacion": False}
            for d in range(1, dias + 1)
        ],
    }, ensure_ascii=False)


@mcp.tool()
def validar_hashtags(hashtags: str) -> str:
    """Valida hashtags: formato (#, sin espacios, sin caracteres inválidos)."""
    tags = [h.strip() for h in hashtags.split(",") if h.strip()]
    validos, invalidos = [], []
    for t in tags:
        if re.fullmatch(r"#[A-Za-z0-9_áéíóúñÁÉÍÓÚÑ]{1,50}", t):
            validos.append(t)
        else:
            invalidos.append(t)
    return json.dumps({
        "validos": validos[:30],
        "invalidos": invalidos,
        "recomendacion": "usa 3-5 hashtags: 2 amplios + 2 nicho + 1 de marca.",
    }, ensure_ascii=False)


@mcp.tool()
def detectar_tendencias(categoria: str = "") -> str:
    """Tendencias de muestra por categoría. (Placeholder: sustituir por API real de tendencias.)"""
    muestra = {
        "categoria": categoria or "general",
        "tendencias": [
            {"tema": "contenido auténtico detrás de cámaras", "vigencia": "alta"},
            {"tema": "reels/tikTok cortos con audio trending", "vigencia": "alta"},
            {"tema": "colaboraciones con creadores locales", "vigencia": "media"},
            {"tema": "contenido generado por usuarios (UGC)", "vigencia": "media"},
        ],
        "fuente": "placeholder",
    }
    return json.dumps(muestra, ensure_ascii=False)


@mcp.tool()
def programar_post(canal: str, hora: str, contenido: str) -> str:
    """Construye el objeto de programación de un post. NO lo publica.
    Requiere aprobación humana antes de emitirse."""
    return json.dumps({
        "canal": canal,
        "hora": hora,
        "contenido": contenido,
        "programado": False,
        "requiere_aprobacion": True,   # gate: publicar/emitir es crítico
    }, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP de la Rama Redes iniciado (stdio)")
    mcp.run()