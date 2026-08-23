#!/usr/bin/env bash
# ============================================================================
#  sembrar.sh  — Crea un ÁRBOL (instancia aislada de la agencia) desde la SEMILLA.
#
#  Uso:
#    sembrar.sh <arbol_id> [--nombre "Cliente X"] [--dir RUTA]
#
#  Ejemplos:
#    sembrar.sh cliente_01 --nombre "La Parroquia"                 # en el dir actual
#    sembrar.sh cliente_02 --dir /srv/agencias/cliente_02          # en otra ruta
#
#  Funciona con bash (Linux/macOS, o Git Bash/WSL en Windows).
#  La SEMILLA jamás se modifica: cada árbol genera su propio .env, DB y /shared.
# ============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# 0) Argumentos y entorno
# ---------------------------------------------------------------------------
ARBOL_ID="${1:?Uso: sembrar.sh <arbol_id> [--rol obrero|comandante|heredero] [--nombre \"...\"] [--dir RUTA]}"
shift
ARBOL_NOMBRE=""
TARGET_DIR=""
ARBOL_ROL=""
HEREDERO_DE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nombre)      ARBOL_NOMBRE="$2"; shift 2 ;;
    --dir)         TARGET_DIR="$2";   shift 2 ;;
    --rol)         ARBOL_ROL="$2";    shift 2 ;;
    --heredero-de) HEREDERO_DE="$2";  shift 2 ;;
    *) echo "⚠️  Argumento desconocido: $1"; exit 1 ;;
  esac
done
ARBOL_NOMBRE="${ARBOL_NOMBRE:-$ARBOL_ID}"
# Rol por defecto según la semilla/plantilla; los válidos son obrero|comandante|heredero
ARBOL_ROL="${ARBOL_ROL:-$(grep -E '^ARBOL_ROL=' .env.example | head -1 | cut -d= -f2- | tr -d '"' || true)}"
ARBOL_ROL="${ARBOL_ROL:-obrero}"
case "$ARBOL_ROL" in
  obrero|comandante|conservante|heredero) : ;;
  *) echo "❌ Rol inválido: $ARBOL_ROL (obrero|comandante|conservante|heredero)"; exit 1 ;;
esac

# ---------------------------------------------------------------------------
# 0.5) AUTO-BOOTSTRAP — la semilla prepara su propio entorno antes de germinar
# ---------------------------------------------------------------------------
REPO_GIT="https://github.com/angelaramiz/semilla-colmena.git"
DOCKER_FLAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --docker)  DOCKER_FLAG="1"; shift ;;
    --no-install) echo "→ --no-install: no se instalarán precondiciones del sistema"; shift ;;
    *) break ;;
  esac
done

is_root() { [ "$(id -u 2>/dev/null)" = "0" ]; }
has_sudo() { command -v sudo >/dev/null 2>&1; }
can_install() { is_root || has_sudo; }
# Ejecuta un comando de instalación con privilegios (root directo o sudo).
_priv() { if is_root; then "$@"; else sudo "$@"; fi; }

echo "→ [BOOTSTRAP] verificando precondiciones base..."

# --- git ---
if ! command -v git >/dev/null 2>&1; then
  if can_install; then
    echo "→ instalando git (sudo)..."
    _priv apt-get -y install git 2>/dev/null || _priv apt install -y git 2>/dev/null || echo "⚠️  no se pudo instalar git"
  else
    echo "⚠️  git no disponible y sin sudo para instalarlo"
  fi
fi

# --- curl ---
if ! command -v curl >/dev/null 2>&1; then
  if can_install; then
    echo "→ instalando curl..."
    _priv apt-get -y install curl 2>/dev/null || echo "⚠️  no se pudo instalar curl"
  fi
fi

# --- python ---
if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  if can_install; then
    echo "→ instalando python..."
    _priv apt-get -y install python3 python3-pip 2>/dev/null || echo "⚠️  no se pudo instalar python"
  fi
fi

# --- Docker (solo si --docker) ---
if [[ -n "$DOCKER_FLAG" ]] && ! command -v docker >/dev/null 2>&1; then
  echo "→ instalando Docker (--docker)..."
  _priv sh -c "curl -fsSL https://get.docker.com/ | sh" 2>/dev/null || echo "⚠️  no se pudo instalar Docker"
fi

# --- AUTO-CLONADO: si no estamos dentro del repo, lo descargamos ---
if [[ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]]; then
  if [[ -n "$TARGET_DIR" ]]; then
    ROOT="$TARGET_DIR"
    if [[ ! -d "$ROOT/.git" ]]; then
      echo "→ clonando la semilla en $ROOT"
      mkdir -p "$ROOT"; git clone "$REPO_GIT" "$ROOT" 2>/dev/null || echo "⚠️  no se pudo clonar (revisa la URL/red)"
    fi
  else
    echo "→ no estás dentro del repo; clonando la semilla..."
    git clone "$REPO_GIT" semilla-colmena 2>/dev/null && cd semilla-colmena
  fi
