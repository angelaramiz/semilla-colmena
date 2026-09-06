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
$ErrorActionPreference = "Continue"   # evita que el stderr de git/pip/uv aborte el script

# --- Codificación UTF-8 (para que la consola CMD muestre →, á, é, etc.) ---
try {
  $enc = New-Object System.Text.UTF8Encoding($false)
  [Console]::InputEncoding  = $enc
  [Console]::OutputEncoding = $enc
  $OutputEncoding = $enc
} catch {}

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
# Python — detecta el ALIAS falso de la Microsoft Store (que lanza la tienda y falla)
function Python-Real { 
  if (-not (Test-Bin python)) { return $false }
  # si es el alias de Store, `python --version` no devuelve una versión real
  try { $v = (python --version 2>&1 | Out-String).Trim(); return $v -match "Python \d" } catch { return $false }
}
if (-not (Python-Real)) {
  Write-Host "→ python no disponible (o es el alias de Microsoft Store); instalando Python real con winget ..." -ForegroundColor Yellow
  try { winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null }
  catch { Write-Host "⚠️  no se pudo instalar python con winget." -ForegroundColor Yellow }
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  # deshabilitar el alias de ejecución de aplicaciones (app execution aliases) que interfiere
  try {
    $aliasUser = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
    Remove-Item (Join-Path $aliasUser "python.exe") -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $aliasUser "python3.exe") -Force -ErrorAction SilentlyContinue
  } catch {}
}
# Fallback: descarga directa desde python.org si winget no existe o falló
if (-not (Python-Real)) {
  Write-Host "→ winget no disponible; descargando Python 3.12 desde python.org ..." -ForegroundColor Yellow
  try {
    $pyInst = "$env:TEMP\python-3.12.7-amd64.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" -OutFile $pyInst -UseBasicParsing -ErrorAction Stop
    Start-Process -FilePath $pyInst -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    # re-intentar quitar alias
    try {
      $aliasUser = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
      Remove-Item (Join-Path $aliasUser "python.exe") -Force -ErrorAction SilentlyContinue
      Remove-Item (Join-Path $aliasUser "python3.exe") -Force -ErrorAction SilentlyContinue
    } catch {}
  } catch { Write-Host "⚠️  no se pudo descargar Python: $_" -ForegroundColor Yellow }
}
if (-not (Python-Real)) {
  Write-Host "❌ Python no disponible. Instálalo (python.org marcando 'Add to PATH') y vuelve a correr." -ForegroundColor Red
  exit 1
}
# Evitar "dubious ownership" cuando el repo fue clonado por otro usuario Windows
try { git config --global --add safe.directory "*" 2>&1 | Out-Null } catch {}

