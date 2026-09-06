# ============================================================================
#  levantar.ps1 — Levanta TODO el árbol con un clic/doble clic:
#   1. Actualiza el código (git pull, repo público, anónimo).
#   2. Actualiza dependencias (uv sync; instala uv si falta).
#   3. Verifica comunicación (Tailscale: estado; conecta solo si hay token y está caído).
#   4. Arranca servicios web del rol (comandante:8001 / conservante:8002 / todos:8000)
#      y Ollama si está instalado pero apagado.
#  Idempotente: lo que ya está corriendo lo deja como está.
# ============================================================================
param([string]$RepoDir = "")
$ErrorActionPreference = "Continue"
try {
  $enc = New-Object System.Text.UTF8Encoding($false)
  [Console]::InputEncoding = $enc; [Console]::OutputEncoding = $enc; $OutputEncoding = $enc
} catch {}

if ($RepoDir) { Set-Location $RepoDir } else { Set-Location $PSScriptRoot }
$repo = (Get-Location).Path
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

function EnvVal($k, $def = "") {
  $f = Join-Path $repo ".env"
  if (Test-Path $f) {
    $m = Select-String -Path $f -Pattern ("^" + $k + "=(.*)") | Select-Object -First 1
    if ($m) { return $m.Matches[0].Groups[1].Value.Trim().Trim('"') }
  }
  $e = [System.Environment]::GetEnvironmentVariable($k)
  if ($e) { return $e }
  return $def
}

Write-Host "`n===== LEVANTAR ÁRBOL =====" -ForegroundColor Cyan
Write-Host "Repo: $repo"

# --- 0. git: ownership + actualización robusta (fetch+reset: el churn local
# de uv.lock abortaría un pull/merge; en un árbol no hay cambios locales que guardar) ---
Write-Host "`n[1/5] Código (fetch + reset) ..." -ForegroundColor Yellow
try { git config --global --add safe.directory $repo 2>&1 | Out-Null } catch {}
try {
  git fetch origin 2>&1 | Out-Null
  git reset --hard origin/main 2>&1 | Out-Null
  Write-Host ("Código en: " + (git log --oneline -1 2>$null))
} catch { Write-Host "AVISO actualización: $_" -ForegroundColor Yellow }

# --- 1. dependencias ---
Write-Host "`n[2/5] Dependencias (uv sync) ..." -ForegroundColor Yellow
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "Instalando uv ..."
  & python -m pip install --quiet uv 2>&1 | Out-Null
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
  & uv sync 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Write-Host "Dependencias OK." } else { Write-Host "AVISO uv sync falló (sigo igual)." -ForegroundColor Yellow }
} else { Write-Host "AVISO sin uv ni pip; omito dependencias." -ForegroundColor Yellow }

$PY = "python"
if (Test-Path (Join-Path $repo ".venv\Scripts\python.exe")) { $PY = Join-Path $repo ".venv\Scripts\python.exe" }

# --- 2. comunicación (Tailscale, solo lectura si lo gestiona otro usuario) ---
Write-Host "`n[3/5] Comunicación (Tailscale) ..." -ForegroundColor Yellow
$tsOk = $false; $tsIp = ""
try {
  $st = (tailscale status 2>&1 | Out-String)
  if ($st -match "100\.") { $tsOk = $true; $tsIp = (tailscale ip -4 2>&1 | Select-Object -First 1).ToString().Trim() }
  elseif (($st -match "Logged out|not logged") -and (EnvVal "TAILSCALE_TOKEN")) {
    Write-Host "Conectando a la tailnet ..."
    tailscale up --authkey=(EnvVal "TAILSCALE_TOKEN") --hostname=(EnvVal "ARBOL_ID" $env:COMPUTERNAME) 2>&1 | Out-Null
    Start-Sleep 4
    $tsIp = (tailscale ip -4 2>&1 | Select-Object -First 1).ToString().Trim()
    $tsOk = [bool]$tsIp
  }
} catch { Write-Host "Tailscale gestionado por otro usuario de esta máquina (normal)." -ForegroundColor DarkGray }
if ($tsOk) { Write-Host "Tailscale conectado. IP: $tsIp" -ForegroundColor Green }
else { Write-Host "Tailscale no disponible desde esta sesión (revisa la app)." -ForegroundColor Yellow }

