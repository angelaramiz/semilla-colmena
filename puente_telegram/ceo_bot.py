# puente_telegram/ceo_bot.py — Control remoto del CEO Humano por Telegram.
#
# Polling contra Bot API (sin webhook público, sin dependencias: solo stdlib).
# Reenvía órdenes al Orquestador (puente AG-UI) y devuelve el resumen.
# Solo responde a chats en TELEGRAM_ALLOWED_IDS (el CEO y quien él autorice).
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
import time
import urllib.parse
import urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
PERMITIDOS = {x.strip() for x in os.environ.get("TELEGRAM_ALLOWED_IDS", "").split(",") if x.strip()}
PUENTE = os.environ.get("PUENTE_URL", "http://127.0.0.1:4210").rstrip("/")
COMANDANTE = os.environ.get("COMANDANTE_URL", "http://127.0.0.1:8001").rstrip("/")
CTOKEN = os.environ.get("COMANDANTE_WEB_TOKEN", "").strip()
API = "https://api.telegram.org/bot%s" % TOKEN


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


def puente_orquestar(texto: str) -> str:
    """Manda la orden al Orquestador y junta los deltas SSE en respuesta final."""
    body = json.dumps({"threadId": "tg-ceo", "runId": "tg-%d" % int(time.time()),
                       "messages": [{"role": "user", "content": texto}]}).encode()
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


def main():
    if not TOKEN or not PERMITIDOS:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN o TELEGRAM_ALLOWED_IDS")
    print("[CEO-BOT] escuchando como control del Orquestador…", flush=True)
    offset = 0
    while True:
        try:
            res = tg("getUpdates", {"offset": offset, "timeout": 50}, timeout=70)
            for up in res.get("result", []):
                offset = up["update_id"] + 1
                msg = up.get("message") or {}
                chat = str((msg.get("chat") or {}).get("id", ""))
                texto = (msg.get("text") or "").strip()
                if not texto:
                    continue
                if chat not in PERMITIDOS:
                    enviar(chat, "No autorizado. Este bot solo responde al CEO.")
                    continue
                if texto.startswith("/gates"):
                    enviar(chat, cmd_gates())
                elif texto.startswith("/aprobar"):
                    p = texto.split()
                    enviar(chat, cmd_resolver(p[1], "aprobada") if len(p) > 1 else "Uso: /aprobar <id>")
                elif texto.startswith("/rechazar"):
                    p = texto.split()
                    enviar(chat, cmd_resolver(p[1], "rechazada") if len(p) > 1 else "Uso: /rechazar <id>")
                elif texto.startswith("/estado"):
                    enviar(chat, puente_orquestar("Reporta en 5 líneas: estado de ramas y gates pendientes."))
                elif texto.startswith("/start") or texto.startswith("/ayuda"):
                    enviar(chat, "Soy el control del Orquestador. Mándame la orden en texto.\n"
                                 "Comandos: /estado /gates /aprobar <id> /rechazar <id>")
                else:
                    enviar(chat, puente_orquestar(texto))
        except Exception as e:
            print("[CEO-BOT] error: %s" % str(e)[:200], flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
