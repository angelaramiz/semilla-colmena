# 🧭 Plan Dirección Colmena — pipeline, equipo completo, plano de control y visión VM

**Fecha**: 2026-10-24 · **Orden de**: Dev Principal (Arangel)
**Estado**: Diseño aprobado-pendiente de implementación (no reemplaza a la doc matriz; la complementa)

---

## 1. Dos modos de ejecución

### 1.1 Modo PIPELINE (campaña completa)

Orquestación inteligente, coherente y dinámica según el objetivo del cliente.

```
objetivo cliente ──▶ ORQUESTADOR (plan v1) ──▶ [fases en DAG]
                        ▲                          │
                        └── replan tras cada fase ─┘
```

- **Entidad `campana`** con manifiesto persistido: `campanas/<id>/manifiesto.json`
  (objetivo, cliente, KPIs, fases[].estado, artefactos, gates exigidos, presupuesto de
  tokens/tiempo, deadline). Sobrevive reboots («reanudar», no «recomenzar»).
- **DAG de fases estándar**: `investigacion → planeación → [contenido ∥ redes] → analítica`
  (+ atencion/auditoría según objetivo). Fases sin dependencia entre sí corren **en
  paralelo** y pueden vivir en **distintos árboles obreros** (despachos).
- **Contratos por fase**: entrada validada por schema (inputs heredados de la fase
  anterior), salida = entregable + checklist de calidad + gate si publica.
- **Replan loop acotado**: tras cada fase, `evaluar_fase` decide `continuar / ajustar /
  repetir / escalar a Directora`; máximo N replans por fase (evita bucles de tokens).
- **Gates**: las fases que publican/envían se congelan en `db.Aprobacion` hasta la
  Directora (infra ya construida); Telegram recibe el ping del gate.
- **Herramientas MCP nuevas** (capa encima de `delegar_rama`):
  `campana_crear`, `campana_iniciar`, `campana_estado`, `campana_paso`, `campana_replanar`.
- **Modo de cómputo**: rutina local (Ollama) para investigación/extracción; estrategia
  (OpenRouter/OpenBot) para plan y redacción; encabezado por `core/llm_router.py`.

### 1.2 Modo INDIVIDUAL (un solo paso)

Ejecutar solo una rama con contexto suficiente: `--paso investigacion|planeacion|
contenido|redes|analitica {--campana <id> --fase <n>}`.

- Si corre **dentro de** una campaña: guarda su artefacto en `campanas/<id>/` y el
  estado del manifiesto se actualiza (se puede luego «coser» a la campaña).
- Si corre **fuera** de campaña: misma calidad (verificador + gates) pero entrega por
  retorno/cola sin manifiesto.
- La auditoría CLI existente (`main.py --cli -n ... -c ...` vía `lanzar_auditoria_obrero`)
  es el precendente: patrón idéntico, formalizado como `--paso auditoria`.

---

## 2. Qué falta para un EQUIPO COMPLETO blindado de calidad

**Inventario honesto** (estado actual del código):

| Capacidad | ¿Ya está? |
|---|---|
| Agentes por rama + delegación | ✅ (`delegar_rama`, 7 ramas) |
| Gates de aprobación con roles | ✅ (Comandante despacha; Conservante observa) |
| Ruteo LLM con fallbacks | ✅ (`llm_router`) |
| Cola persistente + reintentos | ✅ (`ceo_bot`) |
| Supervisor/tareas SYSTEM/guardia engine | ✅ (Fase A/B + `docker_guardia.ps1`) |
| Paneles de mando 8000/8001/8002 | ✅ |
| **Verificador independiente de calidad** | ❌ **falta** |
| **Evals/regresión por rama** | ❌ **falta** (codegraph: «no covering tests») |
| Memoria de cliente persistente (voz de marca, historial, aprendizajes) | ◑ parcial (OpenBot threads + `agent_memory/`) |
| **Planificador de publicaciones (calendario con ejecutor)** | ❌ falta |
| Observabilidad de costos/tokens por fase + alertas activas | ❌ falta |
| Kit de marca por cliente (fuente única para todas las ramas) | ❌ falta |
| Loop analítica→planeación (campaña siguiente aprende de la anterior) | ❌ falta |

**El blindaje (prioridad 1 del equipo)**: para cada entregable, un **verificador
independiente** (equivalente a code-reviewer pero de contenidos):
1. Checks mecánicos primero (regex/esquemas): longitudes, fuentes citadas, formatos,
   dimensiones de imagen, límites de canal — barato y determinista.
2. Crítica LLM con rúbrica (otro modelo que el que redactó): coherencia con la voz de
   marca, veracidad factual (muestreo), tono, componentWillMount de canales.
3. Bucle de revisión acotado (máx 2 iteraciones) → si sigue mal, se escala a Directora
   con el diagnóstico, no se publica jamás de fondo sin visto bueno.

