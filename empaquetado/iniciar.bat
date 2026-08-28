@echo off
REM ============================================================
REM  iniciar.bat — Respaldo: si el .exe extrae pero no auto-ejecuta
REM  maceta.ps1, doble clic aquí para consolidar en "maceta" y germinar.
REM ============================================================
chcp 65001 >nul
setlocal
set "SELFDIR=%~dp0"
echo [iniciar] Consolidando y germinando la semilla ...

REM ── Auto-actualización: pull del repo y copiar scripts actualizados ──
if exist "%SELFDIR%semilla-colmena\.git" (
  echo [iniciar] Actualizando repo ...
  cd /d "%SELFDIR%semilla-colmena"
  git pull 2>&1 | findstr /v "^" >nul 2>&1
  REM copiar scripts actualizados a la raíz
  if exist "%SELFDIR%semilla-colmena\sembrar.ps1" copy /Y "%SELFDIR%semilla-colmena\sembrar.ps1" "%SELFDIR%sembrar.ps1" >nul
  if exist "%SELFDIR%semilla-colmena\maceta.ps1"   copy /Y "%SELFDIR%semilla-colmena\maceta.ps1"   "%SELFDIR%maceta.ps1"   >nul
  if exist "%SELFDIR%semilla-colmena\semillero\heredado.env" (
    if not exist "%SELFDIR%semillero" mkdir "%SELFDIR%semillero" >nul 2>&1
    copy /Y "%SELFDIR%semilla-colmena\semillero\heredado.env" "%SELFDIR%semillero\heredado.env" >nul
  )
  cd /d "%SELFDIR%"
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SELFDIR%maceta.ps1" %1 %2
echo [iniciar] Finalizado.
pause
endlocal