fi

# Resolver el directorio del árbol
if [[ -n "$TARGET_DIR" ]]; then
  ROOT="$TARGET_DIR"
else
  ROOT="$(cd "$(dirname "$0")" && pwd)"
fi
if [[ ! -d "$ROOT" ]]; then
  echo "❌ No existe el directorio: $ROOT"; exit 1
fi
cd "$ROOT"

# Runner de Python: prefiere `uv run python`, cae a `python` si no hay uv
PY="uv run python"
command -v uv >/dev/null 2>&1 || PY="python"

echo "🌱 Sembrando árbol [$ARBOL_ID] en $ROOT"
echo "--------------------------------------------------------------"

# ---------------------------------------------------------------------------
# FASE GERMINACIÓN — la semilla crea sus propias dependencias
# ---------------------------------------------------------------------------
echo "🌱 [GERMINACIÓN] instalando dependencias y nutrientes"
# 0a) Dependencias del proyecto (semilla autocontenida)
if [[ -f "pyproject.toml" ]] && command -v uv >/dev/null 2>&1; then
  echo "→ uv sync (instala crewai, fastmcp, etc.)"
  uv sync || echo "⚠️  uv sync falló (revisa conexión/red)"
elif [[ -f "requirements.txt" ]]; then
  echo "→ pip install -r requirements.txt"
  $PY -m pip install -r requirements.txt -q || echo "⚠️  pip install falló"
fi
# 0b) Modelo local Ollama (nutriente local; no fatal si falta)
if command -v ollama >/dev/null 2>&1; then
  MODELO="${LOCAL_LLM_MODEL:-qwen3:27b}"
  echo "→ ollama pull $MODELO"
  ollama pull "$MODELO" 2>/dev/null || echo "⚠️  no se pudo descargar el modelo Ollama"
else
  echo "→ ollama no instalado; instálalo para usar el modelo local"
fi
# 0c) CodeGraph: instalar CLI + indexar el árbol (grafo para búsquedas del agente)
if command -v npm >/dev/null 2>&1; then
  echo "→ codegraph: instalando CLI e indexando el árbol"
  npm install -g @colbymchenry/codegraph >/dev/null 2>&1 || echo "⚠️  no se pudo instalar el CLI codegraph"
  if command -v codegraph >/dev/null 2>&1; then
    codegraph init >/dev/null 2>&1 && echo "✅ índice .codegraph/ generado" || echo "⚠️  codegraph init no ejecutado"
  else
    echo "⚠️  codegraph CLI no disponible tras instalar (revisa npm/Path)"
  fi
else
  echo "→ npm no disponible; sin índice codegraph (búsquedas del agente sin grafo)"
fi
# 0d) Tailscale: red privada de la colmena (instalar + unirse con token)
# Necesita sudo/root y un TAILSCALE_TOKEN en .env (auth key). No fatal si falta.
TS_TOKEN="$(grep -E '^TAILSCALE_TOKEN=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
if command -v tailscale >/dev/null 2>&1; then
  echo "→ tailscale ya instalado"
else
  echo "→ tailscale: instalando (requiere sudo)"
  if command -v curl >/dev/null 2>&1 && { [ "$(id -u 2>/dev/null)" = "0" ] || command -v sudo >/dev/null 2>&1; }; then
    curl -fsSL https://tailscale.com/install.sh | sh 2>/dev/null \
      && echo "✅ tailscale instalado" \
      || echo "⚠️  no se pudo instalar tailscale (revisa red/sudo)"
  else
    echo "⚠️  no se pudo instalar tailscale (sin curl o sin sudo)"
  fi
fi
if command -v tailscale >/dev/null 2>&1; then
  if [[ -n "$TS_TOKEN" ]]; then
    echo "→ tailscale: uniendo a la tailnet con token"
    tailscale up --authkey="$TS_TOKEN" --hostname="$ARBOL_ID" 2>/dev/null \
      && echo "✅ árbol conectado a la tailnet" \
      || echo "⚠️  tailscale up falló (revisa el token/permisos)"
  else
    echo "⚠️  sin TAILSCALE_TOKEN en .env: conecta manualmente con 'sudo tailscale up'"
  fi
fi

