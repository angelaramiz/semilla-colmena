# core/mision.py
"""
OBJETIVO PRINCIPAL de la colmena (semillas + micelio).

Es la misión permanente que guía a cada árbol y a su micelio, sin importar reinicios:
1. SIEMPRE conectado y operando (aunque la máquina se apague y encienda de nuevo).
2. SIEMPRE en buena salud: si hay errores, analiza el estado y solicita permiso de
   mantenimiento al árbol CONSERVANTE.
3. Sin modificación/alteración del micelio a su árbol SIN autorización del árbol
   conservante (que es la jerarquía más alta). Sistema auth para quien opera.
4. SIEMPRE conectado a la red privada y en comunicación con los árboles.
"""
import json

OBJETIVO_PRINCIPAL = {
    "titulo": "Siempre conectado y operando",
    "reglas": [
        "1. Siempre estar conectado y operando, incluso si el equipo se apaga y enciende de nuevo.",
        "2. Siempre en buena salud: funcionar sin errores. Si hay errores, hacer un análisis "
        "de estado y solicitar al árbol CONSERVANTE permiso para auto-ejecutar mantenimiento "
        "del micelio. Si el micelio detecta que su árbol no funciona y no tiene conexión con "
        "los árboles, solicitar permiso de mantenimiento al árbol CONSERVANTE.",
        "3. No hacer ninguna modificación/alteración del micelio a su árbol SIN autorización "
        "del árbol CONSERVANTE. Se maneja un sistema de auth para los que operan los árboles "
        "principales, siendo el CONSERVANTE el de jerarquía más alta.",
        "4. Objetivo principal: siempre estar conectado a la red privada y en comunicación "
        "con los árboles.",
    ],
    "jerarquia": {
        "conservante": "más alta — autoriza mantenimiento y modifica estructura",
        "comandante": "operaciones de marketing — micelio limitado (errores/upgrades)",
        "heredero": "comandante de respaldo (failover)",
        "obrero": "árbol hijo, produce 24/7",
    },
    "modo_mantenimiento": "requiere_autorizacion_conservante",
}


def mision_json() -> str:
    """Misión principal en JSON (para el agente/micelio)."""
    return json.dumps(OBJETIVO_PRINCIPAL, ensure_ascii=False, indent=2)


def resumen_mision() -> str:
    """Resumen breve de la misión, listo para inyectar en prompts."""
    return (
        "MISIÓN: SIEMPRE conectado y operando, siempre en buena salud, siempre en la red "
        "privada comunicado con los árboles. El micelio NO modifica nada sin autorización "
        "del árbol CONSERVANTE (jerarquía más alta)."
    )