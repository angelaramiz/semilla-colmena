# ============================================================================
#  maceta.ps1 — Launcher de la SEMILLA empaquetada (SFX).
#  El .exe extrae el contenido en el directorio actual; este launcher CONSOLIDA
#  todo en UNA carpeta raíz única llamada "maceta" y allí germina la semilla.
# ============================================================================
param(
  [string]$ArbolId = "arbol_obrero_01",
  [string]$Rol = "obrero"
)
$ErrorActionPreference = "Continue"

# Directorio donde el SFX extrajo (CWD del exe)
$extraido = (Get-Location).Path
# Carpeta raíz única que alberga TODO el árbol
$maceta = Join-Path $extraido "maceta"

Write-Host "[maceta] Consolidando la semilla en: $maceta" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $maceta | Out-Null

# Mover TODO el contenido extraído (excepto la propia maceta) a la carpeta raíz
Get-ChildItem $extraido -Force | Where-Object { $_.Name -ne "maceta" } | ForEach-Object {
  Move-Item -Path $_.FullName -Destination $maceta -Force
}

# Germinar dentro de la maceta
Set-Location $maceta
Write-Host "[maceta] Germinando ($ArbolId, rol=$Rol) ..." -ForegroundColor Cyan

$sembrar = Join-Path $maceta "sembrar.ps1"
if (Test-Path $sembrar) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File $sembrar $ArbolId -rol $Rol
} else {
  Write-Host "[maceta] ERROR: no se encontró sembrar.ps1 en $maceta" -ForegroundColor Red
}

Write-Host "[maceta] Proceso finalizado."