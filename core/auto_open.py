# core/auto_open.py
"""
Apertura automática del panel web al arrancar el servidor (opt-in, solo localhost).

Diseño aprobado por TPM (ciclo AUTO-APERTURA WEB):
- Flag `AUTO_OPEN_BROWSER` en `.env` (`true/1/yes`, case-insensitive; por defecto `false`).
- Solo abre si el host es local (`127.0.0.1`, `localhost`, `::1`).
- Apertura no bloqueante: `threading.Timer(1.5, ...)` con `daemon=True`.
- Silencioso ante cualquier error (entornos headless/docker no deben tumbar uvicorn).
- Una sola apertura por URL en cada arranque del proceso.
- Solo stdlib (`os`, `threading`, `webbrowser`).

Uso desde cada panel (en su evento `startup` de FastAPI):
    from core.auto_open import abrir_navegador_si_local
    abrir_navegador_si_local("http://127.0.0.1:8000/")
"""
import os
import threading
import webbrowser

_ABIERTOS: set = set()


def _flag_activo() -> bool:
    """True si AUTO_OPEN_BROWSER es afirmativo (default: False)."""
    return os.getenv("AUTO_OPEN_BROWSER", "false").strip().lower() in (
        "true", "1", "yes", "on", "si",
    )


def _es_local(host: str) -> bool:
    """True si el host es loopback reconocido."""
    return (host or "").strip().lower() in ("127.0.0.1", "localhost", "::1")


def abrir_navegador_si_local(url: str, host: str = "127.0.0.1") -> bool:
    """Abre `url` en el navegador una sola vez si el flag y el host lo permiten.

    Nunca bloquea al llamador y nunca lanza excepciones: en headless/docker
    simplemente no hace nada. Retorna True solo si programó la apertura.
    """
    try:
        if not _flag_activo():
            return False
        if not _es_local(host):
            return False
        clave = (url or "").strip()
        if not clave:
            return False
        if clave in _ABIERTOS:
            return False
        _ABIERTOS.add(clave)
        t = threading.Timer(1.5, lambda: webbrowser.open(clave))
        t.daemon = True
        t.start()
        return True
    except Exception:
        return False
