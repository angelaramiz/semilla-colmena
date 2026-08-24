# ============================================================================
#  empaquetar.ps1 — Genera un .exe autocontenido (SFX) de la semilla.
#  Al ejecutarlo en la máquina remota Windows: descomprime la semilla y la
#  germina en una carpeta propia "maceta".
#  Usa 7-Zip SFX (7zCon.sfx) si está instalado; si no, cae a IExpress.
#
#  Uso:
#    .\empaquetado\empaquetar.ps1   -> genera semilla-colmena.exe
# ============================================================================
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
$staging = Join-Path $env:TEMP "semilla_sfx"
$outExe = Join-Path $root "semilla-colmena.exe"

$sevenZ = @("C:\Program Files\7-Zip\7z.exe","C:\Program Files (x86)\7-Zip\7z.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$sfxStub = @("C:\Program Files\7-Zip\7zCon.sfx","C:\Program Files (x86)\7-Zip\7zCon.sfx") | Where-Object { Test-Path $_ } | Select-Object -First 1

if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

# --- Archivos esenciales de la semilla ---
$archivos = @(
  "sembrar.ps1","sembrar.sh",".env.example",
  "db.py","auth.py","main.py","web_server.py","comandante_web.py","conservante_web.py",
  "pyproject.toml","requirements.txt"
)
foreach ($f in $archivos) { if (Test-Path (Join-Path $root $f)) { Copy-Item (Join-Path $root $f) $staging -Recurse -Force } }
foreach ($d in @("core","orquestador","contenido","redes","analitica","investigacion","atencion_cliente","planeacion","primer_contacto","micelio","comunicacion","scripts","semillero","static","comandante_web","conservante_web")) {
  if (Test-Path (Join-Path $root $d)) { Copy-Item (Join-Path $root $d) $staging -Recurse -Force }
}
# Credenciales heredadas (ADN)
if (Test-Path (Join-Path $root "semillero\heredado.env")) { Copy-Item (Join-Path $root "semillero\heredado.env") (Join-Path $staging "semillero\heredado.env") -Force }
# Launcher
Copy-Item (Join-Path $PSScriptRoot "maceta.ps1") $staging -Force

Write-Host "Generando semilla-colmena.exe ..." -ForegroundColor Cyan

if ($sevenZ -and $sfxStub) {
  # ---- Método 7-Zip SFX ----
  $archive = Join-Path $env:TEMP "semilla.7z"
  if (Test-Path $archive) { Remove-Item $archive -Force }
  Push-Location $staging
  & $sevenZ a -r -y $archive "*" | Out-Null
  Pop-Location
  # config de 7z SFX: tras extraer, ejecuta maceta.ps1 (consolida en "maceta" y germina)
  $config = Join-Path $env:TEMP "semilla_config.txt"
  Set-Content -Path $config -Value @"
;!@Install@!UTF-8!
Title=Semilla Colmena
RunProgram="powershell.exe -NoProfile -ExecutionPolicy Bypass -File maceta.ps1"
;!@InstallEnd@!
"@ -Encoding ASCII
  # concatenar stub + config + archivo
  $bytes = [System.IO.File]::ReadAllBytes($sfxStub) + [System.IO.File]::ReadAllBytes($config) + [System.IO.File]::ReadAllBytes($archive)
  [System.IO.File]::WriteAllBytes($outExe, $bytes)
  if (Test-Path $outExe) { Write-Host "✅ Creado: $outExe ($([math]::Round((Get-Item $outExe).Length/1MB,1)) MB)" -ForegroundColor Green }
} else {
  # ---- Fallback: IExpress (puede abrir ventana) ----
  Write-Host "⚠️  7-Zip no disponible; usando IExpress (puede abrir ventana)." -ForegroundColor Yellow
  $sed = Join-Path $env:TEMP "semilla.sed"
  @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimationHandler=1
UseCustomInstallProgram=TRUE
InstallProgram=cmd.exe /c maceta.bat
[Strings]
INSTALLATION_PACKAGE=$outExe
SOURCE_DIR=$staging
"@ | Set-Content -Path $sed -Encoding ASCII
  $iexpress = "$env:WINDIR\System32\iexpress.exe"
  if (Test-Path $iexpress) { Start-Process $iexpress -ArgumentList "/n","/m",$sed -Wait }
}