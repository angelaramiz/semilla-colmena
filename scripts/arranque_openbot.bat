@echo off
rem =====================================================================
rem Lanza OpenBot server (:3001, bind 127.0.0.1) o worker en C:\srv\bots
rem openbot. Uso desde tarea SYSTEM de las fases:
rem   arranque_openbot.bat server | worker
rem Los secretos viven unicamente en .env (nunca en este archivo).
rem NOTA host: bun NO reemplaza vars ya-existentes con --env-file; el host
rem puede exportar OPENAI_BASE_URL/OPENAI_API_KEY globales, por eso se
rem fuerzan desde .env antes de arrancar (igual que start.sh upstream).
rem =====================================================================
if not "%~1"=="server" if not "%~1"=="worker" echo uso: %~nx0 server^|worker & exit /b 1
cd /d C:\srv\bots\openbot || exit /b 1
set "OPENAI_BASE_URL="
set "OPENAI_API_KEY="
for /f "tokens=1,* delims==" %%A in ('findstr /B "OPENAI_BASE_URL=" .env') do set "OPENAI_BASE_URL=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /B "OPENAI_API_KEY=" .env') do set "OPENAI_API_KEY=%%B"
if "/%1/"=="/server/" (
  cd server
  if not exist ..\.logs mkdir ..\.logs
  ..\.fase_b\bun.exe --env-file=../.env src/production-entry.ts >> ..\.logs\server.log 2>&1
) else (
  if not exist .logs mkdir .logs
  .fase_b\bun.exe --env-file=.env worker/src/index.ts >> .logs\worker.log 2>&1
)
