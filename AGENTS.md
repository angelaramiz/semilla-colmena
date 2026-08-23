# AGENTS.md — Reglas para agentes IA en este proyecto

## 🔍 Búsqueda de código: usar CodeGraph primero

Este proyecto está indexado con **CodeGraph** (`.codegraph/` + servidor MCP `codegraph`).

**Regla obligatoria:** antes de hacer búsquedas genéricas (`grep`/`find`/glob) o de leer
archivos a ciegas para entender la estructura, usa CodeGraph:

- Herramienta MCP: `codegraph_explore` (consulta por símbolo, archivo o pregunta; devuelve
  fuente verbatim + blast radius).
- CLI: `codegraph explore "pregunta o símbolos"` desde la raíz del repo.

CodeGraph devuelve la fuente actual en disco, las rutas con número de línea y el
**blast radius** (qué depende de qué) — ahorra rondas de búsqueda y lectura.

Si el índice se desactualiza tras editar, el watcher lo re-indexa solo (~1s); para cambios
masivos se puede pedir `codegraph sync`.

---

## 🎯 Objetivo principal (misión de la colmena — `core/mision.py`)

Cada árbol y su micelio cumplen una misión permanente (aunque la máquina se reinicie):
1. **Siempre conectado y operando.**
2. **Siempre en buena salud**: si hay errores, el micelio hace análisis de estado y solicita
   al árbol **CONSERVANTE** permiso para auto-ejecutar mantenimiento.
3. **Sin modificación sin autorización**: el micelio NO altera su árbol sin autorización
   del CONSERVANTE (jerarquía más alta). Sistema de auth para quien opera los árboles.
4. **Siempre en la red privada** y en comunicación con los árboles.

## 🏗️ Arquitectura de la colmena (resumen para agentes)

Sistema multi-agente "mente colmena" (CrewAI + FastMCP + Ollama/OpenRouter):

- **Semilla**: `core/` (enrutador de modelos, clasificador, registro de ramas, manifiesto, permisos).
- **Tronco**: `orquestador/` (agente orquestador + pipeline de campaña).
- **Ramas (obreros)**: `contenido/`, `redes/`, `analitica/`, `investigacion/`, `atencion_cliente/`, `planeacion/`, `auditoria/` (primer_contacto).
- **Micelio (mantenimiento)**: `micelio/`.
- **Comunicación raíz→árboles**: `comunicacion/` (SSH/Tailscale).
- **Paneles web**: `web_server.py` (obrero), `comandante_web.py`, `conservante_web.py` (dev).
- **Despliegue**: `sembrar.sh`, `Dockerfile`, `docker-compose.yml`, `core/manifiesto.py`.

Modelos: **Ollama local** (rutina, `qwen3:27b`) + **OpenRouter** (estrategia, `z-ai/glm-5.2:free` con fallbacks y fallback a Ollama). Enrutado en `core/llm_router.py`.

Gates de aprobación humana: `db.Aprobacion` + endpoints `/aprobaciones` (solo la Directora).

---

## ⚙️ Comandos útiles

```bash
uv run python main.py --orquestador "instrucción"   # Tronco
uv run python main.py --campana "objetivo"          # pipeline de campaña
uv run python main.py --rama <nombre> --inputs '{}' # rama individual
uv run python main.py --micelio                     # mantenimiento (salud/reparar)
uv run python main.py --clasificar "texto"          # clasificación de tarea
uv run python main.py --arboles                     # inventario del comandante
```