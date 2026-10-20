# Arrancar-Colmena.ps1 — Lanzador local de la agencia (post-login del host).
# 1) Espera Docker/Ollama  2) Levanta el puente AG-UI si no está  3) Levanta OpenBot si no está.
# Idempotente: corralo N veces, no duplica servicios. No requiere admin.
# Soporte: chimpyCtrl+Rooms. Registro: puente_agui\arranque.log
$ErrorActionPreference = "Continue"
$agencia = "C:\Users\angel\Desktop\Proyectos\agen_mrk"
$openbot = "C:\Users\angel\Desktop\Proyectos\bots\openbot"
$log = Join-Path $agencia "puente_agui\arranque.log"
"===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') arranque colmena =====" | Add-Content $log

# 1) Esperar a que Ollama (dependencia del stack) responda, max 12 min.
$ok = $false
for ($i = 0; $i -lt 72 -and -not $ok; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/" -TimeoutSec 3 -UseBasicParsing
        $ok = ($r.StatusCode -eq 200)
    } catch { Start-Sleep 10 }
}
if ($ok) { "Ollama listo" | Add-Content $log }
else { "Ollama no respondio tras 12 min; host probablemente sin Docker Desktop abierto." | Add-Content $log }

# 2) Puente AG-UI (:4210)
if (Get-NetTCPConnection -LocalPort 4210 -State Listen -ErrorAction SilentlyContinue) {
    "puente ya activo (:4210)" | Add-Content $log
} else {
    Start-Process -FilePath (Join-Path $agencia "puente_agui\.venv\Scripts\python.exe") `
        -ArgumentList "-m","uvicorn","servidor:app","--host","127.0.0.1","--port","4210" `
        -WorkingDirectory (Join-Path $agencia "puente_agui") -WindowStyle Hidden
    Start-Sleep 8
    $up = [bool](Get-NetTCPConnection -LocalPort 4210 -State Listen -ErrorAction SilentlyContinue)
    "puente: $(if ($up) {'OK'} else {'FALLO'})" | Add-Content $log
}

# 3) OpenBot: app :3010 + server :3001 via start.sh (Git Bash en fondo)
# Vars de modelo FIJAS aquí: el server hereda el entorno y cualquier
# OPENAI_BASE_URL heredado (p. ej. Ollama 11434 de otra sesión) lo desvía.
# La KEY vive en variable de entorno ORCA_API_KEY del host (nunca en repo).
if ((Get-NetTCPConnection -LocalPort 3010 -State Listen -ErrorAction SilentlyContinue) -and
    (Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue)) {
    "openbot ya activo (:3001/:3010)" | Add-Content $log
} else {
    if (-not $env:ORCA_API_KEY) { "FALTA ORCA_API_KEY en entorno; openbot NO lanzado" | Add-Content $log }
    else {
        $bashCmd = 'export PATH=/usr/bin:/mingw64/bin:/c/Users/angel/.bun/bin:/c/Program\ Files/Docker/Docker/resources/bin:$PATH; export OPENAI_BASE_URL=https://api.orcarouter.ai/v1 OPENAI_API_KEY=' + $env:ORCA_API_KEY + '; unset OPENAI_MODEL; cd /c/Users/angel/Desktop/Proyectos/bots/openbot && ./scripts/start.sh > .logs/start-auto.log 2>&1'
        Start-Process -FilePath "C:\Program Files\Git\bin\bash.exe" -ArgumentList "-c", $bashCmd -WindowStyle Hidden
        "openbot lanzado en fondo (start-auto.log)" | Add-Content $log
    }
}
