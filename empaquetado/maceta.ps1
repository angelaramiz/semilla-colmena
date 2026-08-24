# ============================================================================
#  maceta.ps1 — Launcher de la SEMILLA empaquetada (SFX).
#  El .exe extrae el contenido en el directorio actual. Este launcher consolida
#  todo en UNA carpeta raíz única llamada "maceta" y allí germina la semilla.
#  Evita anidar "maceta/maceta": si ya estamos en una carpeta que contiene
#  sembrar.ps1, consolida en el directorio actual.
# ============================================================================
param(
  [string]$ArbolId = "arbol_obrero_01",
  [string]$Rol = "obrero"
)
$ErrorActionPreference = "Continue"

$actual = (Get-Location).Path
$yaEnMaceta = (Split-Path $actual -Leaf) -eq "maceta"
$tieneSembrar = Test-Path (Join-Path $actual "sembrar.ps1")

if ($yaEnMaceta -or $tieneSembrar) {
  # Ya estamos dentro de la maceta (o hay una semilla consolidada) — no anidar.
  $maceta = $actual
  Write-Host "[maceta] Consolidado en (ya es la maceta): $maceta" -ForegroundColor Cyan
} else {
  # Archivos dispersos en el directorio actual → crear UNA carpeta "maceta" y mover.
  $maceta = Join-Path $actual "maceta"
  Write-Host "[maceta] Creando carpeta raíz única: $maceta" -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path $maceta | Out-Null
  Get-ChildItem $actual -Force | Where-Object { $_.Name -ne "maceta" } | ForEach-Object {
    Move-Item -Path $_.FullName -Destination $maceta -Force
  }
}

# Germinar dentro de la maceta
Set-Location $maceta
Write-Host "[maceta] Germinando ($ArbolId, rol=$Rol) ..." -ForegroundColor Cyan

# ── Auto-actualización: pull ANTES de cargar sembrar.ps1 en memoria ──
if (Test-Path ".git") {
  Write-Host "[maceta] Actualizando repo (git pull) ..." -ForegroundColor DarkGray
  git pull 2>&1 | Out-Null
}

$sembrar = Join-Path $maceta "sembrar.ps1"
if (Test-Path $sembrar) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File $sembrar $ArbolId -rol $Rol
} else {
  Write-Host "[maceta] ERROR: no se encontró sembrar.ps1 en $maceta" -ForegroundColor Red
}

Write-Host "[maceta] Proceso finalizado."