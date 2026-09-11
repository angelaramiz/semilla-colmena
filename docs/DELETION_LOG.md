# Code Deletion Log

## [2026-09-11] Refactor Session (dead-code cleanup, branch `refactor/dead-code-cleanup`)

Herramientas: `uvx ruff check --select F401,F841,F821,F811` + script AST propio
(`.venv` excluido). 20 hallazgos F → 0 tras la limpieza. `python -m compileall`
OK + `scripts/check_secrets.py` OK. Sin suite de tests automatizada en el repo
(solo `test_provider.py` manual); verificación = compilación + re-check ruff.

### Unused Imports Removed (SAFE — verificado con grep, sin referencias)
- `agente.py` — `StdioServerParameters` del import top-level (solo se usaba el
  re-import local dentro de `_run_mcp_server`). Queda `from mcp import ClientSession`.
- `primer_contacto/agente.py` — mismo caso que `agente.py`.
- `analitica/agente.py`, `atencion_cliente/agente.py`, `investigacion/agente.py`,
  `orquestador/agente.py` — `RUTINA` de `from core.llm_router import ...`
  (`get_llm` + `ESTRATEGIA` sí se usan; `RUTINA` sin referencias).
  Nota: `contenido/planeacion/redes` ya estaban limpios (sin `RUTINA`).
- `gui.py` — `tkinter.messagebox` (importado, jamás usado) y `sys` (sin `sys.` en el archivo).
- `gui_backup.py` — `datetime.datetime` (sin referencias; `messagebox`/`filedialog` SÍ se usan, se conservan).
- `micelio/servidor_mcp.py` — `resolver_aprobacion` de `from db import ...`
  (importado, jamás llamado en ese módulo; se conservan `crear_aprobacion`, `listar_aprobaciones`).

### Unused Variables Removed (SAFE)
- `gui.py::agregar_log` — dict local `colores` muerto (los colores se aplican vía
  `tag_config` literal abajo; el dict nunca se leía). Eliminado, comportamiento idéntico.

### Bug Fixes incluidos (detectados por F811/F821, no solo limpieza)
- `orquestador/servidor_mcp.py::resolver_aprobacion` — **recursión infinita real**:
  el `@mcp.tool()` se llamaba a sí mismo en vez de a `db.resolver_aprobacion`
  (F811: redefinición del nombre importado). Fix: import aliased
  `resolver_aprobacion as _resolver_aprobacion_db` + llamada al alias.
- `gui.py` / `gui_backup.py` (`except ... as e` + `lambda: ... {e}`) — F821 + bug de
  late-binding (en Py3 `e` se borra al salir del `except` → `NameError` en runtime
  cuando el callback `after(0, ...)` se ejecuta). Fix: `lambda e=e: ...`.
- `web_server.py` (`except Exception as e` sin uso de `e`) — F841. Fix: `except Exception:`.

### Duplicate Code — evaluado, NO consolidado (decisión conservadora)
- `gui.py` (26 KB) vs `gui_backup.py` (21 KB, hashes distintos) — backup huérfano:
  sin referencias en código/bats/ps1/CI. NO eliminado: es el único respaldo de la GUI
  y no hay confirmación del equipo. Recomendación: archivar fuera del repo o borrar
  con aprobación explícita.
- `*/agente.py` (`cargar_prompt`, `setup_crew`, `extract_crew_result`, `call_tool`,
  `_start_loop` repetidos en ~10 ramas) — duplicación intencional por diseño
  (cada rama = obrero autónomo con su `servidor_mcp.py` propio); extraer base común
  cambiaría el modelo de despliegue por árbol. NO consolidado.
- `*/servidor_mcp.py::_log` (9 copias) — trivial, mismo caso que arriba. NO tocado.

### Remaining (manual review needed — NO tocados por riesgo)
- Funciones top-level con ≤2 referencias textuales (mayoría falsos positivos):
  rutas FastAPI (`@app.get/post` en `web_server.py`, `comandante_web.py`,
  `conservante_web.py`), tools CrewAI (`@tool`) y MCP (`@mcp.tool()`) — invocación
  dinámica por decorador, invisible al conteo textual. NO eliminar sin traza runtime.
- `test_provider.py` — script manual de prueba (`DATA_PROVIDER=mock`); sin referencias
  pero útil para diagnóstico. Conservar.
- Resto del reporte ruff completo (445 hallazgos: BLE001, S110, B008, SIM117, etc.) —
  estilo/seguridad, fuera del alcance de esta pasada SAFE (solo familia F).

### Impact
- Files deleted: 0 (solo ediciones quirúrgicas; `gui_backup.py` pendiente de decisión)
- Imports muertos eliminados: 11
- Variables muertas eliminadas: 1
- Bugs reales corregidos: 3 (recursión + 2× lambda-`e` + except sin var)
- Lines of code removed (neto): ~14
- `ruff --select F401,F841,F821,F811`: 20 errores → 0
- `compileall` (53 archivos propios): OK · `check_secrets.py`: OK

### Testing
- `uvx ruff check . --exclude .venv --select F401,F841,F821,F811` → All checks passed
- `python -m compileall` sobre todos los módulos propios → OK
- `python scripts/check_secrets.py` → OK (0 archivos)
- Sin suite pytest en el repo; smoke manual pendiente sugerido:
  `python -c "import ast; ..."` ya hecho + arranque GUI/`uvicorn` en frío
  (20–60 s por `crewai`/`fastmcp`, según AGENTS.md)
