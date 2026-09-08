# ============================================================================
#  levantar.ps1 â€” Levanta TODO el Ã¡rbol con un clic/doble clic:
#   1. Actualiza el cÃ³digo (git pull, repo pÃºblico, anÃ³nimo).
#   2. Actualiza dependencias (uv sync; instala uv si falta).
#   3. Verifica comunicaciÃ³n (Tailscale: estado; conecta solo si hay token y estÃ¡ caÃ­do).
#   4. Arranca servicios web del rol (comandante:8001 / conservante:8002 / todos:8000)
#      y Ollama si estÃ¡ instalado pero apagado.
#  Idempotente: lo que ya estÃ¡ corriendo lo deja como estÃ¡.
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

Write-Host "`n===== LEVANTAR ÃRBOL =====" -ForegroundColor Cyan
Write-Host "Repo: $repo"

# --- 0. git: ownership + actualizaciÃ³n robusta (fetch+reset: el churn local
# de uv.lock abortarÃ­a un pull/merge; en un Ã¡rbol no hay cambios locales que guardar) ---
Write-Host "`n[1/5] CÃ³digo (fetch + reset) ..." -ForegroundColor Yellow
try { git config --global --add safe.directory $repo 2>&1 | Out-Null } catch {}
$headAntes = ""
try { $headAntes = (git rev-parse --short HEAD 2>$null).Trim() } catch {}
try {
  git fetch origin 2>&1 | Out-Null
  git reset --hard origin/main 2>&1 | Out-Null
  Write-Host ("CÃ³digo en: " + (git log --oneline -1 2>$null))
} catch { Write-Host "AVISO actualizaciÃ³n: $_" -ForegroundColor Yellow }
$headDespues = ""
try { $headDespues = (git rev-parse --short HEAD 2>$null).Trim() } catch {}
$codigoCambio = [bool]$headAntes -and [bool]$headDespues -and ($headAntes -ne $headDespues)
if ($codigoCambio) { Write-Host "â†’ cÃ³digo nuevo ($headAntes â†’ $headDespues): se reiniciarÃ¡n servicios." -ForegroundColor Yellow }
# Si el cÃ³digo cambiÃ³, este proceso corre la versiÃ³n VIEJA (ya cargada en memoria):
# relanzar el script actualizado una sola vez para operar siempre con lo nuevo.
if ($codigoCambio -and -not $env:LEVANTAR_REEXEC -and $PSCommandPath) {
  Write-Host "â†’ relanzando con la versiÃ³n nueva ..."
  $env:LEVANTAR_REEXEC = "1"
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$PSCommandPath"
  exit $LASTEXITCODE
}

# --- 1. dependencias ---
Write-Host "`n[2/5] Dependencias (uv sync) ..." -ForegroundColor Yellow
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "Instalando uv ..."
  & python -m pip install --quiet uv 2>&1 | Out-Null
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
  & uv sync 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Write-Host "Dependencias OK." } else { Write-Host "AVISO uv sync fallÃ³ (sigo igual)." -ForegroundColor Yellow }
} else { Write-Host "AVISO sin uv ni pip; omito dependencias." -ForegroundColor Yellow }

$PY = "python"
if (Test-Path (Join-Path $repo ".venv\Scripts\python.exe")) { $PY = Join-Path $repo ".venv\Scripts\python.exe" }

# --- 2. comunicaciÃ³n (Tailscale, solo lectura si lo gestiona otro usuario) ---
Write-Host "`n[3/5] ComunicaciÃ³n (Tailscale) ..." -ForegroundColor Yellow
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
} catch {
  # En sesiÃ³n remota/SSH 'tailscale status' puede fallar aunque la tailnet
  # estÃ© viva (esta misma sesiÃ³n puede venir por ella): intento directo.
  try { $tsIp = (tailscale ip -4 2>$null | Select-Object -First 1).ToString().Trim(); if ($tsIp) { $tsOk = $true } } catch {}
  if (-not $tsOk) { Write-Host "Tailscale gestionado por otro usuario de esta mÃ¡quina (normal)." -ForegroundColor DarkGray }
}
if ($tsOk) { Write-Host "Tailscale conectado. IP: $tsIp" -ForegroundColor Green }
else { Write-Host "Tailscale no disponible desde esta sesiÃ³n (revisa la app)." -ForegroundColor Yellow }

