# docker_guardia.ps1 V2 — vigilante del ENGINE NATIVO dockerd (distro WSL colmena).
# Corre como tarea SYSTEM (AtStartup) en yazmin. Cada 2 min:
#   1. si dockerd no responde -> despierta la distro (wsl.conf [boot] lanza dockerd)
#   2. si el stack compose no esta -> docker compose up -d
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

# Aviso por Telegram con las credenciales del HOST (registro HKLM/HKCU, mismo patron
# que servidor_bots.py; el token jamas vive en repo ni en logs).
function Avisa-Telegram([string]$Texto) {
  function Reg-Lee([string]$Nombre) {
    foreach ($ruta in 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'HKCU:\Environment') {
      $v = (Get-ItemProperty $ruta -ErrorAction SilentlyContinue).$Nombre
      if ($v) { return [string]$v }
    }
    return ''
  }
  $token = Reg-Lee 'TELEGRAM_BOT_TOKEN'
  $ids = ((Reg-Lee 'TELEGRAM_ALLOWED_IDS') -split '[,;\s]') | Where-Object { $_ }
  if (-not $token -or -not $ids) { Log 'aviso TG omitido (credenciales ausentes en host)'; return }
  $chat = $ids[0].Trim()
  $api = 'https://api.telegram.org/bot{0}/sendMessage' -f $token
  $body = @{ chat_id = $chat; text = $Texto.Substring(0, [Math]::Min(3900, $Texto.Length)) } | ConvertTo-Json -Compress
  try {
    Invoke-RestMethod -Uri $api -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 20 | Out-Null
    Log 'aviso TG enviado'
  } catch { Log 'aviso TG fallo (sin detalle: token en URL)' }
}

Log 'guardia v2 arranque (engine nativo en colmena)'
$vivoPrevio = $false
while ($true) {
  if (-not (Engine-Vivo)) {
    Log 'ENGINE caido -> despertando distro colmena'
    wsl --terminate colmena 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    $dead = $true
    for ($i = 0; $i -lt 24; $i++) {
      Start-Sleep -Seconds 10
      if (Engine-Vivo) { $espera = ($i + 1) * 10; Log ('ENGINE vivo (espera {0}s)' -f $espera); $dead = $false; break }
    }
    if ($dead) {
      Log 'boot command no alcanzo -> dockerd manual'
      wsl -d colmena -u root -- sh -c '(nohup dockerd >/var/log/dockerd.log 2>&1 &)' 2>&1 | Out-Null
    }
  }
  if ((Engine-Vivo) -and -not (Stack-Vivo)) {
    Log 'STACK vacio -> compose up -d'
    $salida = wsl -d colmena -u root -- sh -c ('cd {0} && docker compose up -d 2>&1 | tail -5' -f $OB) 2>&1
    foreach ($l in $salida) { Log (($l -replace "`0", '').Trim()) }
  }

  # Transicion CAIDO -> OPERATIVO: aviso unico por Telegram (spam cero en ciclos vivos)
  $vivoAhora = (Engine-Vivo) -and (Stack-Vivo)
  if ($vivoAhora -and -not $vivoPrevio) {
    Log 'STACK OPERATIVO -> aviso Telegram'
    $rep = wsl -d colmena -u root -- sh -c 'docker ps --format {{.Names}}' 2>&1
    $n = ($rep -join ' ').Trim()
    $hora = Get-Date -Format 'HH:mm'
    Avisa-Telegram ("Arbol yazminLap ACTIVO Y OPERATIVO ($hora)`nEngine dockerd vivo - stack OpenBot corriendo: " + $n)
  }
  $vivoPrevio = $vivoAhora

  Start-Sleep -Seconds 120
}
