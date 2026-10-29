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
import sys
import threading
import time
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

# F4b: el chat va DIRECTO a OpenBot por defecto (memoria/learning de su server).
# PUENTE_ORQUESTADOR=crewai conserva el path viejo (puente AG-UI :4210) como
# respaldo de emergencia o para forzarlo manualmente.
PUENTE_MODO = os.getenv("PUENTE_ORQUESTADOR", "openbot").lower()
if PUENTE_MODO not in ("openbot", "crewai"):
    PUENTE_MODO = "openbot"
if PUENTE_MODO == "openbot":
    import openbot_api
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
# Ids no listados en ROLES quedan como conservante (solo lectura) — EXCEPTO el
# primer id nuevo: si TELEGRAM_NUEVO_ID_ROL declara un rol de acceso total
# (comandante/ceo/dev), ese id lo recibe UNA sola vez (cosume marcador en
# cola/nuevo_id_asignado.json) — orden Dev 2026-10-24: proximo id registrado = RUTI.
ROLES: dict = {}
for _par in os.environ.get("TELEGRAM_ROLES", "").split(","):
    if ":" in _par:
        _id, _rol = _par.split(":", 1)
        ROLES[_id.strip()] = _rol.strip()
NUEVO_ID_ROL = os.environ.get("TELEGRAM_NUEVO_ID_ROL", "").strip().lower()
NUEVO_ID_ARCH = os.path.join(COLA, "nuevo_id_asignado.json")
# Identidades por chat: "id:nombre" coma-separado (p.ej. "7360569493:Arangel").
# Si un id no esta aqui, se usa el first_name/username que Telegram trae en
# cada update. Sirve para que el bot (y el cerebro OpenBot) sepa quien es quien.
NOMBRES: dict = {}
for _par in os.environ.get("TELEGRAM_NOMBRES", "").split(","):
    if ":" in _par:
        _id, _nom = _par.split(":", 1)
        if _id.strip():
            NOMBRES[_id.strip()] = _nom.strip()


def nombre_de(chat: str, remitente_tg: str = "") -> str:
    """Nombre visible del remitente: mapa admin > Telegram > chat id."""
    if chat in NOMBRES:
        return NOMBRES[chat]
    if remitente_tg:
        return remitente_tg
    return "chat %s" % chat


ACCESO_ARCH = os.path.join(COLA, "acceso.json")  # DB local: usuarios + solicitudes
ROLES_AUTORIZABLES = ("conservante", "comandante")  # dev/ceo solo por registry manual


def _acceso_cargar() -> dict:
    try:
        with open(ACCESO_ARCH, "r", encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict):
                d.setdefault("usuarios", {})
                d.setdefault("solicitudes", {})
                return d
    except Exception:
        pass
    return {"usuarios": {}, "solicitudes": {}}


