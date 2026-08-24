@echo off
REM ============================================================
REM  empaquetar.bat — Genera semilla-colmena.exe (autocontenido).
REM  Doble clic o:  empaquetar.bat
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0empaquetar.ps1"
pause