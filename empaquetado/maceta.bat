@echo off
REM ============================================================
REM  maceta.bat — Launcher de la SEMILLA empaquetada.
REM  Se ejecuta al descomprimir el .exe. Crea la carpeta "maceta"
REM  (su propia maceta), coloca ahí la semilla y la germina.
REM ============================================================
setlocal
set "SELFDIR=%~dp0"
set "MACETA=%SELFDIR%maceta"

echo [maceta] Creando maceta: %MACETA%
mkdir "%MACETA%" 2>nul

REM Copiar los archivos de la semilla (ya extraídos en SELFDIR) a la maceta
xcopy /y /e /i "%SELFDIR%*" "%MACETA%\" >nul 2>&1

echo [maceta] Germinando la semilla en %MACETA% ...
cd /d "%MACETA%"

REM Args por defecto si no se pasan
set "ARBOL_ID=%~1"
set "ROL=%~2"
if "%ARBOL_ID%"=="" set "ARBOL_ID=arbol_obrero_01"
if "%ROL%"=="" set "ROL=obrero"

powershell -NoProfile -ExecutionPolicy Bypass -File "%MACETA%\sembrar.ps1" "%ARBOL_ID%" -rol "%ROL%"

echo [maceta] Proceso finalizado.
pause
endlocal