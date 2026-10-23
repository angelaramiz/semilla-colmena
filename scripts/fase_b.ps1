#UnaVez scripts/fase_b.ps1
# =====================================================================
# Fase B — migrar el stack OpenBot a yazminlap. Corre LOCAL en yazmin,
# en consola PowerShell ADMIN (sesion de ritoy). Idempotente:
#   powershell -ExecutionPolicy Bypass -File scripts\fase_b.ps1 -Paso 1
# Pasos:
#   1 = instalar WSL2 + Docker Desktop (REQUIERE REBOOT a mitad, se
#       relanza y sigue donde quedo)
#   2 = compose up -d + bun + tareas SYSTEM + reporte
#   3 = corte FINAL: OPENBOT_URL -> 127.0.0.1, tarea escucha ya activa
# =====================================================================
param([int]$Paso = 1)
$ErrorActionPreference = 'Stop'
$OB = 'C:\srv\bots\openbot'
$SRV_FE = 'C:\srv\semilla-colmena'

function Paso1 {
  # WSL2 (features + kernel) — con reboot pendiente, re-ejecutar despues
  wsl --install --no-distribution 2>&1 | Write-Host
  Write-Host '[PASO1] Aplicando features WSL...'
  try { wsl --update 2>&1 | Write-Host } catch { Write-Host '(wsl --update fallo; apto tras reboot)' }
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Docker.DockerDesktop -e --accept-package-agreements --accept-source-agreements --silent
  } else {
    # sin winget: MSI directo (estable)
    $msi = "$env:TEMP\DockerDesktopInstaller.exe"
    if (-not (Test-Path $msi)) {
      Invoke-WebRequest 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile $msi
    }
    & $msi install --quiet --accept-license
  }
  Write-Host '[PASO1] HECHO. SI PIDE REBOOT: reiniciie y vuelva a lanzar -Paso 1 (verificara) o -Paso 2.'
}
function Paso2 {
  docker version | Out-Null
  # restaurar datos de la base (chats/connexor) antes de arrancar server
  # (schema ya lo crea migrate-1; el dump es data-only)
  Get-Content "$OB\.fase_b\openbot_dump_data.sql" -Raw | docker exec -i openbot-postgres-1 psql -U openbot -d openbot | Select-Object -Last 2
  Push-Location $OB
  docker compose up -d
  Pop-Location
  # bun runtime copiado desde angel o descargado
  $bun = "$OB\.fase_b\bun.exe"
  if (-not (Test-Path $bun)) { throw 'Falta bun en .fase_b (copiar bun.exe desde angel: C:\Users\angel\.bun\bin\bun.exe)' }
  # tareas SYSTEM (server + worker) con restart
  $dir = "$SRV_FE\scripts\arranque_openbot.bat"
  foreach ($n in 'OpenBot-Server','OpenBot-Worker') {
    $arg = if ($n -eq 'OpenBot-Server') {'server'} else {'worker'}
    $a = New-ScheduledTaskAction -Execute $dir -Argument $arg -WorkingDirectory $OB
    $t = New-ScheduledTaskTrigger -AtStartup
    $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    $p = New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s -Principal $p -Force | Out-Null
    Start-ScheduledTask -TaskName $n
  }
  Start-Sleep -Seconds 30
  docker ps --format '{{.Names}}: {{.Status}}'
  Write-Host '[PASO2] HECHO. Verificar http://127.0.0.1:3001/api/me y logs .logs/server.log'
}
function Paso3 {
  # corte final: el bot de Zoop deja de llamar a angel
  setx /m OPENBOT_URL 'http://127.0.0.1:3001' | Out-Null
  Stop-ScheduledTask -TaskName BotsColmena
  Start-Sleep 2
  Start-ScheduledTask -TaskName BotsColmena
  Write-Host '[PASO3] HECHO: Bot en Zoop usando OpenBot LOCAL. En angel: tailscale serve --tcp=3001 off'
}
switch ($Paso) { 1 { Paso1 } 2 { Paso2 } 3 { Paso3 } }
