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

# ── Auto-actualización: pull del repo y copiar sembrar.ps1 actualizado ──
$repoDir = Join-Path $maceta "semilla-colmena"
if (Test-Path (Join-Path $repoDir ".git")) {
  Write-Host "[maceta] Actualizando repo (git pull en semilla-colmena/) ..." -ForegroundColor DarkGray
  Push-Location $repoDir
  git pull 2>&1 | Out-Null
  Pop-Location
  # copiar scripts actualizados desde el repo a la raíz de la maceta
  foreach ($f in @("sembrar.ps1", "semillero/heredado.env")) {
    $src = Join-Path $repoDir $f
    $dst = Join-Path $maceta $f
    if (Test-Path $src) {
      $dstDir = Split-Path $dst -Parent
      if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
      Copy-Item $src $dst -Force
      Write-Host "[maceta] $f actualizado desde el repo." -ForegroundColor DarkGray
    }
  }
}

$sembrar = Join-Path $maceta "sembrar.ps1"
if (Test-Path $sembrar) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File $sembrar $ArbolId -rol $Rol
} else {
  Write-Host "[maceta] ERROR: no se encontró sembrar.ps1 en $maceta" -ForegroundColor Red
}

Write-Host "[maceta] Proceso finalizado."