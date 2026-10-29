# openbot_guardia.ps1 — vigilante del API OpenBot (buns server/worker de Windows).
# Corre como tarea S4U (yazminlap\agente). Cada 5 min:
#   1. GET 127.0.0.1:3001/api/me; si falla -> schtasks /run OpenBot-Server + OpenBot-Worker
#   2. Espera 60s y re-verifica; avisa por Telegram solo en transiciones.
param()
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$logDir = 'C:\srv\semilla-colmena\logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir 'openbot_guardia.log'

function Log($m) { Add-Content -Path $log -Encoding UTF8 -Value ('{0} {1}' -f (Get-Date -Format s), $m) }

function Api-Viva {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3001/api/me' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
  } catch { return $false }
}

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

Log 'guardia openbot arranque (api/me cada 5 min)'
$vivoPrevio = Api-Viva
if ($vivoPrevio) { Log 'estado inicial api: VIVA' } else { Log 'estado inicial api: CAIDA' }
while ($true) {
  if (-not (Api-Viva)) {
    Log 'API caida -> relanzando OpenBot-Server + OpenBot-Worker'
    schtasks /run /tn OpenBot-Server 2>&1 | Out-Null
    schtasks /run /tn OpenBot-Worker 2>&1 | Out-Null
    Start-Sleep -Seconds 60
    if (Api-Viva) { Log 'API recuperada tras relanzar' }
    else { Log 'API sigue caida tras relanzar (reintento en 5 min)' }
  }
  $vivo = Api-Viva
  if ($vivo -and -not $vivoPrevio) {
    $hora = Get-Date -Format 'HH:mm'
    Avisa-Telegram ("✅ API OpenBot operativa de nuevo ($hora) — cerebro del bot en linea.")
  }
  if (-not $vivo -and $vivoPrevio) {
    Avisa-Telegram ("⚠️ API OpenBot caida — intentando relanzar buns automaticamente. Te aviso cuando vuelva.")
  }
  $vivoPrevio = $vivo
  Start-Sleep -Seconds 300
}
