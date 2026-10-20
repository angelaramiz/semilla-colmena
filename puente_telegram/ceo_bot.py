# puente_telegram/ceo_bot.py — Control remoto del CEO Humano por Telegram.
#
# Polling contra Bot API (sin webhook público, sin dependencias: solo stdlib).
# Reenvía órdenes al Orquestador (puente AG-UI) y devuelve el resumen.
# Solo responde a chats en TELEGRAM_ALLOWED_IDS (el CEO y quien él autorice).
#
# COLA PERSISTENTE (2026-10-20):
#   - offset de getUpdates persistido en disco: tras un reinicio NO se
#     re-contestan mensajes viejos ni se pierde ninguno no procesado.
#   - toda orden entra a puente_telegram/cola/pendientes.jsonl (una línea por
#     orden) ANTES de ejecutarse: si el bot muere a mitad de run, la orden
#     queda en la cola y se recupera al arrancar ("en_proceso" rancio >15 min
#     vuelve a "pendiente").
#   - 3 workers concurrentes consumen la cola: el bucle de polling nunca se
#     bloquea esperando un run largo (antes quedaba colgado hasta 25 min).
#   - al contestar OK se marca "hecho" y el update_id va a hechos.jsonl
#     (auditoría + dedupe entre reinicios). Envío fallido -> reintento (3 máx).
#
# Env:
#   TELEGRAM_BOT_TOKEN   (BotFather, obligatorio)
#   TELEGRAM_ALLOWED_IDS (coma: 12345,67890 — obligatorio)
#   PUENTE_URL           (default http://127.0.0.1:4210)
#   COMANDANTE_URL       (default http://127.0.0.1:8001, para /gates)
#   COMANDANTE_WEB_TOKEN (si el panel lo exige)
#
# Uso:  python ceo_bot.py   (o Arrancar-Colmena lo levanta si hay token)
import json
import os
import threading
import time
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
COLA = os.path.join(AQUI, "cola")
PENDING = os.path.join(COLA, "pendientes.jsonl")
HECHOS = os.path.join(COLA, "hechos.jsonl")
OFF_FILE = os.path.join(COLA, "offset.txt")
MAX_INTENTOS = 3
RANCIO_S = 900          # "en_proceso" sin terminar se reclama tras 15 min
N_WORKERS = 3

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
PERMITIDOS = {x.strip() for x in os.environ.get("TELEGRAM_ALLOWED_IDS", "").split(",") if x.strip()}
# Roles por chat: "id:rol" coma-separado (conservante observa, comandante ejecuta).
# Ids no listados en ROLES quedan como conservante (solo lectura).
ROLES: dict = {}
for _par in os.environ.get("TELEGRAM_ROLES", "").split(","):
    if ":" in _par:
        _id, _rol = _par.split(":", 1)
        ROLES[_id.strip()] = _rol.strip()


def rol_de(chat: str) -> str:
    if ROLES:
        return ROLES.get(chat, "conservante")
    return "comandante"  # sin mapeo declarado: permitido orig = comando total
PUENTE = os.environ.get("PUENTE_URL", "http://127.0.0.1:4210").rstrip("/")
COMANDANTE = os.environ.get("COMANDANTE_URL", "http://127.0.0.1:8001").rstrip("/")
CTOKEN = os.environ.get("COMANDANTE_WEB_TOKEN", "").strip()
API = "https://api.telegram.org/bot%s" % TOKEN

COLA_LOCK = threading.Lock()   # serializa acceso al archivo de cola
HIST_LOCK = threading.Lock()   # serializa memoria de conversación


