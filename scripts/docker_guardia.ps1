# docker_guardia.ps1 — vigilante del engine Docker en la colmena.
# Corre como tarea SYSTEM (AtStartup). Cada 2 min: si no responde el
# engine (npipe), despierta Docker Desktop oculto y espera hasta 240s.
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$dd = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$logDir = 'C:\srv\semilla-colmena\logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir 'docker_guardia.log'

function Engine-Vivo {
  $v = & $docker version --format '{{.Server.Version}}' 2>&1
  return ("$v" -match '^\d')
}

while ($true) {
  if (-not (Engine-Vivo)) {
    Add-Content -Path $log -Encoding UTF8 -Value ('{0} ENGINE caido -> despierto Docker Desktop' -f (Get-Date -Format s))
    Start-Process -FilePath $dd -WindowStyle Hidden
    for ($i = 0; $i -lt 24; $i++) {
      Start-Sleep -Seconds 10
      if (Engine-Vivo) {
        $v = & $docker version --format '{{.Server.Version}}' 2>&1
        Add-Content -Path $log -Encoding UTF8 -Value ('{0} ENGINE vivo: {1} (espera {2}s)' -f (Get-Date -Format s), $v, (($i + 1) * 10))
        break
      }
    }
    if (-not (Engine-Vivo)) {
      Add-Content -Path $log -Encoding UTF8 -Value ('{0} ENGINE NO ARRIBO tras 240s' -f (Get-Date -Format s))
    }
  }
  Start-Sleep -Seconds 120
}
