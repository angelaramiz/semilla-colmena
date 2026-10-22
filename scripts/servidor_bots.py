# scripts/servidor_bots.py
# Supervisor 24/7 de bots: mantiene vivos ceo_bot (Telegram) y el MCP de investigacion (:8221).
# Lee los secretos de la registry HKCU del host (nunca se hardcodean aqui).
# Uso: uv run python scripts/servidor_bots.py  (lo lanza la tarea de Task Scheduler al boot)
import os
import sys
import time
import json
import subprocess
import io
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(REPO, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "servidor_bots.log")

logging.basicConfig(
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("servidor_bots")

BACKOFF = [10, 30, 60, 120, 300]  # s de espera ante crashes repetidos


def _reg_lee(nombre: str) -> str:
    try:
        out = subprocess.run(
            ["reg", "query", r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "/v", nombre],
            capture_output=True, text=True).stdout
        for l in out.splitlines():
            if nombre in l:
                return l.split()[-1]
    except Exception:
        return ""
    try:
        out = subprocess.run(
            ["reg", "query", r"HKCU\Environment", "/v", nombre],
            capture_output=True, text=True).stdout
        for l in out.splitlines():
            if nombre in l:
                return l.split()[-1]
    except Exception:
        return ""
    return ""


def _hijos():
    """Lista de (nombre, args, cwd, env-extra).

    SERVIDOR_MCP_ONLY=1 levanta solo el MCP (fase de despliegue,
    antes del corte de la escucha de Telegram)."""
    solo_mcp = os.environ.get("SERVIDOR_MCP_ONLY", "").strip() == "1"
    env_base = {}
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_IDS", "TELEGRAM_ROLES"):
        v = _reg_lee(k)
        if v:
            env_base[k] = v
    if not env_base.get("TELEGRAM_BOT_TOKEN"):
        log.warning("TELEGRAM_BOT_TOKEN ausente en registry; solo levantara el MCP")
        solo_mcp = True
        log.warning("corriendo en modo SERVIDOR_MCP_ONLY")

    mcp_cmd = [os.path.join(REPO, ".venv", "Scripts", "python.exe"),
               os.path.join(REPO, "investigacion", "servidor_mcp.py"),
               "--http", "--port", "8221", "--host", "0.0.0.0"]
    if not os.path.exists(mcp_cmd[0]):
        mcp_cmd = ["uv", "run", "python",
                   os.path.join(REPO, "investigacion", "servidor_mcp.py"),
                   "--http", "--port", "8221", "--host", "0.0.0.0"]

    bot_cmd = [os.path.join(REPO, ".venv", "Scripts", "python.exe"),
               os.path.join(REPO, "puente_telegram", "ceo_bot.py")]
    if not os.path.exists(bot_cmd[0]):
        bot_cmd = ["uv", "run", "python", os.path.join(REPO, "puente_telegram", "ceo_bot.py")]

    return [
        ("mcp-8221", mcp_cmd, REPO, {}),
        ("ceo-bot", bot_cmd, REPO, env_base),
    ]


def main():
    log.info("Servidor de bots arrancando (repo: %s)", REPO)
    estados = {}  # nombre -> {"proc": Popen|None, "fallos": int, "espera": s}

    solo_mcp_mode = os.environ.get("SERVIDOR_MCP_ONLY", "").strip() == "1"
    hijos = _hijos()
    if solo_mcp_mode:
        hijos = [h for h in hijos if h[0] == "mcp-8221"]
    for nombre, cmd, cwd, env_extra in hijos:
        estados[nombre] = {"cmd": cmd, "cwd": cwd, "env_extra": env_extra,
                           "proc": None, "fallos": 0, "next": 0.0}

    while True:
        ahora = time.time()
        for nombre, st in estados.items():
            proc = st["proc"]
            vivo = proc is not None and proc.poll() is None
            if not vivo and ahora >= st["next"]:
                st["fallos"] += 1
                backoff = BACKOFF[min(st["fallos"] - 1, len(BACKOFF) - 1)]
                st["next"] = ahora + backoff
                log.info("(%s) arranque #%d (backoff %ds)", nombre, st["fallos"], backoff)
                try:
                    env = os.environ.copy()
                    env.update(st["env_extra"])
                    if sys.platform == "win32":
                        env["PYTHONIOENCODING"] = "utf-8"
                    st["proc"] = subprocess.Popen(
                        st["cmd"], cwd=st["cwd"], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    log.info("(%s) pid %s", nombre, st["proc"].pid)
                except Exception as e:
                    log.error("(%s) no se pudo arrancar: %s", nombre, e)
        time.sleep(15)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("detenido manualmente")
