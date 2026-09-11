# AGENTS.md — Reglas para agentes IA en este proyecto

## 🔍 Código: CodeGraph primero

Repo indexado (`.codegraph/` + MCP `codegraph`). Antes de `grep`/`find`/glob o leer a ciegas: `codegraph_explore` (fuente verbatim + blast radius). CLI: `codegraph explore "símbolos o pregunta"`. El watcher re-indexa en ~1s; para cambios masivos, `codegraph sync`.

## ⚙️ Entorno y comandos (solo `uv`, nunca `pip` global)

- Python ≥3.12. Deps: `uv sync` · correr: `uv run python <script>` · añadir: `uv add <paq>` (`crewai`, `fastmcp`, `fastapi`/`uvicorn`, `sqlalchemy`, `bcrypt`/`pyjwt` en `pyproject.toml`).
- Entrada real: `main.py` — `--orquestador`, `--campana`, `--rama <nombre> --inputs '{}'`, `--micelio`, `--clasificar`, `--arboles` (ver `README.md` para flags exactos).
- Paneles (FastAPI/Uvicorn): `:8000` árbol (`web_server.py`), `:8001` comandante (`comandante_web.py`), `:8002` conservante (`conservante_web.py`). Conservante exige `CONSERVANTE_WEB_TOKEN` (sin él responde 503); Comandante lo exige solo si está definido. `AUTO_OPEN_BROWSER=true` abre el panel al arrancar (solo localhost).
- Arranque en frío tarda 20-60s (import `crewai`/`fastmcp`): no declares caído un servicio sin esperar.

## 🤖 Modelos y proveedores

- LLM en `core/llm_router.py`: rutina = Ollama local (`LOCAL_LLM_MODEL`, default `qwen3:4b`, `LOCAL_LLM_BASE_URL` default `http://localhost:11434/v1`); estrategia = OpenRouter con fallbacks y caída a Ollama. El health check valida que el modelo **exista** en `/api/tags` — un `✅ conectado` sin modelo es bug, no estado.
- Búsqueda en `primer_contacto/servidor_mcp.py`: `DATA_PROVIDER` (default `mock`, nunca asumas keys); cadena `searxng → serper/serpapi → mock` (`SEARXNG_URL`, default `127.0.0.1:8080`, vacío = off). Funciones `*maps*`/`google_maps` son de Google Maps: no tocarlas sin orden que las nombre.

## 🔒 Secretos y autoridad

- Gitignored y jamás commiteables: `.env`, `semillero/heredado.env`, `*.exe`, `*.db`. Pre-commit `scripts/check_secrets.py` bloquea secretos — todo commit con código sensible pasa su grep antes del push.
- Micelio nunca modifica un árbol sin el Conservante (`core/mision.py`); los gates críticos (`db.Aprobacion`, `/aprobaciones`) solo los aprueba la Directora Humana.

## 🪟 Gotchas de Windows PowerShell 5.1

- No existe `head`/`&&`: usa `Select-Object -First`, y `; if ($?) { }` para encadenar. Los arrays se envuelven con `@()` (`+=` sobre objetos revienta).
- Puertos en uso: `Get-NetTCPConnection -LocalPort <p> -State Listen` (más fiable que filtrar `CommandLine`).
- Los scripts `.ps1` que corren en nodos fijan UTF-8 explícito; si ves mojibake, es encoding, no corrupción.

## ☠️ `Levantar Colmena.bat` / `levantar.ps1` hace `fetch + reset --hard`

Borra todo lo no commiteado. **Regla: commit + push antes de cualquier Levantar.** Ya costó 2 ciclos una vez.

## 🤝 Trabajo multi-agente (`.agents/`)

El flujo TPM ↔ Dev Jr vive en `.agents/Gate/` (`input.md` → `output.md`) con Kanban en `.agents/DB_TO-DO-LIST/` (`Pending → onProces → Audit → Finished-db/`). Lee los `Context.md` y `protocol/` vigentes antes de operar — nunca asumas el protocolo de memoria. Topología e inventario vivos: `main.py --arboles` y tabla Supabase `arboles_remotos` (no hardcodees IPs de nodos, cambian).

## 📎 Regla 2026-09-09 — tareas directas del Dev Principal

Toda orden directa del Dev Principal fuera de ciclo se reporta igual en `.agents/Gate/output.md` como anexo fechado (fecha, orden, cambios/commits, estado), sin borrar la entrega pendiente de revisión.
