#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoría de secretos antes del commit (pre-commit).

Corre localmente, sin depender de GitHub Actions (que requiere Pro).
Escanea los archivos que están a punto de commitearse y aborta si detecta
secretos o archivos sensibles.

Uso:
    python scripts/check_secrets.py            # escanea staged
    python scripts/check_secrets.py --all      # escanea todo el repo tracked
"""
import subprocess
import sys
import re
import os

# Asegurar UTF-8 en Windows (para imprimir ✅/⚠️)
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PATRONES = [
    (r"sk-or-v1-[a-zA-Z0-9]{20,}", "OpenRouter API key"),
    (r"\bAIza[a-zA-Z0-9_-]{30,}\b", "Google API key"),
    (r"\bsb_publishable_[a-zA-Z0-9]{10,}", "Supabase publishable key"),
    (r"\bsb_secret_[a-zA-Z0-9]{10,}", "Supabase SECRET key"),
    (r"\beyJhbGciOi[a-zA-Z0-9_.-]{20,}", "JWT"),
    (r"\bghp_[a-zA-Z0-9]{20,}", "GitHub PAT"),
    (r"\bxox[baprs]-[a-zA-Z0-9-]{10,}", "Slack token"),
    (r"\bAKIA[A-Z0-9]{16}", "AWS access key"),
    (r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----", "Clave privada"),
    (r"[A-Za-z0-9_-]+:\w{32,}@", "Credenciales en URL (password embebida)"),
]

# Si el contenido es de placeholder (ej. en .env.example), no alarmar.
_IGNORAR_CADENAS = ["tu-key", "tu-proyecto", "genera-un", "sk-tu-clave", "AIzaSy...", "sb_publishable_tu-key"]

ARCHIVOS_SENSIBLES = [
    r"\.env(local|\.prod|\.secret)?$",
    r"\.db$", r"\.sqlite", r"manifiesto\.yaml$",
    r"\.pem$", r"\.key$", r"id_rsa", r"\.p12$", r"\.jks$",
]


def archivos_a_checar(todo: bool) -> list:
    if todo:
        res = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
        return [l for l in res.stdout.splitlines() if l.strip()]
    res = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)
    return [l for l in res.stdout.splitlines() if l.strip()]


def main() -> int:
    todo = "--all" in sys.argv
    fs = archivos_a_checar(todo)
    errores = []
    for ruta in fs:
        bajo = ruta.lower()
        if any(re.search(p, bajo) for p in ARCHIVOS_SENSIBLES):
            errores.append(f"[SENSIBLE] {ruta}: archivo de secretos/datos no debe commitearse")
            continue
        try:
            texto = open(ruta, "r", encoding="utf-8", errors="replace").read()
        except (OSError, FileNotFoundError):
            continue
        for pat, nombre in PATRONES:
            if not re.search(pat, texto):
                continue
            if any(ig in texto for ig in _IGNORAR_CADENAS):
                continue
            errores.append(f"[SECRETO] {ruta}: posible {nombre}")
            break

    if errores:
        print("⚠️  Auditoría de secretos detectó posibles fugas:\n")
        for e in errores:
            print("  -", e)
        print("\nEnvía solo lo intencional. Si son runtime, están en .gitignore; "
              "para unstaged: `git reset <ruta>`")
        return 1
    print(f"✅ Auditoría de secretos OK ({len(fs)} archivo(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())