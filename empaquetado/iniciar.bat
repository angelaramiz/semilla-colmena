@echo off
REM ============================================================
REM  iniciar.bat — Respaldo: si el .exe extrae pero no auto-ejecuta
REM  maceta.ps1, doble clic aquí para consolidar en "maceta" y germinar.
REM ============================================================
setlocal
set "SELFDIR=%~dp0"
echo [iniciar] Consolidando y germinando la semilla ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SELFDIR%maceta.ps1" %1 %2
echo [iniciar] Finalizado.
pause
endlocal