**Plan de fechas de cierre (número faltante = día de implementación, no prioridad)**:
fase del equipo: P1 verificador+evals → P2 memoria cliente → P3 scheduler → P4
observabilidad/alertas → P5 kit marca → P6 loop analítica.

---

## 3. Plano de control de árboles: más completo, robusto y rápido

**Hoy**: acceso SSH/scp por operación (`comandante_mcp.py`) — cada acción = handshake
SSH + script remoto con quoting frágil (PS 5.1) + procesos atados a sesiones (lo que
acabamos de vivir con el engine). Paneles leen archivos locales. Estado del árbol =
sondeo bajo demanda.

**Diseño: "OJO-COLMENA" (agente de nodo residente en cada obrero)**
_One daemon pequeño por árbol, tarea SYSTEM (junto a la ya existente), hardening por token_

- **API HTTP por tailnet** (NIC tailnet + firewall tailnet-only, patrón ya usado):
  token obligatorio `OJO_TOKEN` en HKLM (jamás en repo/log).
  - `GET /salud` → informe vivo: hostname, git hash/branch, disco, RAM, contenedores,
    tareas SYSTEM, tail de logs, colas pendientes (POST cada 30s como *heartbeat* al
    principal → tabla `arboles_remotos` siempre fresca, sin sondeos).
  - `POST /deploy` → `git fetch + reset --hard origin/main + uv sync` con **lock,
    preflight (disco/logs limpios), progreso streaming y postflight de salud** — el
    reset ya está regulado por las normas del repo (commit antes de Levantar).
  - `POST /exec` → lista blanca de comandos idempotentes (reiniciar tarea X, arrancar
    stack, sincronizar semilla); todo lo irreversible pasa por gate del Conservante.
  - `GET /logs?tail=N`, `GET /shot` → **captura de pantalla** (ver §4),
    `GET/POST /archivos` → subir/bajar artefactos sin scp.
  - `POST /semilla` → registrar/actualizar otro obrero (JM micelio hacia nodos).
- **Inventario + eventos** en el principal: cada gate, deploy, caída o récord de
  trabajo queda en un event-log consultable por panel (8001/8002) — no archivos
  dispersos.
- **Semillas**: declarar una semilla nueva = HTTP `POST /semilla` + plantillas de
  `.env.example`; el node auto-registra su identidad (`ARBOL_ID`, rol, Abilities).
- **Fallback**: SSH/comandante MCP se conserva para cuando el ojo no responda
  (defensa en profundidad; nunca se elimina).
- **Rapidez**: operación típica pasa de ~3-8s (handshake SSH) a <100ms (HTTP local por
  tailnet); el heartbeat elimina el «esperar y ver» de los diagnósticos en cadena.

**Ruta de implementación**: ojo.py (~200 líneas, stdlib/uvicorn) + tarea SYSTEM +
firewall por token; wiring en `comandante_web` (pestaña Árboles lee heartbeats) y en
`conservante_web` (gates de /exec y /deploy).

---

## 4. Capturas de yazminlap "como una VM propia"

Fases, de más barata a más completa:

1. **Fase A (ya viable, hoy)** — *Ojo de sesión*: tarea o Run key de ritoy (sesión
   interactiva) que cada N segundos guarda `C:\srv\colmena\ovni\pantalla.png` solo si
   cambió (hash del frame). Lectura por SSH/scp (mismo patrón probado) o vía
   `/shot` del ojo-colmena cuando exista.
   - Requisito: **sesión desbloqueada** → activar **autologon de ritoy** (portallow:
     bot de colmena no guarda secretos; el .hola autologon es de la laptop de Zoop).
2. **Fase B (robusta)** — endpoint `GET /shot` del ojo-colmena: el principal (yo/
   comandante) pide captura a demanda y读写 múltiple (alt + ventana activa, pestaña
   escolta). Sin autologon fallaría (desktop bloqueado = PNG negro), por lo que se
   combina con 1.
3. **Fase C (acción, no solo visión)** — el agente de computer-use de OpenBot
   (`openbot-computer-orquestador`) apuntando a Zoop por tailnet: click/escribir/
   verificar visualmente — la VM real: *yo la veo e interactúo*.

Contraindicaciones/limite: toda la vía de視覚 se queda dentro del tailnet (Cluster de
firewall ya aplica); las capturas se borran de `ovni/` con retención (anti-asado).

---

## 5. Objetivos de alcanzar (resumen de la orden)

| # | Objetivo | Ruta |
|---|---|---|
| 1 | Pipeline de campañas con orquestación dinámica | §1.1 — entidad campana + DAG + replan acotado |
| 2 | Modo individual por paso | §1.2 — `--paso` formalizado |
| 3 | Equipo completo + blindaje de calidad | §2 — verificador + evals + memoria + scheduler |
| 4 | Acceso robusto y rápido a obreros/semillas | §3 — ojo-colmena + heartbeat + inventario |
| 5 | Capturas de Zoop como VM | §4 — ojo de sesión → /shot → computer-use |
