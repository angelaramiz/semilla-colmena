# ============================================================================
#  empaquetar_preparar.ps1 — Genera preparar-arbol.exe (SFX de un clic).
#  Ruti lo ejecuta con doble clic en su Escritorio: auto-eleva, instala
#  OpenSSH, crea el usuario de gestión y muestra su IP de Tailscale.
#
#  Uso:
#    .\empaquetado\empaquetar_preparar.ps1   -> genera preparar-arbol.exe
# ============================================================================
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
$staging = Join-Path $env:TEMP "preparar_sfx"
$outExe = Join-Path $root "preparar-arbol.exe"

$sevenZ = @("C:\Program Files\7-Zip\7z.exe","C:\Program Files (x86)\7-Zip\7z.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$sfxStub = @("C:\Program Files\7-Zip\7zCon.sfx","C:\Program Files (x86)\7-Zip\7zCon.sfx") | Where-Object { Test-Path $_ } | Select-Object -First 1

if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

Copy-Item (Join-Path $PSScriptRoot "preparar.ps1") $staging -Force
Copy-Item (Join-Path $PSScriptRoot "preparar.bat") $staging -Force

Write-Host "Generando preparar-arbol.exe ..." -ForegroundColor Cyan

if ($sevenZ -and $sfxStub) {
  $archive = Join-Path $env:TEMP "preparar.7z"
  if (Test-Path $archive) { Remove-Item $archive -Force }
  Push-Location $staging
  & $sevenZ a -r -y $archive "*" | Out-Null
  Pop-Location
  $config = Join-Path $env:TEMP "preparar_config.txt"
  Set-Content -Path $config -Value @"
;!@Install@!UTF-8!
Title=Preparar Arbol Colmena
RunProgram="preparar.bat"
;!@InstallEnd@!
"@ -Encoding ASCII
  $bytes = [System.IO.File]::ReadAllBytes($sfxStub) + [System.IO.File]::ReadAllBytes($config) + [System.IO.File]::ReadAllBytes($archive)
  [System.IO.File]::WriteAllBytes($outExe, $bytes)
  if (Test-Path $outExe) { Write-Host "Creado: $outExe ($([math]::Round((Get-Item $outExe).Length/1KB,0)) KB)" -ForegroundColor Green }
} else {
  Write-Host "7-Zip no disponible; instala 7-Zip para generar el SFX." -ForegroundColor Red
  exit 1
}
