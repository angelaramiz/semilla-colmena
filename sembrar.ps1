# ============================================================================
#  sembrar.ps1  — Crea un ÁRBOL (instancia de la agencia) desde la SEMILLA.
#  Equivalente en PowerShell de sembrar.sh (Windows / PowerShell).
#
#  Uso:
#    powershell -ExecutionPolicy Bypass -File sembrar.ps1 <arbol_id> [-rol obrero|comandante|conservante|heredero] [-nombre "Nombre"] [-dir RUTA] [-herederoDe HOST]
#  Ejemplos:
#    .\sembrar.ps1 cliente_01 -rol obrero -nombre "Cliente X"
#    .\sembrar.ps1 cmd_01 -rol comandante
# ============================================================================
param(
  [Parameter(Mandatory=$true, Position=0)] [string]$ArbolId,
  [string]$Rol = "",
  [string]$Nombre = "",
  [string]$Dir = "",
  [string]$HerederoDe = ""
)
$ErrorActionPreference = "Stop"

$REPO_GIT = "https://github.com/angelaramiz/semilla-colmena.git"

Write-Host "`n===== SEMBRAR [$ArbolId] =====" -ForegroundColor Cyan
Write-Host "→ [BOOTSTRAP] verificando precondiciones ..."

function Test-Bin($n) { [bool](Get-Command $n -ErrorAction SilentlyContinue) }

# --- Precondiciones base (solo avisa; el resto lo gestiona la semilla) ---
if (-not (Test-Bin git)) { Write-Host "⚠️  git no instalado (winget install Git.Git)." -ForegroundColor Yellow }
if (-not (Test-Bin python) ) { Write-Host "⚠️  python no detectable; se usará uv si existe." -ForegroundColor Yellow }

# --- AUTO-CLONADO ---
$InRepo = (Test-Path ".git")
if (-not $InRepo) {
  if ([string]::IsNullOrEmpty($Dir)) {
    Write-Host "→ no estás dentro del repo; clonando la semilla ..."
    git clone $REPO_GIT semilla-colmena 2>$null
    Set-Location semilla-colmena
  } else {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    if (-not (Test-Path "$Dir\.git")) { Write-Host "→ clonando en $Dir"; git clone $REPO_GIT $Dir 2>$null }
    Set-Location $Dir
  }
}

# --- Rol por defecto ---
if ([string]::IsNullOrEmpty($Rol)) {
  if (Test-Path ".env.example") { $cand = Select-String -Path ".env.example" -Pattern "^ARBOL_ROL=(.+)" | ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() } }
  $Rol = if ($cand) { $cand } else { "obrero" }
}
if ($Rol -notin @("obrero","comandante","conservante","heredero")) {
  $Rol = "obrero"
}

# --- .env ---
if (Test-Path ".env") { Write-Host "→ .env ya existe." }
else { if (-not (Test-Path ".env.example")) { Write-Host "❌ sin .env.example." -ForegroundColor Red; exit 1 }; Copy-Item ".env.example" ".env" }

# fijar identidad (sobrescribe líneas si existen)
$env:ARBOL_ID = $ArbolId
$env:ARBOL_ROL = $Rol
$env:ARBOL_NOMBRE = $Nombre
$env:ARBOL_HEREDERO_DE = $HerederoDe

Write-Host "→ ARBOL_ID=$ArbolId ROL=$Rol"

# --- DEPENDENCIAS ---
if (Test-Bin uv) { Write-Host "→ uv sync ..."; uv sync 2>$null } 
elseif (Test-Path "requirements.txt") { Write-Host "→ pip install ..."; python -m pip install -r requirements.txt 2>$null }

# --- DB ---
Write-Host "→ inicializando BD (Supabase según .env) ..."
python -c "from db import init_db; init_db()"

# --- Directora Humana ---
$DIR_PASS = $env:DIRECTORA_PASSWORD
if (-not $DIR_PASS) { $DIR_PASS = Read-Host "Contraseña maestra de la Directora (vacío = omitir)" }
if ($DIR_PASS) {
  $env:DIR_USER = if ($env:DIRECTORA_USERNAME) { $env:DIRECTORA_USERNAME } else { "directora" }
  $env:DIR_EMAIL = "directora@$ArbolId"
  $env:DIR_PASS = $DIR_PASS
  python -c "import os
from db import SessionLocal
from auth import crear_usuario
db=SessionLocal()
try:
    crear_usuario(db, os.environ['DIR_USER'], os.environ['DIR_EMAIL'], os.environ['DIR_PASS'], role='directora_humana'); print('→ Directora creada')
except Exception as e:
    print('→ Directora:', e)
finally:
    db.close()"
}

# --- MANIFIESTO ---
python -c "import os
from core.manifiesto import guardar_manifiesto
guardar_manifiesto('manifiesto.yaml', os.environ['ARBOL_ID'], rol=os.environ['ARBOL_ROL'], heredero_de=os.environ.get('ARBOL_HEREDERO_DE',''))
print('→ manifiesto.yaml generado')"

# --- HEALTH ---
python -c "from core.llm_router import get_llm, RUTINA, ESTRATEGIA; get_llm(RUTINA); get_llm(ESTRATEGIA); print('→ modelos configurados')"

Write-Host "`n✅ Árbol [$ArbolId] (rol=$Rol) sembrado." -ForegroundColor Green
Write-Host "→ Revisa: .env (claves/tokens), credenciales, /shared, manifiesto.yaml"
Write-Host "→ Red: tailscale up --authkey=... --hostname=$ArbolId (o clave SSH)"