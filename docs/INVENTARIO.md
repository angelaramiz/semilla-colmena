# INVENTARIO — Deps, herramientas y accesos por rol

> Fecha: 2026-10-15 · Fuente: código+`.env.example` (agencia) y `.env` real (OpenBot, sin valores).
> Secretos: solo NOMBRE de la variable, nunca su valor. Este doc es el mapa para endurecer (persistencia/seguridad).

## 1. Ramas (departamentos CrewAI) — agencia

| Rama | Rol | Inputs | Herramientas MCP | Keys/accesos | Riesgo |
|---|---|---|---|---|---|
| `planeacion` | Estratega | objetivo, dossier_json, ciudad, presupuesto | definir_kpis, armar_calendario, definir_publico, asignar_presupuesto, guardar_plan | — | sin acceso externo |
| `contenido` | Copywriter | tema, marca, audiencia, plataformas, tono | generar_brief, adaptar_tono, reutilizar_contenido, revisar_ortografia, guardar_borrador | — | sin acceso externo |
| `redes` | Community Mgr | marca, audiencia, plataformas, periodo_dias, objetivo | consultar_calendario, validar_hashtags, detectar_tendencias, programar_post | — | sin acceso externo |
| `analitica` | Analista KPI | objetivo, periodo, metricas_json | extraer_metricas, calcular_roi, comparar_periodos, detectar_anomalias | — | sin acceso externo |
| `investigacion` | Analista Mercado | tema, ciudad, categoria | buscar_mercado, analizar_competencia, detectar_tendencias | — | solo lectura |
| `atencion_cliente` | Soporte | mensaje, cliente | clasificar_mensaje, buscar_base_conocimiento, proponer_respuesta, escalar_queja | — | escala quejas (gate) |
| `auditoria` (primer_contacto) | Auditor Huella | negocio, ciudad, recursos_extra, modelo_negocio, contexto_empresa | buscar_negocio, verificar_redes, buscar_competidores, buscar_presencia_web | `DATA_PROVIDER` (mock), `SERPAPI_KEY`, `GOOGLE_API_KEY`, `SERPER_API_KEY`, `SEARXNG_URL` (default 127.0.0.1:8080, **hoy apagado**), `MCP_TOOL_TIMEOUT` | única con APIs de datos externos |
| `orquestador` (Tronco) | Director Ops | instruccion | clasificar, delegar_rama, ejecutar_campana, solicitar/consultar aprobación, guardar_borrador | mismo LLM router | gasta tokens |

**LLM común a todas** (`core/llm_router.py`): `LOCAL_LLM_BASE_URL/MODEL` (Ollama `qwen3:4b`) para rutina; `OPENROUTER_API_KEY/BASE_URL/MODEL/FALLBACK_MODELS/TEMPERATURE/MAX_TOKENS` para estrategia (hoy `gemma-4-26b:free` + rotación 429/404 + fallback Ollama).
**Memoria común** (`scripts/memoria.py`): `LOCAL_LLM_BASE_URL`, `MEMORIA_LLM_MODEL` (qwen2.5:1.5b), `QDRANT_HOST/PORT` (Docker :6333). Todo local.

## 2. Bots (OpenBot) — cara operativa

| Bot | Endpoint | Depende de | Accesos |
|---|---|---|---|
| `orquestador-colmena` | `:4210/ag-ui` | puente → `main.py --orquestador` (venv agencia) | memoria + todo lo del Tronco |
| 7 ramas `rama-*` | `:4210/ag-ui/rama/<nombre>` | puente → `main.py --rama ...` | lo de su rama |
| `asistente-marketing`, `conocimiento-agencia` | built-in | modelo del tenant | chat puro |
| `general-assistant` (sistema) | endpoint built-in | `OPENAI_API_KEY` + `OPENAI_BASE_URL` (OrcaRouter) | chat puro |