# --- 3. Ollama (solo arrancar si está instalado) ---
Write-Host "`n[4/5] Ollama ..." -ForegroundColor Yellow
if (Get-Command ollama -ErrorAction SilentlyContinue) {
  $apiOk = $false
  try { Invoke-WebRequest -Uri "http://localhost:11434/" -TimeoutSec 4 -UseBasicParsing | Out-Null; $apiOk = $true } catch {}
  if (-not $apiOk) {
    Write-Host "Arrancando ollama serve ..."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 5
  }
  try { Invoke-WebRequest -Uri "http://localhost:11434/" -TimeoutSec 4 -UseBasicParsing | Out-Null; Write-Host "Ollama OK." -ForegroundColor Green }
  catch { Write-Host "Ollama instalado pero sin responder (revisa manualmente)." -ForegroundColor Yellow }
} else { Write-Host "Ollama no instalado (opcional)." -ForegroundColor DarkGray }

# --- 4. servicios web según rol ---
Write-Host "`n[5/5] Servidores web ..." -ForegroundColor Yellow
$rol = EnvVal "ARBOL_ROL" "obrero"
$servicios = New-Object System.Collections.ArrayList
if ($rol -eq "conservante") {
  [void]$servicios.Add(@{ n="ConservanteWeb"; m="conservante_web:app"; p=(EnvVal "CONSERVANTE_WEB_PORT" "8002") })
} elseif ($rol -eq "comandante") {
  [void]$servicios.Add(@{ n="ComandanteWeb"; m="comandante_web:app"; p=(EnvVal "COMANDANTE_WEB_PORT" "8001") })
}
[void]$servicios.Add(@{ n="ArbolWeb"; m="web_server:app"; p="8000" })
$startedHere = @()
foreach ($s in $servicios) {
  $esc = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
  if ($esc) { Write-Host "$($s.n) ya activo en :$($s.p)" -ForegroundColor Green; continue }
  $bat = Join-Path $env:APPDATA ($s.n + ".bat")
  Set-Content -Path $bat -Value ('@echo off' + "`r`n" + 'cd /d "' + $repo + '"' + "`r`n" + '"' + $PY + '" -m uvicorn ' + $s.m + ' --host 127.0.0.1 --port ' + $s.p) -Encoding ASCII -Force
  try { schtasks /Create /TN $s.n /TR "`"$bat`"" /SC ONLOGON /RL HIGHEST /F 2>&1 | Out-Null } catch {}
  # Arrancar ahora si el puerto está libre
  $yaEscucha = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
  if ($yaEscucha) {
    Write-Host "→ $($s.n) ya activo en :$s.p"
  } else {
    try { Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $bat -WindowStyle Hidden | Out-Null; Write-Host "→ $($s.n) iniciado en :$s.p (24/7)"; $startedHere += @($s.p) } catch { Write-Host "⚠️  no se pudo arrancar $($s.n): $_" -ForegroundColor Yellow }
  }
}
Start-Sleep 6
Write-Host "`n===== RESUMEN =====" -ForegroundColor Cyan
foreach ($s in $servicios) {
  $esc = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
  if ($esc) { Write-Host "OK  $($s.n) :$($s.p)" -ForegroundColor Green }
  else { Write-Host "FALLO $($s.n) :$($s.p)" -ForegroundColor Red }
}
if ($tsOk) { Write-Host "OK  Tailscale $tsIp" -ForegroundColor Green }
Write-Host "Listo: $(EnvVal 'ARBOL_ID' '?') ($(EnvVal 'ARBOL_ROL' '?'))"

# --- Apertura web al terminar (solo sesión interactiva: doble clic) ---
# Los servicios de tareas programadas (sesión 0) no pueden mostrar ventanas;
# esto abre el navegador solo cuando un humano ejecuta Levantar. Se abren los
# paneles que YA estaban activos (los recién iniciados aquí abren su propio
# navegador desde su evento startup al terminar de arrancar).
if ([Environment]::UserInteractive -and ((EnvVal "AUTO_OPEN_BROWSER" "false").Trim().ToLower() -in @("true","1","yes","on","si"))) {
  foreach ($s in $servicios) {
    if ($startedHere -contains $s.p) { continue }
    $esc = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
    if ($esc) {
      Write-Host "→ abriendo http://127.0.0.1:$($s.p)/ ..."
      Start-Process ("http://127.0.0.1:" + $s.p + "/")
    }
  }
}
