# Dockerfile — Árbol de la colmena (obrero / comandante)
# Construye un contenedor autocontenido con TODAS las dependencias de la semilla.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# --- Instalar dependencias (filtrando pywin32, que es Windows-only) ---
COPY requirements.txt .
RUN python - <<'PY'
import pathlib, subprocess
lines = [l for l in pathlib.Path("requirements.txt").read_text().splitlines() if "pywin32" not in l]
pathlib.Path("requirements.linux.txt").write_text("\n".join(lines))
subprocess.check_call(["pip", "install", "-q", "-r", "requirements.linux.txt"])
PY

# --- Código de la agencia ---
COPY . .

# --- CodeGraph: índice de código para búsquedas del agente (opcional, no rompe el build) ---
# Requiere Node/npm. Si no está disponible, se omite sin error.
RUN (command -v npm >/dev/null 2>&1 && npm install -g @colbymchenry/codegraph || echo 'npm no disponible; codegraph omitido') \
    && (command -v codegraph >/dev/null 2>&1 && codegraph init || echo 'codegraph index omitido') || true

# Carpetas compartidas (el volumen /shared la pisa en runtime)
RUN mkdir -p shared/borradores shared/memoria shared/aprobaciones shared/reportes

# Exponer puertos web: 8000 (Tronco/obrero), 8001 (Comandante)
EXPOSE 8000 8001

# Comando por defecto: obrero (Tronco + ramas 24/7 vía web_server)
CMD ["uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8000"]