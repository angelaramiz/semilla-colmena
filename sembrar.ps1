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

# --- Codificación UTF-8 (para que la consola CMD muestre →, á, é, etc.) ---
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$REPO_GIT = "https://github.com/angelaramiz/semilla-colmena.git"

Write-Host "`n===== SEMBRAR [$ArbolId] =====" -ForegroundColor Cyan
Write-Host "→ [BOOTSTRAP] verificando precondiciones ..."

function Test-Bin($n) { [bool](Get-Command $n -ErrorAction SilentlyContinue) }

# --- Precondiciones base (AUTÓNOMO: instala lo que falta) ---
# Git
if (-not (Test-Bin git)) {
  Write-Host "→ git no instalado; instalando con winget ..." -ForegroundColor Yellow
  try { winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements | Out-Null }
  catch { Write-Host "⚠️  no se pudo instalar git con winget; instálalo manualmente (git-scm.com, marcar 'Add to PATH')." -ForegroundColor Yellow }
  # refrescar PATH de la sesión (winget no lo actualiza en el proceso actual)
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (-not (Test-Bin git)) { Write-Host "⚠️  git sigue sin detectarse. Instálalo y vuelve a correr." -ForegroundColor Red; exit 1 }
# Python
if (-not (Test-Bin python)) {
  Write-Host "→ python no detectable; instalando con winget ..."
  try { winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null }
  catch { Write-Host "⚠️  no se pudo instalar python con winget." -ForegroundColor Yellow }
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# --- AUTO-CLONADO (si la carpeta ya existe, hace pull; no falla) ---
$InRepo = (Test-Path ".git")
if (-not $InRepo) {
  if ([string]::IsNullOrEmpty($Dir)) {
    if (Test-Path "semilla-colmena\.git") {
      Write-Host "→ repo ya clonado; actualizando (git pull) ..."
      Set-Location semilla-colmena
      git pull 2>$null
    } elseif (Test-Path "semilla-colmena") {
      Write-Host "⚠️  existe 'semilla-colmena' pero sin .git; entrando sin reclonar." -ForegroundColor Yellow
      Set-Location semilla-colmena
    } else {
      Write-Host "→ clonando la semilla ..."
      git clone $REPO_GIT semilla-colmena 2>$null
      Set-Location semilla-colmena
    }
  } else {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    if (Test-Path "$Dir\.git") {
      Write-Host "→ repo en $Dir; git pull ..."; Set-Location $Dir; git pull 2>$null
    } else {
      Write-Host "→ clonando en $Dir"; git clone $REPO_GIT $Dir 2>$null; Set-Location $Dir
    }
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
else {
  if (-not (Test-Path ".env.example")) { Write-Host "❌ sin .env.example." -ForegroundColor Red; exit 1 }
  # HERENCIA DE ADN: semillero/heredado.env (credenciales reales del principal, gitignored)
  if (Test-Path "semillero\heredado.env") { Copy-Item "semillero\heredado.env" ".env"; Write-Host "→ .env HEREDA credenciales del árbol principal" }
  else { Copy-Item ".env.example" ".env"; Write-Host "→ .env desde plantilla" }
}

# fijar identidad (sobrescribe líneas si existen)
$env:ARBOL_ID = $ArbolId
$env:ARBOL_ROL = $Rol
$env:ARBOL_NOMBRE = $Nombre
$env:ARBOL_HEREDERO_DE = $HerederoDe

Write-Host "→ ARBOL_ID=$ArbolId ROL=$Rol"

# --- DEPENDENCIAS ---
if (Test-Bin uv) { Write-Host "→ uv sync ..."; uv sync 2>$null } 
elseif (Test-Path "requirements.txt") { Write-Host "→ pip install ..."; python -m pip install -r requirements.txt 2>$null }

# --- OLLAMA (Windows): instalar por CLI si falta y bajar modelo ---
$OLLAMA_MODELO = if ($env:LOCAL_LLM_MODEL) { $env:LOCAL_LLM_MODEL } else { "qwen3:27b" }
$OLLAMA_BASICO = if ($env:OLLAMA_MODELO_BASICO) { $env:OLLAMA_MODELO_BASICO } else { "qwen2.5:1.5b" }
if (-not (Test-Bin ollama)) {
  Write-Host "→ instalando Ollama (descarga el instalador de Windows)..."
  try {
    $exe = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $exe -UseBasicParsing -ErrorAction Stop
    Start-Process -FilePath $exe -ArgumentList "/SILENT" -Wait
    Write-Host "→ Ollama instalado; usa una nueva terminal."
  } catch { Write-Host "⚠️  no se pudo descargar Ollama: $_" -ForegroundColor Yellow }
}
if (Test-Bin ollama) {
  Write-Host "→ modelo básico: $OLLAMA_BASICO ..."; ollama pull $OLLAMA_BASICO 2>$null
  Write-Host "→ modelo principal: $OLLAMA_MODELO ..."; ollama pull $OLLAMA_MODELO 2>$null
}

# --- DB ---
Write-Host "→ inicializando BD (Supabase según .env) ..."
python -c "from db import init_db; init_db()"

# --- Directora Humana (AUTÓNOMO: no pide input, genera contraseña temporal) ---
$DIR_PASS = $env:DIRECTORA_PASSWORD
$GEN_PASS = $null
if (-not $DIR_PASS) {
  $GEN_PASS = python -c "import secrets;print(secrets.token_urlsafe(18))"
  $DIR_PASS = $GEN_PASS
}
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

# --- AUTO-REGISTRO en la nube (conecta el árbol a los principales) ---
$TSIP = (tailscale ip -4 2>$null | Select-Object -First 1)
$HostReg = if ($TSIP) { $TSIP } else { $env:COMPUTERNAME }
$env:HOST_REG = $HostReg
python -c "import os
from db import registrar_arbol
try:
    r = registrar_arbol(os.environ['ARBOL_ID'], os.environ['HOST_REG'], usuario='root', canal='tailscale')
    print('→ Árbol auto-registrado:', r.get('arbol_id'), '@', os.environ['HOST_REG'])
except Exception as e:
    print('→ (aviso) auto-registro:', str(e)[:120])"

Write-Host "`n✅ Árbol [$ArbolId] (rol=$Rol) sembrado." -ForegroundColor Green
if ($GEN_PASS) { Write-Host "⚠️  Contraseña temporal de la Directora: $GEN_PASS  (cámbiala)" -ForegroundColor Yellow }
Write-Host "→ Registrado y visible en el panel del conservante."
Write-Host "→ Revisa: .env (claves/tokens), credenciales, /shared, manifiesto.yaml"
Write-Host "→ Red: tailscale up --authkey=... --hostname=$ArbolId (o clave SSH)"