# 0e) SSH server key: verificar/generar clave para que el micelio/comandante
#     conecte por ssh (puerto 22) como alternativa a Tailscale. No fatal.
if command -v ssh-keygen >/dev/null 2>&1; then
  SSH_DIR="${HOME}/.ssh"
  SSH_KEY="${SSH_DIR}/id_ed25519"
  if [[ -f "${SSH_KEY}" ]]; then
    echo "→ ssh: ya existe clave ${SSH_KEY}"
  else
    mkdir -p "${SSH_DIR}"
    echo "→ ssh: generando clave ed25519 para el árbol"
    ssh-keygen -t ed25519 -f "${SSH_KEY}" -N "" -C "${ARBOL_ID}@colmena" >/dev/null 2>&1 \
      && echo "✅ clave SSH generada" || echo "⚠️  no se pudo generar la clave SSH"
  fi
  if [[ -f "${SSH_KEY}.pub" ]]; then
    echo "→ clave pública (cópiala al inventario del comandante):"
    cat "${SSH_KEY}.pub"
  fi
else
  echo "→ ssh-keygen no disponible; sin clave SSH (usa Tailscale o instala openssh)"
fi

# ---------------------------------------------------------------------------
# 1) .env — crear desde plantilla (nunca copiar el .env de otro árbol)
# ---------------------------------------------------------------------------
if [[ -f ".env" ]]; then
  echo "→ .env ya existe; NO se sobrescribe (verifica ARBOL_ID manualmente)."
else
  if [[ ! -f ".env.example" ]]; then
    echo "❌ No se encontró .env.example (¿es este el repositorio semilla?)."; exit 1
  fi
  cp .env.example .env
  echo "→ .env creado desde .env.example"
fi

# JWT secret único (genera si no está seteado)
JWT_SECRET="$(grep -E '^JWT_SECRET_KEY=' .env | head -1 | cut -d= -f2- || true)"
if [[ -z "$JWT_SECRET" || "$JWT_SECRET" == *"genera-un-secreto"* ]]; then
  JWT_SECRET="$($PY -c 'import secrets;print(secrets.token_hex(32))')"
  sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env && rm -f .env.bak
  echo "→ JWT_SECRET_KEY generado"
fi

# Identidad del árbol: sobrescribe si ya existe (ej. plantilla con cliente_01),
# o añade si el .env no la tenía.
if grep -qE '^ARBOL_ID=' .env; then
  sed -i.bak "s|^ARBOL_ID=.*|ARBOL_ID=$ARBOL_ID|" .env
  sed -i.bak "s|^ARBOL_NOMBRE=.*|ARBOL_NOMBRE=\"$ARBOL_NOMBRE\"|" .env
  sed -i.bak "s|^ARBOL_ROL=.*|ARBOL_ROL=$ARBOL_ROL|" .env
  rm -f .env.bak
else
  cat >> .env <<EOF

# === Identidad del árbol (instalado por sembrar.sh) ===
ARBOL_ID=$ARBOL_ID
ARBOL_NOMBRE="$ARBOL_NOMBRE"
ARBOL_ROL=$ARBOL_ROL
EOF
fi
# Heredero: solo aplica si el rol es 'heredero' y se indicó el comandante primario.
if [[ "$ARBOL_ROL" == "heredero" ]]; then
  if [[ -z "$HEREDERO_DE" ]]; then
    echo "⚠️  Rol 'heredero' requiere --heredero-de <host_comandante_primario>"
  else
    if grep -qE '^ARBOL_HEREDERO_DE=' .env; then
      sed -i.bak "s|^ARBOL_HEREDERO_DE=.*|ARBOL_HEREDERO_DE=$HEREDERO_DE|" .env && rm -f .env.bak
    else
      echo "ARBOL_HEREDERO_DE=$HEREDERO_DE" >> .env
    fi
    echo "→ Heredero del comandante primario: $HEREDERO_DE"
  fi
fi
echo "→ ARBOL_ID=$ARBOL_ID  ARBOL_NOMBRE=$ARBOL_NOMBRE  ROL=$ARBOL_ROL"

# ---------------------------------------------------------------------------
# 2) Credenciales de proveedores — pedir las que falten (sin echo en pantalla)
# ---------------------------------------------------------------------------
grep -qE '^OPENROUTER_API_KEY=.+$' .env || { read -r -s -p "OpenRouter API key para este árbol: " OR_KEY; echo; echo "OPENROUTER_API_KEY=$OR_KEY" >> .env; }
grep -qE '^SERPAPI_KEY=.+$'         .env || { read -r -s -p "SerpAPI key (opcional): " SERP_KEY; echo; [[ -n "$SERP_KEY" ]] && echo "SERPAPI_KEY=$SERP_KEY" >> .env; }
grep -qE '^GOOGLE_API_KEY=.+$'      .env || { read -r -s -p "Google Places key (opcional): " GOOG_KEY; echo; [[ -n "$GOOG_KEY" ]] && echo "GOOGLE_API_KEY=$GOOG_KEY" >> .env; }

# ---------------------------------------------------------------------------
# 3) Carpetas compartidas (aisladas por árbol)
# ---------------------------------------------------------------------------
mkdir -p shared/borradores shared/memoria shared/aprobaciones shared/reportes
echo "→ /shared creado (borradores, memoria, aprobaciones, reportes)"