- Rama: `refactor/dead-code-cleanup` (trabajo SIN commitear; commitear + push
  ANTES de cualquier `Levantar Colmena.bat`, que hace `fetch + reset --hard`)

## [2026-09-11] Refactor Session (continuación — vulture + duplicados)

Herramientas: `vulture --min-confidence 60` (solo código propio, `.venv`
excluido) + `ruff --select F401,F841,F821,F811` + grep de referencias +
`git log`. Hallazgo: la mayoría de hits de vulture son falsos positivos
(handlers FastAPI `@app.get/post`, tools MCP `@mcp.tool()`, columnas SQLAlchemy
y modelos Pydantic — invocación dinámica/declarativa invisible a vulture).

### Unused Functions Removed (SAFE — 0 referencias en código Python)
- `core/llm_router.py::get_strategy_llms()` (14 líneas) — 0 callers en `.py`
  (verificado por auditoría Gate R-1). Superseded por `enable_rotation()`
  (rotación 429 + fallback Ollama in-place); ningún caller tras el refactor
  de rotación. Eliminada.
  ⚠️ Corrección a la nota original: SÍ había un caller fuera de Python —
  `sembrar.sh:337` importaba `get_strategy_llms` en el health-check de
  modelos (habría roto el sembrado con `ImportError`). Fix acompañante R-1:
  línea 337 simplificada a `get_llm(RUTINA)` + `get_llm(ESTRATEGIA)`
  (rutina + estrategia siguen verificadas; la "cadena" la cubre
  `enable_rotation()` in-place). Verificación: `import core.llm_router` OK,
  `hasattr(get_strategy_llms)` False, `bash -n sembrar.sh` OK.

### Vulture hits verificados como FALSOS POSITIVOS (NO tocados)
- `db.py::buscar_arbol/marcar_estado/exportar_inventario/importar_inventario` —
  usados por `comunicacion/comandante_mcp.py` (10+ callers). NO eliminar.
- `web_server.py`, `comandante_web.py`, `conservante_web.py` handlers —
  rutas FastAPI por decorador. NO eliminar.
- `orquestador/servidor_mcp.py`, `primer_contacto/servidor_mcp.py`,
  `servidor_mcp.py` funciones — tools MCP por decorador. NO eliminar.
- `auth.py::crear_usuario` — 0 callers pero API pública de auth (helper para
  futuros registros/admin). Conservar por diseño.
- `core/permisos.py::ROLES_ARBOL/MICELIO_ESTRUCTURA/rol_descripcion` y
  `core/registro_ramas.py::RAMAS_DISPONIBLES` — 0 referencias pero constantes
  de dominio (RBAC/contrato de ramas), 1 línea c/u, costo 0. Conservar.
  (`rol_tiene_micelio`/`es_conservante` SÍ se usan en `micelio/servidor_mcp.py`;
  `REGISTRO_RAMAS` SÍ se usa en `main.py`, `orquestador/campana.py`,
  `orquestador/servidor_mcp.py`.)

### Duplicate Code — evaluado, NO consolidado (decisión conservadora)
- `servidor_mcp.py` raíz (454 líneas) vs `primer_contacto/servidor_mcp.py`
  (520 líneas) — DIVERGIERON, no son copias: `primer_contacto/` trae bloque
  SearXNG (`_buscar_red_con_searxng`, `_buscar_presencia_con_searxng`, cadena
  `searxng → serper/serpapi → mock`); la raíz no lo tiene. Ambos VIVOS:
  raíz usada por `agente.py:91` (stdio) + `test_provider.py:8`;
  `primer_contacto/` usada por `primer_contacto/agente.py:94-95`. NO fusionar
  sin suite que valide providers (sin keys no se puede probar SearXNG/Serper).
  Recomendación: portar bloque SearXNG a la raíz o eliminar la raíz si
  `agente.py` legacy ya no se usa — con aprobación explícita.
- `requirements.txt` — autogenerado por `uv pip compile`, en sync con
  `pyproject.toml`. Sin dependencias huérfanas que remover.
- Resto igual que la pasada anterior (`gui_backup.py`, `*/agente.py`,
  `*/servidor_mcp.py::_log`).

### Impact (esta pasada)
- Files deleted: 0
- Functions muertas eliminadas: 1 (`get_strategy_llms`, ~14 líneas)
- Lines of code removed (neto): ~14
- `ruff --exclude .venv --select F401,F841,F821,F811`: All checks passed
- `compileall` (módulos propios): OK · `check_secrets.py`: OK (0 archivos)

### Testing (esta pasada)
- `import core.llm_router` + `import servidor_mcp` → OK
- `ruff` familia F → All checks passed · `compileall` → OK · `check_secrets` → OK
- `test_provider.py` no ejecutable en esta terminal (falla pre-existente:
  emoji 🔍 + `cp1252` en PowerShell 5.1, línea 10, antes de tocar red;
  gotcha Windows documentado en AGENTS.md — usar `chcp 65001` o
  `$env:PYTHONUTF8=1` para correrlo). No relacionado con este cambio
  (el cambio toca `core/llm_router`, el script importa `servidor_mcp`).
