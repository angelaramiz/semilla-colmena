@echo off
rem Launcher del servidor de bots 24/7. Tarea SYSTEM lo ejecuta al boot.
rem activar escucha de Telegram (corte a Zoop): setx /m SERVIDOR_BOTS_ALL 1
rem por defecto solo MCP hasta el corte, para no duplicar polling con otro host
cd /d %~dp0..
set PYTHONIOENCODING=utf-8
if not exist logs mkdir logs
.venv\Scripts\python.exe scripts\servidor_bots.py >> logs\servidor_system.log 2>&1