def tg(metodo: str, datos: dict, timeout: int = 60):
    req = urllib.request.Request(
        "%s/%s" % (API, metodo),
        data=urllib.parse.urlencode(datos).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def enviar(chat: str, texto: str):
    for i in range(0, len(texto), 4000):
        tg("sendMessage", {"chat_id": chat, "text": texto[i:i + 4000]}, timeout=30)


def puente_orquestar(texto: str, contexto: str = "") -> str:
    """Manda la orden al Orquestador y junta los deltas SSE en respuesta final.

    `contexto` arrastra el historial reciente del chat (plan previo <-> confirmación).
    """
    instruccion = (contexto + "\n\nNueva instrucción: " + texto) if contexto else texto
    body = json.dumps({"threadId": "tg-ceo", "runId": "tg-%d" % int(time.time()),
                       "messages": [{"role": "user", "content": instruccion}]}).encode()
    req = urllib.request.Request(PUENTE + "/ag-ui", data=body,
                                 headers={"Content-Type": "application/json"})
    partes = []
    evento_final = ""
    with urllib.request.urlopen(req, timeout=1500) as r:
        for raw in r:
            linea = raw.decode("utf-8", "replace").strip()
            if not linea.startswith("data:"):
                continue
            try:
                ev = json.loads(linea[5:])
            except Exception:
                continue
            if ev.get("type") == "TEXT_MESSAGE_CONTENT":
                d = ev.get("delta", "")
                partes.append(d)
                if '"evento"' in d and "ORQUESTA" in d:
                    evento_final = d
    texto_full = "".join(partes)

    # Salida limpia: si el run trajo el entregable marcado del Tronco, devuelve
    # solo esa sección (sin banners de CrewAI).
    if "ENTREGABLE DEL TRONCO" in texto_full:
        seg = texto_full.split("ENTREGABLE DEL TRONCO", 1)[1]
        fin = seg.find("[END_OF_TRONCO")
        if fin > -1:
            seg = seg[:fin]
        limpio = seg.strip()
        if limpio.startswith("="):
            limpio = limpio.lstrip("=\n ").lstrip("=").strip()
        if limpio:
            return limpio
    # Devuelve el evento final si existe, si no los últimos 3500 chars.
    if evento_final:
        try:
            ev = json.loads(evento_final[evento_final.index("{"):])
            return "Evento: %(evento)s\nSiguiente: %(siguiente)s\n\n%(resultado)s" % {
                "evento": ev.get("evento"), "siguiente": ev.get("siguiente"),
                "resultado": str(ev.get("resultado", ev.get("error", "")))[:3000]}
        except Exception:
            pass
    return texto_full[-3500:] or "(sin respuesta del orquestador)"


def cmd_gates() -> str:
    try:
        req = urllib.request.Request(COMANDANTE + "/api/aprobaciones",
                                     headers={"X-Comandante-Token": CTOKEN} if CTOKEN else {})
        with urllib.request.urlopen(req, timeout=20) as r:
            gs = json.loads(r.read().decode("utf-8")).get("pendientes", [])
        if not gs:
            return "Sin gates pendientes."
        return "\n".join("#%s [%s] %s: %s" % (g.get("id"), g.get("arbol_id"),
                                              g.get("tipo"), (g.get("detalle") or "")[:120])
                         for g in gs)
    except Exception as e:
        return "No pude leer gates: %s" % str(e)[:150]


def cmd_estado() -> str:
    """Tablero instantáneo: GET /estado del puente (sin run CrewAI)."""
    try:
        with urllib.request.urlopen(PUENTE + "/estado", timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))
        lineas = ["🧵 ESTADO COLMENA (tablero instantáneo)",
                  "✅ puente vivo (%ds desde arranque)" % d.get("uptime_s", 0)]
        runs = d.get("runs") or {}
        for rid, inf in runs.items():
            lineas.append("⏳ run %s rama %s desde %s (%s)"
                          % (str(rid)[:8], inf.get("rama"),
                             inf.get("inicio"), inf.get("estado")))
        ult = d.get("ultimos") or {}
        for rama, ev in ult.items():
            detalle = str(ev.get("resumen") or ev.get("error") or "")[:110]
            lineas.append("- %s: %s -> %s | %s"
                          % (rama, ev.get("evento", ""), ev.get("siguiente", ""), detalle))
        if not runs:
            lineas.append("(sin runs activos)")
        lineas.append("Tip: manda una orden en texto para un run completo (1-3 min).")
        return "\n".join(lineas)
    except Exception as e:
        return "No pude leer el tablero del puente: %s" % str(e)[:150]


def cmd_resolver(gid: str, decision: str) -> str:
    try:
        body = json.dumps({"decision": decision}).encode()
        req = urllib.request.Request(
            COMANDANTE + "/api/aprobaciones/%s/resolver" % gid, data=body,
            headers={"Content-Type": "application/json",
                     **({"X-Comandante-Token": CTOKEN} if CTOKEN else {})})
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode("utf-8"))
        return "Gate #%s: %s" % (gid, res.get("estado"))
    except Exception as e:
        return "Error resolviendo gate: %s" % str(e)[:150]


