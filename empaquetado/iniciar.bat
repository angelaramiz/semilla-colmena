@echo off
REM ============================================================
REM  iniciar.bat — Respaldo: si el .exe extrae pero no auto-ejecuta
REM  maceta.ps1, doble clic aquí para consolidar en "maceta" y germinar.
REM ============================================================
chcp 65001 >nul
setlocal
set "SELFDIR=%~dp0"
echo [iniciar] Consolidando y germinando la semilla ...

REM ── Auto-actualización: pull ANTES de cargar maceta.ps1/sembrar.ps1 ──
cd /d "%SELFDIR%"
if exist ".git" (
  echo [iniciar] Actualizando repo ...
  git pull 2>&1 | findstr /v "^" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SELFDIR%maceta.ps1" %1 %2
echo [iniciar] Finalizado.
pause
endlocal