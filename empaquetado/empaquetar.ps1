# ============================================================================
#  empaquetar.ps1 — Genera un .exe autocontenido (SFX) de la semilla.
#  Al ejecutarlo en la máquina remota Windows: descomprime la semilla y la
#  germina en una carpeta propia "maceta".
#  Usa IExpress (incluido en Windows) — sin instalar nada.
#
#  Uso:
#    .\empaquetado\empaquetar.ps1   -> genera semilla-colmena.exe
# ============================================================================
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot)   # raíz del repo (../)
$staging = Join-Path $env:TEMP "semilla_sfx"
$outExe = Join-Path $root "semilla-colmena.exe"

# --- Limpiar staging ---
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

# --- Archivos esenciales de la semilla a empaquetar ---
$archivos = @(
  "sembrar.ps1", "sembrar.sh", ".env.example",
  "db.py", "auth.py", "main.py", "web_server.py", "comandante_web.py", "conservante_web.py",
  "pyproject.toml", "requirements.txt"
)
foreach ($f in $archivos) {
  if (Test-Path (Join-Path $root $f)) { Copy-Item (Join-Path $root $f) $staging -Recurse }
}
# Módulos Python (core, orquestador, ramas, micelio, comunicación)
foreach ($d in @("core","orquestador","contenido","redes","analitica","investigacion","atencion_cliente","planeacion","primer_contacto","micelio","comunicacion","scripts","semillero","static","comandante_web","conservante_web")) {
  if (Test-Path (Join-Path $root $d)) { Copy-Item (Join-Path $root $d) $staging -Recurse }
}
# Credenciales heredadas (ADN) si existen
if (Test-Path (Join-Path $root "semillero\heredado.env")) { Copy-Item (Join-Path $root "semillero\heredado.env") (Join-Path $staging "semillero\heredado.env") }

# --- Launcher maceta.bat (se ejecuta al descomprimir) ---
Copy-Item (Join-Path $PSScriptRoot "maceta.bat") $staging -Force

# --- Crear el script .SED de IExpress ---
$sed = Join-Path $env:TEMP "semilla.sed"
$install = '"cmd.exe" /c ""%TEMP%\maceta.bat""'  # comando que corre tras extraer

@"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimationHandler=1
UseCustomInstallProgram=TRUE
InstallProgram=$install
AlwaysInstallProgram=TRUE
[Strings]
INSTALLATION_PACKAGE=$outExe
SOURCE_DIR=$staging
"@ | Set-Content -Path $sed -Encoding ASCII

Write-Host "Generando semilla-colmena.exe ..." -ForegroundColor Cyan
$iexpress = "$env:WINDIR\System32\iexpress.exe"
if (Test-Path $iexpress) {
  Start-Process $iexpress -ArgumentList "/n","/m",$sed -Wait
  if (Test-Path $outExe) { Write-Host "✅ Creado: $outExe" -ForegroundColor Green }
  else { Write-Host "⚠️  iexpress no generó el exe (revisa el staging)." -ForegroundColor Yellow }
} else {
  Write-Host "❌ IExpress no disponible." -ForegroundColor Red
}