def _presentar(respuesta: str) -> str:
    """Si el entregable del Tronco es JSON estricto, muestra solo lo útil al CEO."""
    try:
        d = json.loads(respuesta)
        if isinstance(d, dict) and "entregable" in d:
            partes = [str(d.get("entregable") or "").strip()]
            pasos = d.get("proximos_pasos") or []
            if "esperar_confirmacion_directora" in pasos:
                partes.append("❓ ¿Confirmas la ejecución? (responde: sí, ejecuta — o los ajustes)")
            elif pasos:
                partes.append("Próximos pasos: " + ", ".join(str(p) for p in pasos))
            if d.get("aprobacion"):
                partes.append("🚦 Gate pendiente de tu aprobación: %s" % d["aprobacion"])
            out = "\n".join(p for p in partes if p)
            return out or respuesta
    except Exception:
        pass
    return respuesta


HIST: dict = {}  # chat_id -> [(remitente, texto)] — memoria de conversación por chat


def _historial(chat: str, nuevo: str | None = None) -> str:
    """Registro por chat: guarda el nuevo mensaje y devuelve el contexto reciente."""
    with HIST_LOCK:
        hm = HIST.setdefault(chat, [])
        if nuevo is not None:
            hm.append(("ceo", nuevo))
        ctx = ""
        if hm:
            ctx = "Historial reciente de la conversación (más nuevo al final):\n" + "\n".join(
                "%s: %s" % (q, t[:500]) for q, t in hm[-6:])
        return ctx


# ---------- Cola persistente ----------

def _offset_cargar() -> int:
    try:
        with open(OFF_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0


def _offset_guardar(o: int):
    try:
        os.makedirs(COLA, exist_ok=True)
        tmp = OFF_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(o))
        os.replace(tmp, OFF_FILE)
    except Exception:
        pass


