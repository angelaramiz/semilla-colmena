@echo off
REM Preparar Arbol Colmena - lanzador con ventana persistente y log.
REM No se cierra solo: muestra el resultado y espera una tecla.
chcp 65001 >nul
cd /d "%~dp0"
set LOG=%USERPROFILE%\Desktop\preparar_log.txt
echo [%date% %time%] Iniciando preparar.ps1 > "%LOG%"
powershell -NoProfile -ExecutionPolicy Bypass -File "preparar.ps1" >> "%LOG%" 2>&1
echo [%date% %time%] Codigo de salida: %ERRORLEVEL% >> "%LOG%"
echo.
echo ----------------------------------------
echo Log guardado en: %LOG%
echo Codigo de salida: %ERRORLEVEL%
echo ----------------------------------------
pause
