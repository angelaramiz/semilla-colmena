# docker_guardia.ps1 V3 — vigilante del ENGINE NATIVO (distro WSL colmena)
# Hallazgo 2026-10-24: WSL NO corre como SYSTEM (WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED)
# y los procesos wsl mueren con su sesion de origen.
# Solucion: la guardia corre como tarea S4U (yazminlap\agente, sin password) y
# sostiene un HOLDER wsl permanente (vm_holder.sh = sleep infinity) que mantiene
# la VM colmena siempre viva. dockerd + compose revive lo cubre /etc/wsl.conf boot.
param()
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$logDir = 'C:\srv\semilla-colmena\logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir 'docker_guardia.log'
$OB = '/root/openbot'

function Log($m) { Add-Content -Path $log -Encoding UTF8 -Value ('{0} {1}' -f (Get-Date -Format s), $m) }

function Engine-Vivo {
  $r = wsl -d colmena -u root -- docker version --format '{{.Server.Version}}' 2>&1
  return ("$r" -match '^\d')
}

function Stack-Vivo {
  $r = wsl -d colmena -u root -- sh -c 'docker ps --filter name=openbot-postgres-1 --format {{.Names}}' 2>&1
  return ("$r" -match 'openbot-postgres-1')
}

function Holder-Vivo {
  $p = Get-CimInstance Win32_Process -Filter "Name='wsl.exe'" -ErrorAction SilentlyContinue
  return ($p | Where-Object { $_.CommandLine -match 'vm_holder\.sh' })
}

# Aviso por Telegram con las credenciales del HOST (registro HKLM/HKCU, mismo patron
# que servidor_bots.py; el token jamas vive en repo ni en logs).
# Fix 2026-10-24: envolver en @() para que $ids[0] no sea un Char.
function Avisa-Telegram([string]$Texto) {
  function Reg-Lee([string]$Nombre) {
    foreach ($ruta in 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'HKCU:\Environment') {
      $v = (Get-ItemProperty $ruta -ErrorAction SilentlyContinue).$Nombre
      if ($v) { return [string]$v }
    }
    return ''
  }
  $token = Reg-Lee 'TELEGRAM_BOT_TOKEN'
  $ids = @(((Reg-Lee 'TELEGRAM_ALLOWED_IDS') -split '[,;\s]') | Where-Object { $_ })
  if (-not $token -or -not $ids) { Log 'aviso TG omitido (credenciales ausentes en host)'; return }
  $chat = [string]$ids[0]
  $api = 'https://api.telegram.org/bot{0}/sendMessage' -f $token
  $body = @{ chat_id = $chat; text = $Texto.Substring(0, [Math]::Min(3900, $Texto.Length)) } | ConvertTo-Json -Compress
  try {
    Invoke-RestMethod -Uri $api -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 20 | Out-Null
    Log 'aviso TG enviado'
  } catch { Log 'aviso TG fallo (sin detalle: token en URL)' }
}

Log 'guardia v3 arranque (holder permanente + engine nativo en colmena, S4U)'
$vivoPrevio = $false
while ($true) {
  # 1) HOLDER: mantener una VM colmena permanente (wsl con sleep infinity)
  if (-not (Holder-Vivo)) {
    Log 'HOLDER ausente -> lanzando wsl permanente (vm_holder.sh)'
    Start-Process -FilePath 'wsl.exe' -ArgumentList '-d', 'colmena', '-u', 'root', '--', '/usr/local/bin/vm_holder.sh' -WindowStyle Hidden
    Start-Sleep -Seconds 8
  }

  # 2) ENGINE: boot_docker.sh (wsl.conf) levanta dockerd si la VM recien desperto
  if (-not (Engine-Vivo)) {
    Log 'ENGINE caido -> esperando boot de colmena (boot_docker.sh)'
    for ($i = 0; $i -lt 12; $i++) {
      Start-Sleep -Seconds 10
      if (Engine-Vivo) { Log ('ENGINE vivo tras {0}s' -f (($i + 1) * 10)); break }
    }
  }

  # 3) STACK: compose up si contenedores ausentes (sin --build: imagenes ya existen)
  if ((Engine-Vivo) -and -not (Stack-Vivo)) {
    Log 'STACK vacio -> compose up -d'
    $salida = wsl -d colmena -u root -- sh -c ('cd {0} && docker compose up -d 2>&1 | tail -5' -f $OB) 2>&1
    foreach ($l in $salida) { Log (($l -replace "`0", '').Trim()) }
  }

  # 4) Transicion CAIDO -> OPERATIVO: aviso unico por Telegram (spam cero)
  $vivoAhora = (Engine-Vivo) -and (Stack-Vivo)
  if ($vivoAhora -and -not $vivoPrevio) {
    Log 'STACK OPERATIVO -> aviso Telegram'
    $rep = wsl -d colmena -u root -- sh -c 'docker ps --format {{.Names}}' 2>&1
    $n = (($rep -join ' ').Trim())
    $hora = Get-Date -Format 'HH:mm'
    Avisa-Telegram ("Arbol yazminLap ACTIVO Y OPERATIVO ($hora)`nHolder permanente + engine dockerd vivo - stack OpenBot corriendo: " + $n)
  }
  $vivoPrevio = $vivoAhora

  Start-Sleep -Seconds 60
}