# ---------------------------------------------------------------------------
# 4) Base de datos (tablas + admin inicial)
# ---------------------------------------------------------------------------
$PY -c "from db import init_db; init_db()"
echo "→ Base de datos inicializada (admin por defecto)"

# ---------------------------------------------------------------------------
# 5) Usuario Directora Humana (rol: directora_humana)
# ---------------------------------------------------------------------------
DIR_USER="$(grep -E '^DIRECTORA_USERNAME=' .env | cut -d= -f2- | head -1)"
DIR_USER="${DIR_USER:-directora}"
DIR_EMAIL="${DIRECTORA_EMAIL:-directora@$ARBOL_ID}"
if [[ -z "${DIRECTORA_PASSWORD:-}" ]]; then
  read -r -s -p "Contraseña maestra de la Directora Humana: " DIR_PASS; echo
  [[ -z "$DIR_PASS" ]] && { echo "⚠️  Contraseña vacía; se omite crear la Directora."; }
else
  DIR_PASS="$DIRECTORA_PASSWORD"
fi
if [[ -n "${DIR_PASS:-}" ]]; then
  export DIR_USER DIR_EMAIL DIR_PASS
  $PY -c "
import os
from db import SessionLocal
from auth import crear_usuario
db = SessionLocal()
try:
    crear_usuario(db, username=os.environ['DIR_USER'], email=os.environ['DIR_EMAIL'],
                  password=os.environ['DIR_PASS'], role='directora_humana')
    print('→ Directora Humana creada:', os.environ['DIR_USER'])
except ValueError as e:
    print('→ (ya existe):', e)
finally:
    db.close()
"
fi

# ---------------------------------------------------------------------------
# 6) Verificación de modelos (config, no llamada en vivo)
# ---------------------------------------------------------------------------
$PY -c "from core.llm_router import get_llm, RUTINA, ESTRATEGIA, get_strategy_llms; print('rutina     ->', get_llm(RUTINA).model); print('estrategia ->', get_llm(ESTRATEGIA).model); print('cadena     ->', [l.model for l in get_strategy_llms()])"
echo "→ Modelos configurados"

# ---------------------------------------------------------------------------
# FASE MADUREZ — manifiesto Trinity + health check + registro
# ---------------------------------------------------------------------------
echo "🌳 [MADUREZ] generando manifiesto y verificando salud"
ARBOL_ROL="${ARBOL_ROL:-$(grep -E '^ARBOL_ROL=' .env | head -1 | cut -d= -f2- | tr -d '"')}"
ARBOL_ROL="${ARBOL_ROL:-obrero}"
ARBOL_ID_FINAL="${ARBOL_ID:-$(grep -E '^ARBOL_ID=' .env | head -1 | cut -d= -f2- | tr -d '"')}"
HEREDERO_DE_FINAL="$(grep -E '^ARBOL_HEREDERO_DE=' .env | head -1 | cut -d= -f2- | tr -d '"' || true)"
ARBOL_ID="$ARBOL_ID_FINAL" ARBOL_ROL="$ARBOL_ROL" ARBOL_HEREDERO_DE="$HEREDERO_DE_FINAL" \
  $PY -c "from core.manifiesto import guardar_manifiesto; import os; r=guardar_manifiesto('manifiesto.yaml', os.getenv('ARBOL_ID','local'), rol=os.getenv('ARBOL_ROL','obrero'), heredero_de=os.getenv('ARBOL_HEREDERO_DE','')); print('→ Manifiesto Trinity:', r)"
echo "→ Rol del árbol: $ARBOL_ROL"

# Health check: modelos + DB + directorio compartido
$PY -c "from core.llm_router import get_llm, RUTINA, ESTRATEGIA; get_llm(RUTINA); get_llm(ESTRATEGIA); from db import init_db; init_db(); print('→ Salud OK: modelos + DB')"
[[ -d shared ]] && echo "→ /shared presente"

# ---------------------------------------------------------------------------
# 7) Resumen final (árbol maduro)
# ---------------------------------------------------------------------------
echo
echo "✅ Árbol [$ARBOL_ID_FINAL] (rol=$ARBOL_ROL) MADURO."
echo "   Germinado: dependencias instaladas, modelo local listo."
echo "   Crecido  : .env + /shared + DB + roles + ramas."
echo "   Maduro   : manifiesto.yaml generado para Trinity."
echo "   Próximos pasos:"
echo "   - obrero    : correr las ramas 24/7 (sistema completo)."
echo "   - comandante: arrancar el panel web (comandante_web.py)."
echo "   - heredero  : activarse con reclamar_comandancia (failover)."
echo "Recordatorio: .env y /shared de este árbol NO deben copiarse a otro árbol."