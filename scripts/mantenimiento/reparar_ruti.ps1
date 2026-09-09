# Kit de reparacion para ruti (cmd_01). Se ejecuta EN ruti.
# 1) uv sync con reintentos 2) chequeo de imports 3) Ollama 4) OpenRouter 5) reporte
$ErrorActionPreference = "Continue"
$repo = 'C:\Users\ritoy\OneDrive\Desktop\maceta\semilla-colmena'
$log = 'C:\Users\agente\reparar_ruti.log'
"=== reparar $(Get-Date -Format 'yyyy-MM-dd HH:mm') ===" | Out-File $log -Append

"--- [1] uv sync (3 intentos) ---" | Out-File $log -Append
Set-Location $repo
$uv = 'C:\Program Files\Python312\Scripts\uv.exe'
if (-not (Test-Path $uv)) { $uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe' }
if (-not (Test-Path $uv)) { $uv = 'uv' }
$syncOk = $false
for ($i = 1; $i -le 3 -and -not $syncOk; $i++) {
  & $uv sync 2>&1 | Select-Object -Last 2 | Out-File $log -Append
  if ($LASTEXITCODE -eq 0) { $syncOk = $true }
  else { "intento $i fallo, reintentando en 10s..." | Out-File $log -Append; Start-Sleep -Seconds 10 }
}
"uv sync OK=$syncOk" | Out-File $log -Append

"--- [2] imports ---" | Out-File $log -Append
$py = Join-Path $repo '.venv\Scripts\python.exe'
$chk = "import importlib.util`nfor m in ['crewai','crewai_tools','mcp','fastmcp','openai','requests','dotenv','sqlalchemy','uvicorn','fastapi']:`n    print(m, 'OK' if importlib.util.find_spec(m) else 'FALTA')"
Set-Content -Path "$env:TEMP\chkimp.py" -Value $chk -Encoding ASCII
& $py "$env:TEMP\chkimp.py" 2>&1 | Out-File $log -Append

"--- [3] ollama ---" | Out-File $log -Append
try {
  $tags = Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -TimeoutSec 10
  $nombres = $tags.models | ForEach-Object { $_.name }
  ('modelos: ' + ($nombres -join ', ')) | Out-File $log -Append
  ('qwen3:4b presente=' + ($nombres -contains 'qwen3:4b')) | Out-File $log -Append
} catch { ('ollama ERROR: ' + $_.Exception.Message) | Out-File $log -Append }

"--- [4] openrouter ---" | Out-File $log -Append
$envf = Join-Path $repo '.env'
$key = (Get-Content $envf | Where-Object { $_ -match '^OPENROUTER_API_KEY=' } | Select-Object -First 1)
if ($key) {
  $kv = $key.Split('=', 2)[1].Trim()
  try {
    $r = Invoke-WebRequest -Uri 'https://openrouter.ai/api/v1/models' -Headers @{ Authorization = "Bearer $kv" } -TimeoutSec 20 -UseBasicParsing
    ('openrouter HTTP ' + $r.StatusCode) | Out-File $log -Append
  } catch { ('openrouter ERROR: ' + $_.Exception.Message) | Out-File $log -Append }
} else { 'OPENROUTER_API_KEY ausente en .env' | Out-File $log -Append }

"--- [5] serpapi ---" | Out-File $log -Append
$sk = (Get-Content $envf | Where-Object { $_ -match '^SERPAPI_KEY=' } | Select-Object -First 1)
if ($sk -and $sk.Split('=', 2)[1].Trim()) { 'SERPAPI_KEY presente' | Out-File $log -Append }
else { 'SERPAPI_KEY ausente/vacia' | Out-File $log -Append }

'REPARAR_FIN' | Out-File $log -Append
Write-Host 'listo, ver reparar_ruti.log'