**Modelo del tenant OpenBot**: `BOT_MODEL`/`AGENT_BOT_MODEL` = `z-ai/glm-5.3-flash-free` vía `api.orcarouter.ai`; en `examples/agencia/model.yaml:default_model`.

## 3. Servicios e infra (host)

| Servicio | Puerto | Persistencia | Auth |
|---|---|---|---|
| OpenBot app | 3010 | proceso bun (no persistente) | single-user (TODO: OAuth) |
| OpenBot server API | 3001 | proceso bun + Postgres `openbot-postgres` (volúmenes Docker) | licencia + Intelligence key |
| OpenBot computers | 4200/4201/4100/54032 | perfiles en volúmenes (`agent-profiles`) | tokens internos rotados |
| Puente AG-UI | 4210 | proceso manual (TODO: tarea programada) | `PUENTE_TOKEN` env-gated (apagado en local) |
| Qdrant (memoria) | 6333 | volumen Docker | **sin auth — solo localhost, exponer con auth** |
| Postgres OpenBot | 5433→5432 | volumen Docker | password en `.env` (nombrar: `DATABASE_URL`) |
| Ollama | 11434 | modelos en `~/.ollama` | open localhost |
| SearXNG | 8080 | — | **no corre hoy** (`SEARXNG_URL` para auditoría) |

**Credenciales (solo nombres):** agencia `.env` — `OPENROUTER_API_KEY`, `SERPAPI_KEY`/`GOOGLE_API_KEY`/`SERPER_API_KEY` (vacías hoy), `TAILSCALE_TOKEN`, `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, `DIRECTORA_PASSWORD`, `COMANDANTE_WEB_TOKEN`, `CONSERVANTE_WEB_TOKEN`, `SUPABASE_URL/PUBLISHABLE_KEY`, `DATABASE_URL`. OpenBot `.env` — `OPENAI_API_KEY` (OrcaRouter), `COPILOTKIT_LICENSE_TOKEN`, `CPK_INTELLIGENCE_API_KEY`/`INTELLIGENCE_API_KEY`, `MANAGED_AGENT_TOKEN`, `KEY_ENCRYPTION_KEY` (¡aún la de ejemplo!), `WORKER_SHARED_SECRET`, `SUPERVISOR_TOKEN`, `COMPUTER_TOKEN`, `AGENT_TOOL_TOKEN`.

**Tailscale**: `laptop-p3tdnov6.tail99835a.ts.net` → :3010 (serve activo) + VM tombada `cmd_vm_01` (`100.74.85.20`, útiles `:8000/:8001/:11434`), ruti `100.114.102.85` (offline), llaves SSH `~/.ssh/id_colmena*`, `id_rsa`, `id_ed25519`.

## 4. Matriz rol → acceso (para endurecer)

| Rol | Necesita | NO debería |
|---|---|---|
| Directora (tú) | aprobaciones, todos los canales, admin/audit | — |
| Mercadóloga (ruti) | canales creacion/inteligencia/atencion, chats con bots de su área | admin, credenciales, API keys, push git |
| Bots de rama | memoria lecture/write de su usuario | emitir (publicar), gastar por encima de presupuesto |
| Orquestador | delegar ramas, gates | ejecutar acción crítica final |

## 5. Vacíos que este inventario destapa

1. Puente y OpenBot sin persistencia tras reinicio del host (tarea programada / `bash scripts/stop.sh` documentado).
2. Auth: single-user + puente sin token (ok localhost; **obligatorio antes de exponer por funnel/dominio público**).
3. `KEY_ENCRYPTION_KEY` de ejemplo — regenerar antes de guardar credenciales reales en OpenBot.
4. Proveedores de datos de auditoría vacíos: solo mock (decisión: o se consigue key o queda mock).
5. SearXNG no corre en host (solo en la VM tombada).
6. Backups inexistentes (Restic pendiente, plan Fase 5).
7. Cero tests sobre puente/memoria/tenant (codegraph: "no covering tests" en todo lo nuevo).
