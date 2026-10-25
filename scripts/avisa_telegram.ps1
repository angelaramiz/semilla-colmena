# avisa_telegram.ps1 — Envía un mensaje por Telegram usando las credenciales del HOST.
# Regla del repo: el token JAMAS vive en codigo ni repo; se lee del registro del host
# (mismo mecanismo con que servidor_bots.py inyecta TELEGRAM_* al puente ceo_bot).
# Uso: powershell -File avisa_telegram.ps1 -Texto "mensaje"
param(
    [Parameter(Mandatory = $true)][string]$Texto,
    [int]$Parte = 3900
)
$ErrorActionPreference = 'Stop'

function Reg-Lee([string]$Nombre) {
    foreach ($ruta in 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'HKCU:\Environment') {
        $v = (Get-ItemProperty $ruta -ErrorAction SilentlyContinue).$Nombre
        if ($v) { return [string]$v }
    }
    return ''
}

$token = Reg-Lee 'TELEGRAM_BOT_TOKEN'
$ids = @(((Reg-Lee 'TELEGRAM_ALLOWED_IDS') -split '[,;\s]') | Where-Object { $_ })
if (-not $token -or -not $ids) {
    Write-Output 'FALLO: TELEGRAM_BOT_TOKEN o TELEGRAM_ALLOWED_IDS ausentes en el registro del host'
    exit 1
}
$chat = [string]$ids[0]
$api = 'https://api.telegram.org/bot{0}/sendMessage' -f $token

$partes = @()
for ($i = 0; $i -lt $Texto.Length; $i += $Parte) {
    $partes += $Texto.Substring($i, [Math]::Min($Parte, $Texto.Length - $i))
}
foreach ($p in $partes) {
    $body = @{ chat_id = $chat; text = $p } | ConvertTo-Json -Compress
    try {
        Invoke-RestMethod -Uri $api -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 20 | Out-Null
        Write-Output 'ENVIADO'
    } catch {
        # sin detalle de excepcion para no exponer nunca la URL con el token
        Write-Output 'FALLO envio telegram'
        exit 2
    }
}
