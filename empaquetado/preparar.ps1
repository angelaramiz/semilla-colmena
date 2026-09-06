# ============================================================================
#  preparar.ps1 — Prepara una máquina Windows para ser ÁRBOL de la colmena.
#  Ruti (o cualquiera) lo ejecuta con doble clic:
#   1. Se auto-eleva a administrador (un solo clic en el UAC).
#   2. Instala OpenSSH Server, lo arranca (automático) y abre el puerto 22.
#   3. Crea el usuario local 'agente' (admin) para gestión remota.
#   4. Muestra la IP de Tailscale para reportarla al conservante.
# ============================================================================
param(
  [string]$Usuario = "agente",
  [string]$Password = "Agr0c0lmen4!"
)
$ErrorActionPreference = "Continue"
try {
  $enc = New-Object System.Text.UTF8Encoding($false)
  [Console]::InputEncoding = $enc; [Console]::OutputEncoding = $enc; $OutputEncoding = $enc
} catch {}

# --- Auto-elevación (un clic en UAC, sin consola manual) ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Host "Solicitando permisos de administrador ..."
  try {
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs -ErrorAction Stop
    Write-Host "Ventana de administrador lanzada. Puedes cerrar esta."
  } catch {
    Write-Host "ERROR no se pudo elevar permisos: $_" -ForegroundColor Red
    Write-Host "Causas posibles: tu cuenta no es administradora, UAC desactivado," -ForegroundColor Yellow
    Write-Host "política de ejecución bloqueada o el antivirus intervino." -ForegroundColor Yellow
  }
  exit
}

Write-Host "`n===== PREPARAR ÁRBOL =====" -ForegroundColor Cyan

Write-Host "`n[1/4] OpenSSH Server ..." -ForegroundColor Yellow
try {
  $cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction Stop | Select-Object -First 1
  if ($cap.State -ne "Installed") {
    Write-Host "Instalando OpenSSH Server (puede tardar 1-2 min) ..."
    Add-WindowsCapability -Online -Name $cap.Name -ErrorAction Stop | Out-Null
  } else { Write-Host "OpenSSH Server ya instalado." }
} catch { Write-Host "AVISO no se pudo instalar OpenSSH: $_" -ForegroundColor Red }
try {
  Start-Service sshd -ErrorAction Stop
  Set-Service -Name sshd -StartupType Automatic -ErrorAction Stop
  if (-not (Get-NetFirewallRule -Name "sshd-colmena" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name "sshd-colmena" -DisplayName "OpenSSH Colmena" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
  }
  Write-Host "sshd: $((Get-Service sshd).Status) (automático, puerto 22 abierto)"
} catch { Write-Host "AVISO no se pudo arrancar sshd: $_" -ForegroundColor Red }

Write-Host "`n[2/4] Usuario de gestión '$Usuario' ..." -ForegroundColor Yellow
try {
  $u = Get-LocalUser -Name $Usuario -ErrorAction SilentlyContinue
  if (-not $u) {
    $sec = ConvertTo-SecureString $Password -AsPlainText -Force
    New-LocalUser -Name $Usuario -Password $sec -FullName "Agente Colmena" -Description "Gestión remota de la colmena" -ErrorAction Stop | Out-Null
    Add-LocalGroupMember -Group "Administradores" -Member $Usuario -ErrorAction Stop
    Write-Host "Usuario '$Usuario' creado (administrador)."
  } else { Write-Host "Usuario '$Usuario' ya existe." }
} catch { Write-Host "AVISO no se pudo crear el usuario: $_" -ForegroundColor Red }

Write-Host "`n[3/4] Verificación ..." -ForegroundColor Yellow
$t = Test-NetConnection -ComputerName 127.0.0.1 -Port 22 -WarningAction SilentlyContinue
if ($t.TcpTestSucceeded) { Write-Host "SSH local en puerto 22: OK" -ForegroundColor Green }
else { Write-Host "SSH local en puerto 22: FALLO (revisa el antivirus/firewall)" -ForegroundColor Red }

Write-Host "`n[4/4] IP de Tailscale (repórtala al conservante) ..." -ForegroundColor Yellow
try {
  $ip = (tailscale ip -4 2>$null | Select-Object -First 1).ToString().Trim()
  if ($ip) { Write-Host "Tu IP Tailscale es: $ip" -ForegroundColor Green }
  else { Write-Host "Tailscale no conectado. Ábrelo e inicia sesión." -ForegroundColor Yellow }
} catch { Write-Host "Tailscale no instalado o no conectado." -ForegroundColor Yellow }

Write-Host "`nListo. Ya puedes cerrar esta ventana." -ForegroundColor Green
pause