# --- 3. Ollama (solo arrancar si estÃ¡ instalado) ---
# El serve responde en localhost aunque lo haya instalado OTRO usuario
# (Get-ChildItem C:\Users\* falla sin elevaciÃ³n): probar la API PRIMERO.
Write-Host "`n[4/5] Ollama ..." -ForegroundColor Yellow
$apiOk = $false
try { Invoke-WebRequest -Uri "http://localhost:11434/" -TimeoutSec 4 -UseBasicParsing | Out-Null; $apiOk = $true } catch {}
$ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
if (-not $ollamaExe) {
  $candidatos = @("C:\Program Files\Ollama\ollama.exe")
  if ($env:LOCALAPPDATA) { $candidatos += Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe" }
  $candidatos += Get-ChildItem "C:\Users\*\AppData\Local\Programs\Ollama\ollama.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
  $ollamaExe = $candidatos | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
if ($ollamaExe) { Write-Host "Ollama en: $ollamaExe" }
if ($ollamaExe -and -not $apiOk) {
  Write-Host "Arrancando ollama serve ..."
  Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
  Start-Sleep 6
  try { Invoke-WebRequest -Uri "http://localhost:11434/" -TimeoutSec 4 -UseBasicParsing | Out-Null; $apiOk = $true } catch {}
}
if ($apiOk) {
  Write-Host "Ollama OK." -ForegroundColor Green
  $nmod = 0
  try { $nmod = ((Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5).models | Measure-Object).Count } catch {}
  if (-not $nmod -and $ollamaExe) {
    try { $nmod = ((& $ollamaExe list 2>$null | Select-Object -Skip 1 | Where-Object { $_.Trim() }) | Measure-Object).Count } catch {}
  }
  Write-Host "Modelos Ollama: $nmod"
} elseif ($ollamaExe) {
  Write-Host "Ollama instalado pero sin responder (revisa manualmente)." -ForegroundColor Yellow
} else { Write-Host "Ollama no instalado (opcional)." -ForegroundColor DarkGray }

# --- 4. servicios web segÃºn rol ---
Write-Host "`n[5/5] Servidores web ..." -ForegroundColor Yellow
$rol = EnvVal "ARBOL_ROL" "obrero"
$servicios = New-Object System.Collections.ArrayList
if ($rol -eq "conservante") {
  [void]$servicios.Add(@{ n="ConservanteWeb"; m="conservante_web:app"; p=(EnvVal "CONSERVANTE_WEB_PORT" "8002") })
} elseif ($rol -eq "comandante") {
  [void]$servicios.Add(@{ n="ComandanteWeb"; m="comandante_web:app"; p=(EnvVal "COMANDANTE_WEB_PORT" "8001") })
}
[void]$servicios.Add(@{ n="ArbolWeb"; m="web_server:app"; p="8000" })
foreach ($s in $servicios) {
  $esc = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
  # Si el cÃ³digo cambiÃ³, reiniciar aunque el puerto estÃ© ocupado (cargar lo nuevo)
  if ($esc -and $codigoCambio) {
    Write-Host "â†’ $($s.n): cÃ³digo nuevo, reiniciando ..."
    try { schtasks /End /TN $s.n 2>&1 | Out-Null } catch {}
    Start-Sleep 2
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like ("*" + $s.m + "*") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $esc = $null
  }
  if ($esc) { Write-Host "$($s.n) ya activo en :$($s.p)" -ForegroundColor Green; continue }
  $bat = Join-Path $env:APPDATA ($s.n + ".bat")
  # Los .bat fuerzan AUTO_OPEN_BROWSER=false: un servidor lanzado desde aquÃ­ o por
  # tareas (sesiÃ³n 0) no abre pestaÃ±as solo; Levantar abre solo :8000 al final.
  Set-Content -Path $bat -Value ('@echo off' + "`r`n" + 'set AUTO_OPEN_BROWSER=false' + "`r`n" + 'cd /d "' + $repo + '"' + "`r`n" + '"' + $PY + '" -m uvicorn ' + $s.m + ' --host 127.0.0.1 --port ' + $s.p) -Encoding ASCII -Force
  # Recrear limpio: si la tarea existÃ­a de otro usuario/instalaciÃ³n, el principal
  # obsoleto auto-terminaba el servicio (267014). AsÃ­ el principal es quien corre hoy.
  try { schtasks /Delete /TN $s.n /F 2>&1 | Out-Null } catch {}
  try { schtasks /Create /TN $s.n /TR "`"$bat`"" /SC ONLOGON /RL HIGHEST /F 2>&1 | Out-Null } catch {}
  # Arrancar ahora si el puerto estÃ¡ libre
  $yaEscucha = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
  if ($yaEscucha) {
    Write-Host "â†’ $($s.n) ya activo en :$($s.p)"
  } else {
    try { Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $bat -WindowStyle Hidden | Out-Null; Write-Host "â†’ $($s.n) iniciado en :$($s.p) (24/7)" } catch { Write-Host "âš ï¸  no se pudo arrancar $($s.n): $_" -ForegroundColor Yellow }
  }
}
Start-Sleep 3
Write-Host "`n===== RESUMEN =====" -ForegroundColor Cyan
foreach ($s in $servicios) {
  # Arranque en frÃ­o (import crewai/fastmcp) tarda 20-60s: sondear hasta 60s
  # en vez de declarar FALLO a los 6s.
  $esc = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
  for ($i = 0; ($i -lt 11) -and (-not $esc); $i++) {
    Start-Sleep 5
    $esc = Get-NetTCPConnection -LocalPort $s.p -State Listen -ErrorAction SilentlyContinue
  }
  if ($esc) { Write-Host "OK  $($s.n) :$($s.p)" -ForegroundColor Green }
  else { Write-Host "FALLO $($s.n) :$($s.p)" -ForegroundColor Red }
}
if ($tsOk) { Write-Host "OK  Tailscale $tsIp" -ForegroundColor Green }
Write-Host "Listo: $(EnvVal 'ARBOL_ID' '?') ($(EnvVal 'ARBOL_ROL' '?'))"

# --- Apertura web al terminar (solo sesiÃ³n interactiva: doble clic) ---
# Abre UN solo panel: LEVANTAR_URL si estÃ¡ definido, si no el ArbolWeb (:8000,
# el panel del operador local en todo Ã¡rbol). Los .bat fuerzan
# AUTO_OPEN_BROWSER=false asÃ­ los servidores no duplican pestaÃ±as; las tareas
# programadas (sesiÃ³n 0) de todos modos no pueden mostrar ventanas.
# El :8001/:8002 siguen corriendo para gestiÃ³n remota (tailnet).
if ([Environment]::UserInteractive -and ((EnvVal "AUTO_OPEN_BROWSER" "false").Trim().ToLower() -in @("true","1","yes","on","si"))) {
  $abrirUrl = (EnvVal "LEVANTAR_URL" "").Trim()
  if (-not $abrirUrl) { $abrirUrl = "http://127.0.0.1:8000/" }
  $abrirOk = $false
  try {
    $puertoAbrir = ([uri]$abrirUrl).Port
    $esc = Get-NetTCPConnection -LocalPort $puertoAbrir -State Listen -ErrorAction SilentlyContinue
    if ($esc) {
      Write-Host "â†’ abriendo $abrirUrl ..."
      Start-Process $abrirUrl
      $abrirOk = $true
    }
  } catch {}
  if (-not $abrirOk) {
    Write-Host "âš ï¸  $abrirUrl no responde, no se abre el navegador." -ForegroundColor Yellow
  }
}