def _acceso_guardar(d: dict) -> None:
    try:
        os.makedirs(COLA, exist_ok=True)
        with open(ACCESO_ARCH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception as e:
        print("[CEO-BOT] no pude guardar acceso.json: %s" % str(e)[:120], flush=True)


def _acceso_merge() -> None:
    """Al arrancar: los usuarios autorizados en la DB local entran como permitidos."""
    d = _acceso_cargar()
    for cid, u in d.get("usuarios", {}).items():
        cid = str(cid)
        PERMITIDOS.add(cid)
        if u.get("rol"):
            ROLES[cid] = u["rol"]
        if u.get("nombre"):
            NOMBRES[cid] = u["nombre"]


def _admins() -> list:
    """Chats admin (dev/ceo) que reciben las solicitudes. Sin efectos laterales."""
    ads = [c for c, r in ROLES.items()
           if r.strip().lower() in ("dev", "ceo") and c in PERMITIDOS]
    if ads:
        return ads
    return sorted(PERMITIDOS)[:1]


def _atender_solicitud(chat: str, texto: str, de: dict) -> None:
    """Onboarding de ids no autorizados: pide apodo, registra solicitud, avisa al admin."""
    d = _acceso_cargar()
    sol = d["solicitudes"].get(chat)
    if sol and sol.get("estado") == "pendiente":
        enviar(chat, "⏳ Tu solicitud como '%s' sigue pendiente de aprobación. "
                     "Te aviso en cuanto te den acceso." % sol.get("nombre", "?"))
        return
    if sol and sol.get("estado") == "esperando_nombre":
        apodo = texto.strip()[:30]
        if not apodo or apodo.startswith("/"):
            enviar(chat, "Dime el nombre o apodo que quieres usar "
                         "(texto simple, sin /comandos).")
            return
        sol["nombre"] = apodo
        sol["estado"] = "pendiente"
        sol["ts"] = time.time()
        _acceso_guardar(d)
        quien = "%s%s" % (sol.get("first_name") or "?", 
                          (" (@" + sol["username"] + ")") if sol.get("username") else "")
        for adm in _admins():
            enviar(adm, "🆕 Solicitud de acceso\n¿Quién: %s — id %s\nApodo: %s\n\n"
                        "Autoriza con:\n/autorizar %s comandante\n"
                        "/autorizar %s conservante\n/rechazar %s"
                   % (quien, chat, apodo, chat, chat, chat))
        print("[CEO-BOT] solicitud %s (%s) pendiente" % (chat, apodo), flush=True)
        enviar(chat, "✅ Listo, %s. Tu solicitud quedó registrada — "
                     "te aviso cuando te autoricen." % apodo)
        return
    d["solicitudes"][chat] = {
        "estado": "esperando_nombre",
        "first_name": str((de or {}).get("first_name") or ""),
        "username": str((de or {}).get("username") or ""),
        "ts": time.time(),
    }
    _acceso_guardar(d)
    hola = " %s" % d["solicitudes"][chat]["first_name"] if d["solicitudes"][chat]["first_name"] else ""
    enviar(chat, "👋 Hola%s. Este bot es privado.\n"
                 "¿Con qué nombre o apodo quieres registrarte? Escríbelo ahora "
                 "y tu solicitud llegará al administrador." % hola)


APREN_ARCH = os.path.join(COLA, "aprendizajes.json")  # DB local de memoria enseñada
APREN_STOP = frozenset(
    "que como para por con una eso este esta los las del son fue han hay muy mas sin sobre "
    "entre hasta desde donde cuando cual cuales porque pues solo tan tambien pero sus mis tu tus "
    "the and for are with que".split())


def _apren_cargar() -> list:
    try:
        with open(APREN_ARCH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _apren_guardar(items: list) -> None:
    try:
        os.makedirs(COLA, exist_ok=True)
        with open(APREN_ARCH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
    except Exception as e:
        print("[CEO-BOT] no pude guardar aprendizajes.json: %s" % str(e)[:120], flush=True)


def _apren_tokens(s: str) -> set:
    return {w for w in __import__("re").findall(r"[a-záéíóúñü]{4,}", s.lower())
            if w not in APREN_STOP}


def _apren_relevantes(texto: str, top: int = 3) -> list:
    """Aprendizajes cuyo tema/dato comparte palabras clave con el texto."""
    toks = _apren_tokens(texto)
    if not toks:
        return []
    scored = []
    for a in _apren_cargar():
        blob = "%s %s" % (a.get("tema", ""), a.get("dato", ""))
        n = len(toks & _apren_tokens(blob))
        if n:
            scored.append((n, a))
    scored.sort(key=lambda x: -x[0])
    return [a for _, a in scored[:top]]


def _apren_agregar(tema: str, dato: str, autor: str) -> int:
    items = _apren_cargar()
    nid = max([a.get("id", 0) for a in items] + [0]) + 1
    items.append({"id": nid, "tema": tema, "dato": dato,
                  "autor": autor, "ts": time.time()})
    _apren_guardar(items)
    return nid


def _apren_borrar(nid: int):
    items = _apren_cargar()
    resto = [a for a in items if a.get("id") != nid]
    if len(resto) == len(items):
        return None
    _apren_guardar(resto)
    return True


REC_ARCH = os.path.join(COLA, "recordatorios.json")  # DB local de recordatorios/rutinas
REC_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
            "viernes": 4, "sabado": 5, "domingo": 6}


def _rec_cargar() -> list:
    try:
        with open(REC_ARCH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _rec_guardar(items: list) -> None:
    try:
        os.makedirs(COLA, exist_ok=True)
        with open(REC_ARCH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
    except Exception as e:
        print("[CEO-BOT] no pude guardar recordatorios.json: %s" % str(e)[:120], flush=True)


def _rec_norm(s: str) -> str:
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        s = s.replace(a, b)
    return s


def _rec_parsear(resto: str):
    """Lenguaje natural -> (ts_disparo, diaria, texto) o (None, False, mensaje_uso)."""
    import re as _re
    import datetime as _dt
    USO = ("Uso: /recordar en 30 min|2 horas <texto> | manana|hoy HH:MM <texto> | "
           "lunes..domingo HH:MM <texto> | HH:MM <texto> | diaria HH:MM <texto>")
    r = _rec_norm(resto.strip())
    if not r:
        return None, False, USO
    ahora = _dt.datetime.now()
    m = _re.match(r"en\s+(\d+)\s*(min\w*|hora\w*|h)\s+(.+)", r)
    if m:
        n, u, texto = int(m.group(1)), m.group(2), m.group(3).strip()
        if not texto:
            return None, False, USO
        delta = _dt.timedelta(minutes=n) if u.startswith("min") else _dt.timedelta(hours=n)
        return (ahora + delta).timestamp(), False, texto[:500]
    m = _re.match(r"diaria\s+(\d{1,2}):(\d{2})\s+(.+)", r)
    if m:
        h, mi, texto = int(m.group(1)), int(m.group(2)), m.group(3).strip()
        if not (0 <= h < 24 and 0 <= mi < 60) or not texto:
            return None, False, USO
        tiro = ahora.replace(hour=h, minute=mi, second=0, microsecond=0)
        if tiro <= ahora:
            tiro += _dt.timedelta(days=1)
        return tiro.timestamp(), True, texto[:500]
    m = _re.match(r"(hoy|manana)\s+(\d{1,2}):(\d{2})\s+(.+)", r)
    if m:
        dia, h, mi, texto = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).strip()
        if not (0 <= h < 24 and 0 <= mi < 60) or not texto:
            return None, False, USO
        tiro = ahora.replace(hour=h, minute=mi, second=0, microsecond=0)
        if dia == "manana":
            tiro += _dt.timedelta(days=1)
        elif tiro <= ahora:
            tiro += _dt.timedelta(days=1)
        return tiro.timestamp(), False, texto[:500]
    m = _re.match(r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2}):(\d{2})\s+(.+)", r)
    if m:
        h, mi, texto = int(m.group(2)), int(m.group(3)), m.group(4).strip()
        if not (0 <= h < 24 and 0 <= mi < 60) or not texto:
            return None, False, USO
        ahead = (REC_DIAS[m.group(1)] - ahora.weekday()) % 7
        tiro = (ahora + _dt.timedelta(days=ahead)).replace(hour=h, minute=mi, second=0, microsecond=0)
        if tiro <= ahora:
            tiro += _dt.timedelta(days=7)
        return tiro.timestamp(), False, texto[:500]
    m = _re.match(r"(\d{1,2}):(\d{2})\s+(.+)", r)
    if m:
        h, mi, texto = int(m.group(1)), int(m.group(2)), m.group(3).strip()
        if not (0 <= h < 24 and 0 <= mi < 60) or not texto:
            return None, False, USO
        tiro = ahora.replace(hour=h, minute=mi, second=0, microsecond=0)
        if tiro <= ahora:
            tiro += _dt.timedelta(days=1)
        return tiro.timestamp(), False, texto[:500]
    return None, False, USO


def _rec_agregar(chat: str, autor: str, ts: float, texto: str, diaria: bool) -> int:
    items = _rec_cargar()
    nid = max([x.get("id", 0) for x in items] + [0]) + 1
    items.append({"id": nid, "chat": chat, "autor": autor, "texto": texto,
                  "ts": ts, "diaria": diaria, "estado": "pendiente",
                  "creado": time.time()})
    _rec_guardar(items)
    return nid


def _rec_borrar(nid: int, chat: str, es_admin: bool):
    items = _rec_cargar()
    for x in items:
        if x.get("id") == nid and x.get("estado") == "pendiente":
            if str(x.get("chat")) != str(chat) and not es_admin:
                return "ajeno"
            x["estado"] = "cancelado"
            _rec_guardar(items)
            return "ok"
    return None


def _rec_listar(chat: str, es_admin: bool) -> str:
    import datetime as _dt
    items = [x for x in _rec_cargar() if x.get("estado") == "pendiente"]
    if not es_admin:
        items = [x for x in items if str(x.get("chat")) == str(chat)]
    if not items:
        return "Sin recordatorios pendientes."
    items.sort(key=lambda x: x.get("ts", 0))
    lineas = []
    for x in items:
        cuando = _dt.datetime.fromtimestamp(x["ts"]).strftime("%d %H:%M")
        quien = "" if str(x.get("chat")) == str(chat) else " (%s)" % x.get("autor", "?")
        rep = " [diaria]" if x.get("diaria") else ""
        lineas.append("#%d %s%s: %s%s" % (x["id"], cuando, rep, x.get("texto", "")[:80], quien))
    return "Recordatorios:\n" + "\n".join(lineas)


def _recordatorios_loop():
    """Hilo de entrega: cada 30s dispara los vencidos (diaria se reprograma +24h)."""
    while True:
        try:
            items = _rec_cargar()
            ahora = time.time()
            cambio = False
            for x in items:
                if x.get("estado") == "pendiente" and x.get("ts", 0) <= ahora:
                    try:
                        enviar(str(x["chat"]), "Recordatorio: %s" % x.get("texto", ""))
                    except Exception as e:
                        print("[CEO-BOT] no pude entregar rec #%d: %s"
                              % (x.get("id"), str(e)[:120]), flush=True)
                        continue
                    if x.get("diaria"):
                        x["ts"] = x["ts"] + 86400
                    else:
                        x["estado"] = "hecho"
                    cambio = True
                    print("[CEO-BOT] recordatorio #%d entregado" % x.get("id"), flush=True)
            if cambio:
                _rec_guardar(items)
        except Exception as e:
            print("[CEO-BOT] loop recordatorios: %s" % str(e)[:150], flush=True)
        time.sleep(30)


ACCESO_TOTAL = ("comandante", "ceo", "dev")  # dev = conservante con planta completa


def _nuevo_id_leer() -> dict:
    try:
        with open(NUEVO_ID_ARCH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def rol_de(chat: str) -> str:
    if ROLES:
        if chat in ROLES:
            return ROLES[chat]
        # id autorizado pero sin rol declarado
        if NUEVO_ID_ROL in ACCESO_TOTAL:  # dev = conservante con planta completa
            previo = _nuevo_id_leer()
            if not previo.get("id"):
                dato = {"id": chat, "rol": NUEVO_ID_ROL, "ts": time.time()}
                try:
                    os.makedirs(COLA, exist_ok=True)
                    with open(NUEVO_ID_ARCH, "w", encoding="utf-8") as f:
                        json.dump(dato, f, ensure_ascii=False)
                    print("[CEO-BOT] id %s -> rol %s (primer id nuevo, consumo unico)"
                          % (chat, NUEVO_ID_ROL), flush=True)
                except Exception:
                    return "conservante"
                return NUEVO_ID_ROL
        return "conservante"
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


def _respaldo_vivo() -> bool:
    """¿Está vivo el puente CrewAI viejo (:4210)? Se usa solo como respaldo."""
    try:
        with urllib.request.urlopen(PUENTE + "/estado", timeout=5):
            return True
    except Exception:
        return False


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
        lineas = ["🧵 ESTADO COLMENA (tablero instantáneo)"]
        if PUENTE_MODO == "openbot":
            lineas.append("🧩 openbot: %s"
                          % ("✅ arriba " + openbot_api.BASE
                             if openbot_api.disponible()
                             else "⚠️ CAÍDO " + openbot_api.BASE))
        lineas.append("✅ puente vivo (%ds desde arranque)" % d.get("uptime_s", 0))
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
    nombre = nombre_de(chat, item.get("remitente", ""))
    es_comandante = rol in ACCESO_TOTAL
    es_admin = rol in ("dev", "ceo")
    if texto.startswith("/quiensoy"):
        r = "Eres %s · rol: %s (chat %s)" % (nombre, rol, chat)
    elif texto.startswith("/solicitudes"):
        if not es_admin:
            r = "🚫 Solo el administrador ve las solicitudes. Tu rol: %s." % rol
        else:
            d = _acceso_cargar()
            pend = [(c, s) for c, s in d.get("solicitudes", {}).items()
                    if s.get("estado") == "pendiente"]
            if not pend:
                r = "📭 Sin solicitudes pendientes."
            else:
                r = "📬 Solicitudes pendientes:\n" + "\n".join(
                    "- %s · id %s (%s)" % (s.get("nombre", "?"), c,
                                           s.get("first_name") or s.get("username") or "?")
                    for c, s in pend)
    elif texto.startswith("/autorizar"):
        if not es_admin:
            r = "🚫 Solo el administrador autoriza accesos. Tu rol: %s." % rol
        else:
            p = texto.split()
            if len(p) < 2 or not p[1].isdigit():
                r = "Uso: /autorizar <id> [conservante|comandante]"
            else:
                cid, rol_new = p[1], (p[2].lower() if len(p) > 2 else "conservante")
                if rol_new not in ROLES_AUTORIZABLES:
                    r = "Rol inválido: solo %s (dev/ceo se dan por registry)." % "/".join(ROLES_AUTORIZABLES)
                else:
                    d = _acceso_cargar()
                    sol = d.get("solicitudes", {}).get(cid, {})
                    apodo = sol.get("nombre") or nombre_de(cid)
                    d["usuarios"][cid] = {"nombre": apodo, "rol": rol_new,
                                          "autorizado_por": nombre, "ts": time.time()}
                    d["solicitudes"].pop(cid, None)
                    _acceso_guardar(d)
                    PERMITIDOS.add(cid)
                    ROLES[cid] = rol_new
                    NOMBRES[cid] = apodo
                    enviar(cid, "✅ Acceso autorizado: eres %s · rol %s. "
                                "Manda /quiensoy para verificar." % (apodo, rol_new))
                    print("[CEO-BOT] autorizado %s (%s) rol %s por %s"
                          % (cid, apodo, rol_new, chat), flush=True)
                    r = "✅ %s (id %s) registrado como %s." % (apodo, cid, rol_new)
    elif texto.startswith("/rechazar"):
        if not es_admin:
            r = "🚫 Solo el administrador rechaza accesos. Tu rol: %s." % rol
        else:
            p = texto.split()
            if len(p) < 2 or not p[1].isdigit():
                r = "Uso: /rechazar <id> [motivo]"
            else:
                cid = p[1]
                motivo = " ".join(p[2:])[:120]
                d = _acceso_cargar()
                sol = d.get("solicitudes", {}).pop(cid, {})
                _acceso_guardar(d)
                enviar(cid, "🚫 Tu solicitud de acceso fue rechazada.%s"
                            % (" Motivo: " + motivo if motivo else ""))
                print("[CEO-BOT] rechazado %s por %s" % (cid, chat), flush=True)
                r = "🚫 Solicitud de %s rechazada." % (sol.get("nombre") or cid)
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
    elif texto.startswith("/aprendizajes"):
        items = _apren_cargar()
        if not items:
            r = "📚 Aún no me han enseñado nada. Usa /aprender tema | dato."
        else:
            r = "📚 Lo que me han enseñado:\n" + "\n".join(
                "#%d %s (por %s)" % (a.get("id"), a.get("tema"), a.get("autor", "?"))
                for a in items)
    elif texto.startswith("/aprender"):
        if not es_comandante:
            r = "🚫 Solo el Comandante (o Dev) me enseña. Tu rol: %s." % rol
        else:
            resto = texto[len("/aprender"):].strip()
            if "|" not in resto:
                r = "Uso: /aprender tema | dato que debo recordar"
            else:
                tema, dato = (x.strip() for x in resto.split("|", 1))
                if not tema or not dato:
                    r = "Uso: /aprender tema | dato que debo recordar"
                else:
                    nid = _apren_agregar(tema[:80], dato[:1500], nombre)
                    print("[CEO-BOT] aprendizaje #%d '%s' por %s"
                          % (nid, tema[:60], chat), flush=True)
                    r = "🧠 Anotado #%d (%s). Lo usaré como contexto en tus órdenes." % (nid, tema)
    elif texto.startswith("/olvidar_rec"):
        p = texto.split()
        if len(p) < 2 or not p[1].lstrip("#").isdigit():
            r = "Uso: /olvidar_rec <id>  (ver ids con /recordatorios)"
        else:
            bor = _rec_borrar(int(p[1].lstrip("#")), chat, es_admin)
            if bor == "ok":
                r = "🗑️ Recordatorio #%s cancelado." % p[1].lstrip("#")
            elif bor == "ajeno":
                r = "Ese recordatorio no es tuyo; pide a un admin que lo cancele."
            else:
                r = "No existe recordatorio #%s pendiente." % p[1].lstrip("#")
    elif texto.startswith("/olvidar"):
        if not es_comandante:
            r = "🚫 Solo el Comandante (o Dev) borra memoria. Tu rol: %s." % rol
        else:
            p = texto.split()
            if len(p) < 2 or not p[1].lstrip("#").isdigit():
                r = "Uso: /olvidar <id>  (ver ids con /aprendizajes)"
            elif _apren_borrar(int(p[1].lstrip("#"))):
                r = "🗑️ Olvidé el #%s." % p[1].lstrip("#")
            else:
                r = "No existe aprendizaje #%s." % p[1].lstrip("#")
    elif texto.startswith("/recordatorios"):
        r = _rec_listar(chat, es_admin)
    elif texto.startswith("/recordar"):
        if not es_comandante:
            r = "🚫 Solo el Comandante (o Dev) programa recordatorios. Tu rol: %s." % rol
        else:
            ts, diaria, res = _rec_parsear(texto[len("/recordar"):])
            if ts is None:
                r = res
            else:
                import datetime as _dt
                nid = _rec_agregar(chat, nombre, ts, res, diaria)
                cuando = _dt.datetime.fromtimestamp(ts).strftime("%d %H:%M")
                print("[CEO-BOT] recordatorio #%d para %s (%s)" % (nid, chat, cuando), flush=True)
                r = "⏰ Anotado #%d para el %s%s: %s" % (
                    nid, cuando, " (diaria)" if diaria else "", res[:120])
    elif texto.startswith("/start") or texto.startswith("/ayuda"):
        r = ("Soy el control del Orquestador. Eres %s · rol: %s.\n"
             "Comandos: /estado /cola /gates /quiensoy /aprendizajes /recordatorios%s%s"
             % (nombre, rol,
                " /aprobar <id> /rechazar <id> + órdenes en texto /aprender tema | dato /olvidar <id> /recordar ... /olvidar_rec <id>" if es_comandante
                else " (solo lectura)",
                " | admin: /solicitudes /autorizar <id> [rol] /rechazar <id>" if es_admin else ""))
    else:
        ctx = _historial(chat)
        # Identidad inyectada: el cerebro sabe QUIEN habla y con QUE rol,
        # asi "sabes quien soy?" se responde con datos, no con memoria generica.
        # Memoria enseñada: aprendizajes relevantes viajan como contexto.
        rel = _apren_relevantes(texto)
        memoria = ""
        if rel:
            memoria = "\n[Lo que me enseñaron: " + " | ".join(
                "#%d %s: %s" % (a.get("id"), a.get("tema"), a.get("dato"))
                for a in rel) + "]"
        firmado = "[Soy %s, rol %s] %s%s" % (nombre, rol, texto, memoria)
        if PUENTE_MODO == "openbot":
            # F4b: texto crudo al thread de OpenBot — el historial/plan y la
            # confirmación ya viven en la memoria del thread de OpenBot.
            try:
                respuesta = openbot_api.orquestar(chat, firmado)
            except Exception as e:
                causa = str(e)[:200]
                if _respaldo_vivo():
                    respuesta = ("🔧 Respaldo CrewAI (OpenBot falló: %s)\n\n%s"
                                 % (causa[:110],
                                    _presentar(puente_orquestar(firmado,
                                                                contexto=ctx))))
                else:
                    respuesta = ("⚠️ OpenBot no respondió: %s\n"
                                 "Tampoco hay respaldo CrewAI vivo. "
                                 "Revisa el stack y usa /estado." % causa)
        else:
            respuesta = puente_orquestar(firmado, contexto=ctx)
        if not respuesta.strip():
            respuesta = "(respuesta vacía del orquestador)"
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
    _acceso_merge()  # usuarios autorizados en la DB local entran como permitidos
    hechos = _hechos_ids()
    offset = _offset_cargar()
    for _ in range(N_WORKERS):
        threading.Thread(target=_trabajador, daemon=True).start()
    threading.Thread(target=_recordatorios_loop, daemon=True).start()
    print("[CEO-BOT] hilo de recordatorios activo (cada 30s)", flush=True)
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
                de = msg.get("from") or {}
                remitente_tg = str(de.get("first_name") or de.get("username") or "").strip()
                if chat not in PERMITIDOS:
                    _atender_solicitud(chat, texto, de)
                    continue
                uid = up["update_id"]
                if uid in hechos:
                    continue
                with COLA_LOCK:
                    items = _items_leer()
                    if any(it["update_id"] == uid for it in items):
                        continue
                    items.append({"update_id": uid, "chat": chat,
                                  "remitente": remitente_tg,
                                  "texto": texto[:4000], "estado": "pendiente",
                                  "ts": time.time()})
                    _items_escribir(items)
                if not texto.startswith("/"):
                    enviar(chat, "📥 En cola, %s. Hay %d orden(es) esperando — te contesto "
                                 "en cuanto le toque." % (nombre_de(chat, remitente_tg), len(items)))
        except Exception as e:
            print("[CEO-BOT] error: %s" % str(e)[:200], flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
