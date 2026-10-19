# core/ejecutar.py — Hook de ejecución restringida (allowlist).
#
# Todo subproceso del sistema pasa por aquí:
# - Solo binarios en BINARIOS_PERMITIDOS (rutas exactas, sin PATH ambiguo).
# - shell=False siempre (prohibido shell=True en el repo).
# - Sin secretos en argumentos (los tokens viajan por entorno, no argv).
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

BINARIOS_PERMITIDOS = {
    sys.executable,  # python del venv activo
    os.path.join(RAIZ, ".venv", "Scripts", "python.exe"),
    os.path.join(RAIZ, "puente_agui", ".venv", "Scripts", "python.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
}


def _normalizar(binario: str) -> str:
    return os.path.normcase(os.path.abspath(binario))


_PERMITIDOS_NORM = {_normalizar(b) for b in BINARIOS_PERMITIDOS}


def verificar(binario: str) -> str:
    """Lanza PermissionError si el binario no está en la allowlist."""
    nb = _normalizar(binario)
    if nb not in _PERMITIDOS_NORM:
        raise PermissionError("binario no permitido por hook: %s" % binario)
    return binario


def run_seguro(args: list, **kw) -> subprocess.CompletedProcess:
    """subprocess.run con allowlist + shell=False forzado."""
    if not args:
        raise ValueError("args vacío")
    verificar(args[0])
    kw["shell"] = False
    return subprocess.run(args, **kw)


class PopenSeguro(subprocess.Popen):
    """subprocess.Popen con allowlist + shell=False forzado."""
    def __init__(self, args, **kw):
        if not args:
            raise ValueError("args vacío")
        verificar(args[0] if isinstance(args, list) else args.split()[0])
        kw["shell"] = False
        super().__init__(args, **kw)