def _items_leer() -> list:
    items = []
    try:
        with open(PENDING, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    items.append(json.loads(ln))
    except FileNotFoundError:
        pass
    return items


def _items_escribir(items: list):
    tmp = PENDING + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    os.replace(tmp, PENDING)


def _hechos_ids() -> set:
    ids = set()
    try:
        with open(HECHOS, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    ids.add(json.loads(ln)["update_id"])
    except FileNotFoundError:
        pass
    return ids


def _hecho_registrar(item: dict, respuesta: str):
    reg = {"update_id": item["update_id"], "chat": item["chat"],
           "ts": time.time(), "respuesta": respuesta[:150]}
    with open(HECHOS, "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def _procesar(item: dict) -> str:
    """Ejecuta una orden de la cola y devuelve el texto contestado.

    Gating por rol: conservante observa (estado/gates/ubicación); solo el
    comandante despacha órdenes (texto libre) y resuelve gates.
    """
    chat, texto = item["chat"], item["texto"]
    rol = rol_de(chat)
    es_comandante = rol in ("comandante", "ceo")
    if texto.startswith("/quiensoy"):
        r = "Tu chat %s tiene rol: %s" % (chat, rol)
    elif texto.startswith("/cola"):
        with COLA_LOCK:
            items = _items_leer()
        n_p = sum(1 for it in items if it.get("estado") == "pendiente")
        n_e = sum(1 for it in items if it.get("estado") == "en_proceso")
        n_err = sum(1 for it in items if it.get("estado") == "error")
        r = "📋 Cola: %d pendiente(s), %d en proceso, %d en error. Lo contestado queda en el registro de hechos." % (
            n_p, n_e, n_err)
    elif texto.startswith(("/aprobar", "/rechazar")) and not es_comandante:
        r = "🚫 Solo el Comandante resuelve gates. Tu rol: %s (consulta: /estado /gates)." % rol
    elif not texto.startswith("/") and not es_comandante:
        r = ("🚫 Rol %s es de observación: solo /estado, /gates y /quiensoy.\n"
             "Las órdenes de ejecución las despacha el Comandante (según chat id)." % rol)
    elif texto.startswith("/gates"):
        r = cmd_gates()
    elif texto.startswith("/aprobar"):
        p = texto.split()
        r = cmd_resolver(p[1], "aprobada") if len(p) > 1 else "Uso: /aprobar <id>"
    elif texto.startswith("/rechazar"):
        p = texto.split()
        r = cmd_resolver(p[1], "rechazada") if len(p) > 1 else "Uso: /rechazar <id>"
    elif texto.startswith("/estado"):
        r = cmd_estado()
    elif texto.startswith("/start") or texto.startswith("/ayuda"):
        r = ("Soy el control del Orquestador. Tu rol: %s.\n"
             "Comandos: /estado /cola /gates /quiensoy%s"
             % (rol, " /aprobar <id> /rechazar <id> + órdenes en texto" if es_comandante
                else " (solo lectura)"))
    else:
        ctx = _historial(chat)
        respuesta = puente_orquestar(texto, contexto=ctx)
        respuesta = _presentar(respuesta)
        _historial(chat, texto)
        with HIST_LOCK:
            HIST.setdefault(chat, []).append(("tronco", respuesta[:600]))
        r = respuesta
    enviar(chat, r)
    return r


def _trabajador():
    while True:
        objetivo = None
        with COLA_LOCK:
            items = _items_leer()
            for it in items:
                est = it.get("estado")
                if est == "pendiente" or (
                        est == "en_proceso"
                        and time.time() - float(it.get("desde", 0)) > RANCIO_S):
                    objetivo = it
                    it["estado"] = "en_proceso"
                    it["desde"] = time.time()
                    break
            if objetivo:
                _items_escribir(items)
        if not objetivo:
            time.sleep(2)
            continue
        try:
            respuesta = _procesar(objetivo)
        except Exception as e:
            objetivos_int = int(objetivo.get("intentos", 0)) + 1
            with COLA_LOCK:
                items = _items_leer()
                for it in items:
                    if it["update_id"] == objetivo["update_id"]:
                        it["intentos"] = objetivos_int
                        it["error"] = str(e)[:150]
                        it["estado"] = "pendiente" if objetivos_int < MAX_INTENTOS else "error"
                        break
                _items_escribir(items)
            print("[CEO-BOT] orden %s error (intento %d): %s"
                  % (objetivo["update_id"], objetivos_int, str(e)[:120]), flush=True)
            time.sleep(3)
            continue
        with COLA_LOCK:
            items = _items_leer()
            _items_escribir([it for it in items
                             if it["update_id"] != objetivo["update_id"]])
            _hecho_registrar(objetivo, respuesta)


def main():
    if not TOKEN or not PERMITIDOS:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN o TELEGRAM_ALLOWED_IDS")
    os.makedirs(COLA, exist_ok=True)
    hechos = _hechos_ids()
    offset = _offset_cargar()
    for _ in range(N_WORKERS):
        threading.Thread(target=_trabajador, daemon=True).start()
    print("[CEO-BOT] escuchando como control del Orquestador…", flush=True)
    print("[CEO-BOT] cola persistente activa: offset=%d pendientes=%d hechos=%d"
          % (offset, len(_items_leer()), len(hechos)), flush=True)
    while True:
        try:
            res = tg("getUpdates", {"offset": offset, "timeout": 50}, timeout=70)
            for up in res.get("result", []):
                offset = up["update_id"] + 1
                _offset_guardar(offset)
                msg = up.get("message") or {}
                chat = str((msg.get("chat") or {}).get("id", ""))
                texto = (msg.get("text") or "").strip()
                if not texto:
                    continue
                if chat not in PERMITIDOS:
                    enviar(chat, "No autorizado. Este bot solo responde al CEO.")
                    continue
                uid = up["update_id"]
                if uid in hechos:
                    continue
                with COLA_LOCK:
                    items = _items_leer()
                    if any(it["update_id"] == uid for it in items):
                        continue
                    items.append({"update_id": uid, "chat": chat,
                                  "texto": texto[:4000], "estado": "pendiente",
                                  "ts": time.time()})
                    _items_escribir(items)
                if not texto.startswith("/"):
                    enviar(chat, "📥 En cola. Hay %d orden(es) esperando — te contesto "
                                 "en cuanto le toque." % len(items))
        except Exception as e:
            print("[CEO-BOT] error: %s" % str(e)[:200], flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
