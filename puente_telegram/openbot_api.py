# puente_telegram/openbot_api.py
"""
F4b: puente Telegram -> OpenBot (protocolo AG-UI sobre CopilotKit v2).

Protocolo verificado en vivo contra el server (:3001):

1. POST /api/copilotkit/agent/<agentId>/run  (RunAgentInput)
   -> {threadId, runId, joinToken}
2. GET  /api/copilotkit/threads/<threadId>/events -> snapshot JSON de eventos
   (RUN_STARTED / TEXT_MESSAGE_CONTENT / RUN_FINISHED / RUN_ERROR).

La memoria/aprendizaje de OpenBot vive en el thread (Intelligence): cada chat
de Telegram mapea a SU PROPIO channel/thread, asi la conversacion del CEO
(plan -> confirmacion -> ejecucion) acumula memoria real sin duplicarla en
el lado de la agencia.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

BASE = os.getenv("OPENBOT_URL", "http://127.0.0.1:3001").rstrip("/")
AGENT = os.getenv("OPENBOT_AGENT", "orquestador-colmena")
TIMEOUT_RUN = int(os.getenv("OPENBOT_RUN_TIMEOUT", "900"))
POLL_S = float(os.getenv("OPENBOT_POLL_S", "2"))
# Reintentos de transito: 1 intento extra si la red falla al POST run;
# y hasta N enfriamientos si el proveedor devulve 429/capacidad llena.
INTENTOS_RED = int(os.getenv("OPENBOT_INTENTOS_RED", "2"))
ENFRIAMIENTOS = int(os.getenv("OPENBOT_ENFRIAMIENTOS", "2"))
COOLDOWN_S = float(os.getenv("OPENBOT_COOLDOWN_S", "45"))
MAP_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "cola", "openbot_map.json")
MAPA_LOCK = threading.Lock()


def _get(path: str, timeout: int = 30):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path: str, body: dict, timeout: int = 60):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _mapa_leer() -> dict:
    try:
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _mapa_guardar(mapa: dict):
    os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)


def disponible() -> bool:
    try:
        _get("/api/me", timeout=5)
        return True
    except Exception:
        return False


def _ventana(ch: dict, texto: str) -> str:
    """Un ciclo de run completo con un channel/thread resuelto."""
    json_body = {
        "threadId": ch["threadId"],
        "runId": "tg-%s" % str(int(time.time() * 1000)),
        "state": {},
        "messages": [{"id": "tg-%d" % int(time.time() * 1000),
                      "role": "user", "content": texto}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    r = None
    for intento in range(1, INTENTOS_RED + 1):
        try:
            r = _post("/api/copilotkit/agent/%s/run" % AGENT, json_body,
                      timeout=60)
            break
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            if intento >= INTENTOS_RED:
                raise RuntimeError(
                    "OpenBot inalcanzable tras %d intentos: %s"
                    % (intento, str(e)[:150]))
            time.sleep(2 * intento)
    run_id = r.get("runId")
    if not run_id:
        raise RuntimeError("OpenBot no acepto el run: %s" % json.dumps(r)[:300])

    deadline = time.time() + TIMEOUT_RUN
    mejor = ""
    error = None
    while time.time() < deadline:
        time.sleep(POLL_S)
        try:
            ev = _get("/api/copilotkit/threads/%s/events"
                      % ch["threadId"], timeout=25)
        except Exception:
            continue  # blip de red en el snapshot: se repite el ciclo
        evs = ev.get("events", []) if isinstance(ev, dict) else (
            ev if isinstance(ev, list) else [])
        partes = []
        for e in evs:
            erun = e.get("runId") or (e.get("input", {}) or {}).get("runId")
            if erun != run_id:
                continue
            if e.get("type") == "TEXT_MESSAGE_CONTENT":
                partes.append(e.get("delta", ""))
            elif e.get("type") == "RUN_ERROR":
                error = e.get("message") or "RUN_ERROR"
        texto = "".join(partes)
        if len(texto) > len(mejor):
            mejor = texto
        if error:
            raise RuntimeError("OpenBot: %s" % error[:300])
        for e in evs:
            erun = e.get("runId") or (e.get("input", {}) or {}).get("runId")
            if erun == run_id and e.get("type") == "RUN_FINISHED":
                return mejor or "(run terminado sin texto)"
    raise RuntimeError(
        "timeout %ds esperando RUN_FINISHED; parcial: %d chars"
        % (TIMEOUT_RUN, len(mejor)))


def channel_para(chat: str) -> dict:
    """Devuelve {channelId, threadId} propio para el chat (creando si falta).

    El channel/thread persiste las conversaciones de ese chat: la memoria de
    OpenBot (thread + learning) queda pegada al dueño, no al ciclo del bot.
    """
    mapa = _mapa_leer() if MAPA_LOCK.acquire(timeout=5) else {}
    try:
        ch = mapa.get(chat)
        if ch and ch.get("threadId"):
            try:
                _get("/api/channels/" + ch["channelId"], timeout=10)
                return ch
            except Exception:
                pass  # channel borrado/limpieza: se recrea
        nuevo = _post("/api/channels", {"agentIds": [AGENT]}, timeout=20)
        ch = {"channelId": nuevo["channel"]["id"],
              "threadId": nuevo["channel"].get("threadId")}
        mapa[chat] = ch
        _mapa_guardar(mapa)
        return ch
    finally:
        if MAPA_LOCK.locked():
            MAPA_LOCK.release()


def orquestar(chat: str, texto: str) -> str:
    """Manda la orden al agente de OpenBot y devuelve el texto final del run.

    El historial NO se inyecta desde Telegram: vive en el thread de OpenBot
    (memoria real). Política de robustez:
    - 2 intentos de red en el POST de run (transitorios).
    - hasta N enfriamientos (COOLDOWN_S) si el proveedor marca 429/capacidad.
    Lanza RuntimeError en RUN_ERROR persistente / timeout, con la causa.
    """
    ch = channel_para(chat)
    intento_cap = 0
    while True:
        try:
            return _ventana(ch, texto)
        except RuntimeError as e:
            msg = str(e)
            cap = ("capacity" in msg.lower()) or ("429" in msg) or (
                "request limit" in msg.lower())
            if cap and intento_cap < ENFRIAMIENTOS:
                intento_cap += 1
                time.sleep(COOLDOWN_S)
                continue
            raise


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("OpenBot arriba:", disponible())
    ch = channel_para("ping-cli")
    print("channel:", ch["channelId"], "thread:", ch["threadId"])
    print("res:", orquestar("ping-cli", "Responde UNA sola palabra: PONG"))
