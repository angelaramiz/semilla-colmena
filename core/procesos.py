# core/procesos.py
"""Registro de procesos en ejecución con FASES (no % a ciegas).

Cada proceso largo (auditoría local o delegada, pulls, upgrades) se registra con
una lista de fases y avanza parseando markers reales de su log (CrewAI, MCP,
tareas). Persistencia en JSON para que los paneles (/api/procesos) lo muestren
en la pestaña global "Procesos en ejecución".
"""
import json
import os
import time

# Fases canónicas de una auditoría (crew primer_contacto, por rol de agente).
FASES_AUDITORIA = [
    "Servidor MCP",
    "Clasificando modelo de negocio",
    "Investigando identidad",
    "Auditando huella digital",
    "Analizando competencia",
    "Reporte estratégico",
    "Finalizando",
]

# Fases de una auditoría DELEGADA a un obrero (el trabajo pesado corre allá).
FASES_DELEGADA = [
    "Delegando al obrero",
    "Ejecutando en obrero",
    "Trayendo reporte",
    "Listo",
]

# (fase_idx, [subcadenas que la delatan en el log]) — orden de evaluación.
_MARCADORES_AUDITORIA = [
    (0, ["Starting MCP server"]),
    (1, ["Clasificador de Modelo de Negocio"]),
    (2, ["Investigador de Identidad Corporativa"]),
    (3, ["Auditor de Huella Digital"]),
    (4, ["Analista de Competencia"]),
    (5, ["Ingeniero de Automatización", "Director Comercial"]),
    (6, ["END_OF_JSON_REPORT", "Guardado en:"]),
]


def detectar_fase(linea: str):
    """Devuelve (fase_idx, etiqueta) si la línea delata una fase auditora.
    Genérico: cualquier 'Agent: X' produce etiqueta dinámica."""
    if not linea:
        return None
    for idx, claves in _MARCADORES_AUDITORIA:
        for k in claves:
            if k in linea:
                return idx, FASES_AUDITORIA[idx]
    if "Agent:" in linea:
        try:
            nombre = linea.split("Agent:", 1)[1].strip().strip("| ").strip()[:60]
            if nombre:
                return -1, f"Agente: {nombre}"
        except Exception:
            pass
    if "Crew Execution Started" in linea:
        return 0, FASES_AUDITORIA[0]
    return None


def _ruta(base_dir: str) -> str:
    return os.path.join(base_dir, "procesos.json")


def _load(base_dir: str) -> list:
    try:
        with open(_ruta(base_dir), "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(base_dir: str, procs: list) -> None:
    try:
        os.makedirs(base_dir, exist_ok=True)
        tmp = _ruta(base_dir) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(procs[-50:], fh, ensure_ascii=False)
        os.replace(tmp, _ruta(base_dir))
    except Exception:
        pass


def iniciar(base_dir: str, proc_id: str, tipo: str, titulo: str,
            fases: list = None, detalle: str = "") -> dict:
    procs = _load(base_dir)
    procs = [p for p in procs if p.get("id") != proc_id]
    entry = {
        "id": proc_id, "tipo": tipo, "titulo": titulo,
        "estado": "en_curso", "fases": fases or FASES_AUDITORIA,
        "idx": 0, "detalle": detalle or "Iniciando...",
        "inicio": time.time(), "fin": None,
    }
    procs.append(entry)
    _save(base_dir, procs)
    return entry


def avanzar(base_dir: str, proc_id: str, idx: int, detalle: str = "") -> dict:
    procs = _load(base_dir)
    for p in procs:
        if p.get("id") == proc_id and p.get("estado") == "en_curso":
            if isinstance(idx, int) and idx >= 0:
                p["idx"] = max(int(p.get("idx", 0)), min(idx, len(p.get("fases", [])) - 1))
            if detalle:
                p["detalle"] = detalle[:220]
            _save(base_dir, procs)
            return p
    return {}


def terminar(base_dir: str, proc_id: str, estado: str = "completada") -> dict:
    procs = _load(base_dir)
    for p in procs:
        if p.get("id") == proc_id:
            p["estado"] = estado
            p["fin"] = time.time()
            if estado == "completada":
                p["idx"] = len(p.get("fases", [])) - 1
            _save(base_dir, procs)
            return p
    return {}


def listar(base_dir: str) -> list:
    procs = _load(base_dir)
    ahora = time.time()
    for p in procs:
        fin = p.get("fin") or ahora
        p["transcurrido_s"] = int(max(0, fin - (p.get("inicio") or ahora)))
    # En curso primero, luego recientes.
    return sorted(procs, key=lambda p: (p.get("estado") != "en_curso", -(p.get("inicio") or 0)))
