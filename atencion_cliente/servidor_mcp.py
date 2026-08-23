# atencion_cliente/servidor_mcp.py
"""
Servidor MCP de la RAMA ATENCIÓN AL CLIENTE (Soporte y relaciones).

Herramientas de apoyo deterministas para el agente:
- clasificar_mensaje      : clasifica (consulta | queja | venta | otro).
- buscar_base_conocimiento: busca una respuesta en la base de conocimiento (plantillas).
- proponer_respuesta      : esboza una respuesta para consultas rutinarias.
- escalar_queja           : registra una queja para escalar a la Directora (GATE).

La rama responde consultas RUTINARIAS; las QUEJAS/confidenciales requieren aprobación.
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

mcp = FastMCP("RamaAtencionCliente")

# Base de conocimiento (plantillas de ejemplo)
BASE_CONOCIMIENTO = {
    "horario": "Nuestro horario es de 9:00 a 18:00, de lunes a sábado.",
    "envio": "Hacemos envíos a toda la ciudad; el costo depende de la zona.",
    "pago": "Aceptamos tarjetas, transferencia y efectivo.",
    "soporte": "Para soporte técnico escribe a soporte@agenciamarketing.com.",
    "default": "Gracias por escribirnos. Un asesor te atenderá en breve.",
}


def _log(msg: str):
    print(f"[ATENCION] {msg}", file=sys.stderr)
    sys.stderr.flush()


@mcp.tool()
def clasificar_mensaje(mensaje: str) -> str:
    """Clasifica un mensaje del cliente: consulta | queja | venta | otro."""
    m = mensaje.lower()
    if any(k in m for k in ["queja", "reclamo", "devolución", "devolucion", "molesto", "mal servicio", "error"]):
        tipo = "queja"
    elif any(k in m for k in ["precio", "comprar", "cotiza", "presupuesto", "pago", "disponible"]):
        tipo = "venta"
    elif any(k in m for k in ["horario", "envío", "envio", "pago", "donde", "cuando", "cómo", "como", "soporte"]):
        tipo = "consulta"
    else:
        tipo = "otro"
    return json.dumps({"clasificacion": tipo, "requiere_aprobacion": tipo == "queja",
                       "sugerencia": "escalar a Directora" if tipo == "queja" else "responder rutina"},
                      ensure_ascii=False)


@mcp.tool()
def buscar_base_conocimiento(tema: str) -> str:
    """Busca una respuesta en la base de conocimiento."""
    t = tema.lower()
    for k, v in BASE_CONOCIMIENTO.items():
        if k in t:
            return json.dumps({"encontrado": True, "tema": k, "respuesta": v}, ensure_ascii=False)
    return json.dumps({"encontrado": False, "respuesta": BASE_CONOCIMIENTO["default"]}, ensure_ascii=False)


@mcp.tool()
def proponer_respuesta(mensaje: str) -> str:
    """Esboza una respuesta empática para consultas rutinarias (no quejas)."""
    return json.dumps({
        "respuesta_borrador": f"Gracias por tu mensaje. Recibimos tu consulta: '{mensaje[:80]}'. "
                              f"Te confirmamos que estamos atendiendo y te responderemos a la brevedad.",
        "tono": "empatico",
        "lista_para_enviar": False,   # requiere revisión/aprobación antes de enviar
    }, ensure_ascii=False)


@mcp.tool()
def escalar_queja(mensaje: str, cliente: str = "") -> str:
    """Registra una queja para escalar. NUNCA la responde directamente (GATE)."""
    return json.dumps({
        "escalada": True,
        "cliente": cliente,
        "motivo": mensaje[:120],
        "requiere_aprobacion_humana": True,   # 🔴 responder queja = crítico
        "accion": "pendiente de revisión por la Directora Humana",
    }, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP de la Rama Atención al Cliente iniciado (stdio)")
    mcp.run()