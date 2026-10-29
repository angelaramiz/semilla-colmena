# respaldo_openbot.ps1 — respaldo diario del arbol yazminlap (tarea 03:00 S4U agente).
# 1. pg_dump de postgres (contenedor) -> \\wsl$\colmena -> destino con fecha
# 2. copia de la memoria local del puente (cola/*.jsonl, acceso.json, aprendizajes.json, offset)
# 3. rotacion: conserva ultimos 7 de cada tipo. Avisa por Telegram solo si falla.
param()
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$logDir = 'C:\srv\semilla-colmena\logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir 'respaldo.log'
function Log($m) { Add-Content -Path $log -Encoding UTF8 -Value ('{0} {1}' -f (Get-Date -Format s), $m) }

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
  if (-not $token -or -not $ids) { return }
  $body = @{ chat_id = [string]$ids[0]; text = $Texto.Substring(0, [Math]::Min(3900, $Texto.Length)) } | ConvertTo-Json -Compress
  try { Invoke-RestMethod -Uri ('https://api.telegram.org/bot{0}/sendMessage' -f $token) -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 20 | Out-Null } catch { }
}

$Fecha = Get-Date -Format 'yyyy-MM-dd'
$Dest = 'C:\srv\semilla-colmena\respaldos-openbot'
if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
$fallos = @()

# 1) pg_dump dentro de la distro (despierta la VM si dormia)
Log 'respaldo inicio: pg_dump postgres'
wsl -d colmena -u root -- sh -c "docker exec openbot-postgres-1 pg_dump -U openbot openbot > /root/openbot/.fase_b/respaldo-$Fecha.sql 2>/tmp/pgdump.err; echo PGDUMP-EXIT:\$?" 2>&1 | Out-Null
$origen = "\\wsl$\colmena\root\openbot\.fase_b\respaldo-$Fecha.sql"
if (Test-Path $origen) {
  Copy-Item $origen (Join-Path $Dest "openbot-db-$Fecha.sql") -Force
  $mb = [math]::Round((Get-Item (Join-Path $Dest "openbot-db-$Fecha.sql")).Length / 1MB, 2)
  Log "pg_dump OK ($mb MB)"
  if ($mb -lt 0.1) { $fallos += 'dump sospechosamente pequeno' }
} else { $fallos += 'pg_dump no genero archivo'; Log 'pg_dump FALLO (sin archivo)' }

# 2) memoria local del puente
Log 'respaldo: memoria del puente'
$Cola = 'C:\srv\semilla-colmena\puente_telegram\cola'
foreach ($f in @('pendientes.jsonl', 'hechos.jsonl', 'acceso.json', 'aprendizajes.json', 'offset.txt', 'nuevo_id_asignado.json')) {
  $o = Join-Path $Cola $f
  if (Test-Path $o) { Copy-Item $o (Join-Path $Dest ("cola-{0}-{1}" -f $Fecha, $f)) -Force }
}
Log 'memoria del puente copiada'

# 3) rotacion 7 dias
foreach ($pat in @('openbot-db-*.sql', 'cola-*-pendientes.jsonl', 'cola-*-hechos.jsonl', 'cola-*-acceso.json', 'cola-*-aprendizajes.json')) {
  Get-ChildItem $Dest -Filter $pat -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -Skip 7 |
    ForEach-Object { Remove-Item $_.FullName -Force; Log ('rotado: ' + $_.Name) }
}

if ($fallos.Count -gt 0) {
  Log ('RESPALDO CON FALLOS: ' + ($fallos -join '; '))
  Avisa-Telegram ("⚠️ Respaldo nocturno con fallos ($Fecha): " + ($fallos -join '; '))
} else {
  Log 'respaldo OK completo'
}