# --- AUTO-CLONADO (si la carpeta ya existe, hace pull; no falla) ---
$InRepo = (Test-Path ".git")
if (-not $InRepo) {
  if ([string]::IsNullOrEmpty($Dir)) {
    if (Test-Path "semilla-colmena\.git") {
      Write-Host "→ repo ya clonado; actualizando (git pull) ..."
      Set-Location semilla-colmena
      git pull 2>&1 | Out-Null
    } elseif (Test-Path "semilla-colmena") {
      Write-Host "⚠️  existe 'semilla-colmena' pero sin .git; entrando sin reclonar." -ForegroundColor Yellow
      Set-Location semilla-colmena
    } else {
      Write-Host "→ clonando la semilla ..."
      git clone $REPO_GIT semilla-colmena 2>&1 | Out-Null
      Set-Location semilla-colmena
    }
  } else {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    if (Test-Path "$Dir\.git") {
      Write-Host "→ repo en $Dir; git pull ..."; Set-Location $Dir; git pull 2>&1 | Out-Null
    } else {
      Write-Host "→ clonando en $Dir"; git clone $REPO_GIT $Dir 2>&1 | Out-Null; Set-Location $Dir
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
  # HERENCIA DE ADN: semillero/heredado.env (credenciales reales del principal, gitignored).
  # Buscar en el repo Y en la raíz de la maceta (..\), que es donde el SFX lo deja
  # (el clon nunca lo trae porque es gitignored).
  $heredado = $null
  foreach ($cand in @("semillero\heredado.env", "..\semillero\heredado.env")) {
    if (Test-Path $cand) { $heredado = $cand; break }
  }
  if ($heredado) { Copy-Item $heredado ".env"; Write-Host "→ .env HEREDA credenciales del árbol principal (desde $heredado)" }
  else { Copy-Item ".env.example" ".env"; Write-Host "→ .env desde plantilla" }
}

# fijar identidad (sobrescribe líneas si existen)
$env:ARBOL_ID = $ArbolId
$env:ARBOL_ROL = $Rol
$env:ARBOL_NOMBRE = $Nombre
$env:ARBOL_HEREDERO_DE = $HerederoDe

Write-Host "→ ARBOL_ID=$ArbolId ROL=$Rol"

# --- DEPENDENCIAS (uv sync → fallback a pip) ---
Write-Host "→ instalando dependencias de Python (puede tardar unos minutos) ..."
$deps_ok = $false
if (-not (Test-Bin uv)) {
  Write-Host "→ uv no encontrado; instalando con pip ..."
  & python -m pip install --quiet uv 2>&1 | Out-Null
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (Test-Bin uv) {
  Write-Host "→ uv sync ..."
  & uv sync 2>&1 | Out-Null
  $deps_ok = ($LASTEXITCODE -eq 0)
}
if (-not $deps_ok) {
  if (Test-Path "requirements.txt") {
    Write-Host "→ pip install -r requirements.txt ..."
    & python -m pip install --quiet -r requirements.txt 2>&1 | Out-Null
    $deps_ok = ($LASTEXITCODE -eq 0)
  }
}
if (-not $deps_ok) { Write-Host "⚠️  no se completaron las dependencias; continúa pero puede fallar más adelante." -ForegroundColor Yellow }

# --- PY: usar el python del venv si existe (uv sync instala ahí), si no, el del sistema ---
$PY = "python"
if (Test-Path ".venv\Scripts\python.exe") { $PY = ".venv\Scripts\python.exe" }
elseif (Test-Path "venv\Scripts\python.exe") { $PY = "venv\Scripts\python.exe" }
Write-Host "→ python: $PY"

# --- OLLAMA (Windows): instalar por CLI si falta, registrar como servicio y bajar modelos ---
$OLLAMA_MODELO = if ($env:LOCAL_LLM_MODEL) { $env:LOCAL_LLM_MODEL } else { "qwen3:27b" }
$OLLAMA_BASICO = if ($env:OLLAMA_MODELO_BASICO) { $env:OLLAMA_MODELO_BASICO } else { "qwen2.5:1.5b" }
if (-not (Test-Bin ollama)) {
  Write-Host "→ instalando Ollama (descarga el instalador de Windows)..."
  try {
    $exe = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $exe -UseBasicParsing -ErrorAction Stop
    Start-Process -FilePath $exe -ArgumentList "/SILENT" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "→ Ollama instalado."
  } catch { Write-Host "⚠️  no se pudo descargar Ollama: $_" -ForegroundColor Yellow }
}
if (Test-Bin ollama) {
  # Registrar Ollama como tarea de inicio para que persista tras reinicio
  try {
    $ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollamaExe) { $ollamaExe = "ollama" }
    $batPath = "$env:APPDATA\ollama_serve.bat"
    Set-Content -Path $batPath -Value "@echo off`r`n`"$ollamaExe`" serve" -Encoding ASCII -Force
    schtasks /Create /TN "OllamaServe" /TR "`"$batPath`"" /SC ONLOGON /RL HIGHEST /F 2>&1 | Out-Null
    # Iniciar ahora si no está corriendo
    $isRunning = Get-Process -Name "ollama" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ollama*" }
    if (-not $isRunning) {
      Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 5
    }
  } catch { Write-Host "⚠️  no se pudo registrar Ollama como servicio: $_" -ForegroundColor Yellow }

  # Pull modelos con fallback (qwen3:27b no existe en registry, probar tamaños menores)
  $modelosFallback = @($OLLAMA_MODELO, "qwen3:14b", "qwen3:8b", "qwen3:4b", "qwen2.5:7b")
  $modelosFallback = $modelosFallback | Select-Object -Unique
  foreach ($m in $modelosFallback) {
    Write-Host "→ intentando modelo: $m ..."
    ollama pull $m 2>&1 | Out-Null
    $ok = (ollama list 2>&1 | Select-String -SimpleMatch $m)
    if ($ok) {
      if ($m -ne $OLLAMA_MODELO) {
        Write-Host "→ $OLLAMA_MODELO no disponible, usando $m (actualizando .env)" -ForegroundColor Yellow
        (Get-Content ".env" -Raw) -replace "LOCAL_LLM_MODEL=.*", "LOCAL_LLM_MODEL=$m" | Set-Content ".env" -NoNewline
        $env:LOCAL_LLM_MODEL = $m
      }
      break
    }
  }
  Write-Host "→ modelo básico: $OLLAMA_BASICO ..."; ollama pull $OLLAMA_BASICO 2>&1 | Out-Null
}

# --- DB ---
Write-Host "→ inicializando BD (Supabase según .env) ..."
& $PY -c "from db import init_db; init_db()"

# --- Directora Humana (AUTÓNOMO: no pide input, genera contraseña temporal) ---
$DIR_PASS = $env:DIRECTORA_PASSWORD
$GEN_PASS = $null
if (-not $DIR_PASS) {
  $GEN_PASS = & $PY -c "import secrets;print(secrets.token_urlsafe(18))"
  $DIR_PASS = $GEN_PASS
}
if ($DIR_PASS) {
  $env:DIR_USER = if ($env:DIRECTORA_USERNAME) { $env:DIRECTORA_USERNAME } else { "directora" }
  $env:DIR_EMAIL = "directora@$ArbolId"
$env:DIR_PASS = $DIR_PASS
  & $PY -c "import os
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
& $PY -c "import os
from core.manifiesto import guardar_manifiesto
guardar_manifiesto('manifiesto.yaml', os.environ['ARBOL_ID'], rol=os.environ['ARBOL_ROL'], heredero_de=os.environ.get('ARBOL_HEREDERO_DE',''))
print('→ manifiesto.yaml generado')"

# --- HEALTH ---
& $PY -c "from core.llm_router import get_llm, RUTINA, ESTRATEGIA; get_llm(RUTINA); get_llm(ESTRATEGIA); print('→ modelos configurados')"

# --- TAILSCALE (idempotente: no re-loguea si ya está conectado) ---
if (Test-Bin tailscale) {
  $tsStatus = (tailscale status 2>&1 | Out-String)
  $alreadyUp = $tsStatus -match "100\." -and $tsStatus -notmatch "Logged out|not logged in|NoState"
  if (-not $alreadyUp -and $env:TAILSCALE_TOKEN) {
    Write-Host "→ conectando Tailscale ..."
    tailscale up --authkey=$env:TAILSCALE_TOKEN --hostname=$ArbolId 2>&1 | Out-Null
    Start-Sleep -Seconds 3
  } elseif ($alreadyUp) {
    Write-Host "→ Tailscale ya conectado."
  } elseif (-not $env:TAILSCALE_TOKEN) {
    Write-Host "⚠️  TAILSCALE_TOKEN vacío; Tailscale no se conectará (configúralo en .env)" -ForegroundColor Yellow
  }
} else {
  Write-Host "⚠️  Tailscale no instalado (opcional, se omitió)" -ForegroundColor Yellow
}

# --- AUTO-REGISTRO en la nube (conecta el árbol a los principales) ---
$TSIP = ""
try { $TSIP = (tailscale ip -4 2>&1 | Select-Object -First 1).ToString().Trim() } catch {}
if (-not $TSIP -or $TSIP -match "failed|error|not logged") { $TSIP = "" }
$HostReg = if ($TSIP) { $TSIP } else { $env:COMPUTERNAME }
$env:HOST_REG = $HostReg
$env:ARBOL_ROLE = $Rol
# 1) Registro local vía db.py (escribe al DATABASE_URL; si Postgres no es alcanzable,
#    db.py cae a SQLite local y el paso no es crítico porque el 2) va a la nube por REST).
& $PY -c "import os
from db import registrar_arbol
try:
    r = registrar_arbol(
        os.environ['ARBOL_ID'], os.environ['HOST_REG'], usuario='root', canal='tailscale',
        rol=os.environ.get('ARBOL_ROLE','obrero'), ip_tailscale=os.environ.get('HOST_REG',''),
        hostname=os.environ.get('COMPUTERNAME',''), estado='operativo'
    )
    print('→ Árbol registrado (DB):', r.get('arbol_id'), '(', r.get('rol'), ')')
except Exception as e:
    print('→ (aviso) registro local:', str(e)[:120])"

# 2) Registro en la nube por REST (IPv4 fiable; es lo que el panel del conservante lee).
$env:REG_NAME = if ($Nombre) { $Nombre } else { "Arbol $ArbolId" }
& $PY -c "import os, json, urllib.request, urllib.error, urllib.parse
url = os.environ.get('SUPABASE_URL','').rstrip('/')
key = os.environ.get('SUPABASE_PUBLISHABLE_KEY','')
if not url or not key:
    print('→ (aviso) sin SUPABASE_URL/KEY; registro en nube omitido')
else:
    payload = {
        'arbol_id': os.environ['ARBOL_ID'],
        'nombre': os.environ.get('REG_NAME',''),
        'rol': os.environ.get('ARBOL_ROLE','obrero'),
        'host': os.environ.get('HOST_REG',''),
        'ip_tailscale': os.environ.get('HOST_REG',''),
        'hostname': os.environ.get('COMPUTERNAME',''),
        'estado': 'operativo',
    }
    body = json.dumps(payload).encode()
    H = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    def _req(method, target, data=None):
        rq = urllib.request.Request(target, data=data, method=method, headers=H)
        try:
            with urllib.request.urlopen(rq, timeout=20) as resp:
                return resp.status, resp.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', 'replace')
    base = url + '/rest/v1/arboles_remotos'
    code, _ = _req('POST', base, body)
    if code in (200, 201):
        print('→ Árbol registrado en la nube (nuevo).')
    elif code == 409:
        aid = urllib.parse.quote(os.environ['ARBOL_ID'])
        code, _ = _req('PATCH', base + '?arbol_id=eq.' + aid, body)
        print('→ Árbol actualizado en la nube (ya existía).' if code in (200, 204) else ('→ (aviso) PATCH ' + str(code)))
    else:
        print('→ (aviso) registro en nube: HTTP ' + str(code))"

# --- ARRANQUE PERSISTENTE 24/7 (según rol) ---
# Registra los paneles web de este árbol como tareas de inicio (ONLOGON) y los
# arranca ahora si no están escuchando. El python del venv es el que tiene uvicorn.
$PY_ABS = "python"
if (Test-Path $PY) { $PY_ABS = (Resolve-Path $PY).Path }
$servicios = New-Object System.Collections.ArrayList

# Panel específico según rol
if ($Rol -eq "conservante") {
  $p = if ($env:CONSERVANTE_WEB_PORT) { $env:CONSERVANTE_WEB_PORT } else { "8002" }
  [void]$servicios.Add(@{ name="ConservanteWeb"; mod="conservante_web:app"; port=$p })
} elseif ($Rol -eq "comandante") {
  $p = if ($env:COMANDANTE_WEB_PORT) { $env:COMANDANTE_WEB_PORT } else { "8001" }
  [void]$servicios.Add(@{ name="ComandanteWeb"; mod="comandante_web:app"; port=$p })
}
# Todo árbol vivo sirve su panel web local (obrero/comandante/conservante)
[void]$servicios.Add(@{ name="ArbolWeb"; mod="web_server:app"; port="8000" })

foreach ($svc in $servicios) {
  $bat = Join-Path $env:APPDATA ("{0}.bat" -f $svc.name)
  $svcMod = $svc.mod; $svcPort = $svc.port
  $batContent = "@echo off`r`ncd /d `"$PWD`"`r`n`"$PY_ABS`" -m uvicorn $svcMod --host 127.0.0.1 --port $svcPort"
  Set-Content -Path $bat -Value $batContent -Encoding ASCII -Force
  try { schtasks /Create /TN $svc.name /TR "`"$bat`"" /SC ONLOGON /RL HIGHEST /F 2>&1 | Out-Null } catch {}
  # Arrancar ahora si el puerto está libre
  $yaEscucha = Get-NetTCPConnection -LocalPort $svcPort -State Listen -ErrorAction SilentlyContinue
  if ($yaEscucha) {
    Write-Host "→ $($svc.name) ya activo en :$svcPort"
  } else {
    try { Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $bat -WindowStyle Hidden | Out-Null; Write-Host "→ $($svc.name) iniciado en :$svcPort (24/7)" } catch { Write-Host "⚠️  no se pudo arrancar $($svc.name): $_" -ForegroundColor Yellow }
  }
}

Write-Host "`n✅ Árbol [$ArbolId] (rol=$Rol) sembrado." -ForegroundColor Green
if ($GEN_PASS) { Write-Host "⚠️  Contraseña temporal de la Directora: $GEN_PASS  (cámbiala)" -ForegroundColor Yellow }
Write-Host "→ Registrado y visible en el panel del conservante."
Write-Host "→ Revisa: .env (claves/tokens), credenciales, /shared, manifiesto.yaml"
Write-Host "→ Red: tailscale up --authkey=... --hostname=$ArbolId (o clave SSH)"