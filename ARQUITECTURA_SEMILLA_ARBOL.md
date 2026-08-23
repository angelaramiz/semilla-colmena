# 🌱 Agencia de Marketing Autónoma — Arquitectura "Semilla-Árbol"

**Directora Humana**: [Tu Nombre]
**Fecha**: 23 de agosto de 2026
**Estado**: Especificación técnica (v2.0)
**Metáfora rectora**: Cada despliegue es un **árbol** que crece de una **semilla** común. Una semilla crea muchos árboles (un servidor/cliente por árbol), todos idénticos en estructura pero con datos y credenciales independientes.

---

## 0. Resumen Ejecutivo

La agencia es un **sistema multi-agente** donde:

- **La Semilla** = base reutilizable (manifiesto + repo Git + reglas + conectores de modelos).
- **El Tronco** = Agente Orquestador que recibe instrucciones de la Directora y delega.
- **Las Ramas** = agentes especializados con herramientas y límites de autonomía.
- **Los Frutos** = entregables; algunos automáticos, otros con **gate de aprobación humana**.
- **La Replicación** = poda/clonación para levantar instancias aisladas por cliente/sucursal.

La base técnica ya existe en el repo `agen_mrk` (CrewAI + FastMCP + Ollama + OpenRouter).
Esta especificación **formaliza y estandariza** ese patrón como una plantilla clonable.

> ⚠️ **Nota Trinity**: se modela como orquestador de contenedores con manifiesto declarativo,
> volumen compartido y RBAC. Si tu Trinity usa otro esquema de manifiesto, ajusta solo la
> sección de clonación; el resto es agnóstico de la plataforma.

---

## 1. 🌰 La Semilla (Base)

Es el **mínimo replicable**: todo lo que un árbol nuevo necesita para nacer y operar, sin
depender de otro árbol.

### 1.1 Repositorio Git base

```
semilla-agen/
├── core/
│   ├── __init__.py
│   └── llm_router.py          # get_llm(nivel) + get_strategy_llms()  [YA EXISTE]
├── orquestador/               # El Tronco
│   ├── agente.py
│   ├── servidor_mcp.py
│   └── system_prompts/orquestador.md
├── ramas/                     # Las Ramas (agentes especializados)
│   ├── contenido/
│   ├── redes_sociales/
│   ├── analitica/
│   ├── investigacion/
│   ├── atencion_cliente/
│   └── auditoria/             # = primer_contacto/ (existente, se reutiliza)
├── shared/                    # Volumen compartido (borradores, memoria, aprobaciones)
├── web/                       # web_server.py + auth.py + db.py (FastAPI + JWT)
├── .env.example               # Plantilla de variables (SIN secretos reales)
├── .gitignore                 # SIEMPRE excluye .env
├── manifiesto.yaml            # Manifiesto Trinity (deploy)
└── README.md
```

### 1.2 Reglas fundamentales (no negociables)

1. **Permisos (RBAC)**: solo la Directora Humana tiene permiso `aprobar_acciones_criticas`.
   Ningún agente puede publicar o enviar sin un gate de aprobación (§4).
2. **Variables de entorno**: toda configuración vive en `.env`, nunca en código.
   `.env` está en `.gitignore` (lección ya aplicada en este repo: `.env` estaba trackeado;
   se corrigió con `git rm --cached .env`).
3. **Conexión a modelos**:
   - **Ollama local** → tareas **rutinarias** (`qwen3:27b`): scraping, extracción,
     resúmenes, clasificación, formateo JSON. Gratis y privado.
   - **OpenRouter cloud** → razonamiento **avanzado/estratégico** (`z-ai/glm-5.2:free` con
     fallbacks `google/gemma-4-26b-a4b-it:free`, `nvidia/nemotron-3.5-lightning:free`).
   - Enrutado por `core/llm_router.py:get_llm(nivel)`.

### 1.3 `.env.example` (plantilla para cada árbol)

```env
# === Ollama (rutina) ===
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=qwen3:27b
USE_LOCAL_LLM=true

# === OpenRouter (estrategia/razonamiento) ===
OPENROUTER_API_KEY=sk-or-...                    # ÚNICA por árbol (independiente)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=z-ai/glm-5.2:free
OPENROUTER_FALLBACK_MODELS=google/gemma-4-26b-a4b-it:free,nvidia/nemotron-3.5-lightning:free
OPENROUTER_TEMPERATURE=0.7
OPENROUTER_MAX_TOKENS=4096

# === Datos (proveedores) ===
SERPAPI_KEY=
GOOGLE_API_KEY=
DATA_PROVIDER=serper

# === Aprobación humana ===
APROBACION_MODO=manual          # manual SIEMPRE en producción; auto solo para tests

# === Identidad del árbol ===
ARBOL_ID=cliente_01              # Identificador único de esta instancia
ARBOL_NOMBRE="Cliente X"
```

---

## 2. 🌳 El Tronco (Orquestación)

Es el **Agente Orquestador**, único punto de entrada de la Directora Humana.

### 2.1 Responsabilidades

1. **Recibir instrucciones** de la Directora (mensaje / API / cola).
2. **Evaluar complejidad**: clasifica la tarea en rutina, media o estratégica
   (decide qué modelo usar y si necesita gate de aprobación).
3. **Delegar** a la(s) rama(s) apropiada(s) con un plan de trabajo.
4. **Consolidar** resultados y redactar el entregable final.
5. **Solicitar aprobación** cuando la acción es crítica (§4).

### 2.2 Firmas de tarea (clasificación de complejidad)

```yaml
clasificacion:
  rutina:      { nivel: "rutina",     modelo: ollama,     aprobacion: NO  }
  media:       { nivel: "estrategia", modelo: openrouter, aprobacion: NO  }
  critica:     { nivel: "estrategia", modelo: openrouter, aprobacion: SI  }
```

- **rutina**: "resume estas reseñas", "formatea este CSV" → Ollama, sin gate.
- **media**: "propón 5 ideas de posts" → OpenRouter, sin gate (es borrador interno).
- **critica**: "publica la campaña", "envía el correo", "responde esta queja" → OpenRouter
  + **gate de aprobación SI** (§4).

### 2.3 Estructura del Orquestador

Sigue el patrón `primer_contacto/agente.py` (CrewAI + `PersistentMCPClient`):

```python
# orquestador/agente.py
from core.llm_router import get_llm, ESTRATEGIA, RUTINA

def setup_crew(modo):
    llm_estrategia = get_llm(ESTRATEGIA)   # OpenRouter (razonamiento)
    llm_rutina     = get_llm(RUTINA)       # Ollama (delegación rápida)

    orquestador = Agent(
        role="Director de Operaciones de la Agencia",
        goal="Recibir el objetivo de la Directora, clasificarlo y delegar a las ramas correctas.",
        backstory=orquestador_prompt,
        llm=llm_estrategia,                 # el tronco razona con el mejor modelo
        tools=[crear_tarea, solicitar_aprobacion, consolidar],
        allow_delegation=True,              # única rama que delega
        verbose=True,
    )
    # ... tareas de clasificación y consolidación
```

### 2.4 Comunicación (bus de eventos)

Las ramas **no se llaman entre sí**; se comunican vía el Tronco y el volumen `/shared`:

```
Directora ──► TRONCO ──► (clasifica) ──► delega a RAMA(S)
                                   │
                          ┌────────┴─────────┐
                          ▼                  ▼
                     Rama entrega        Rama entrega
                     resultado a        resultado a
                     /shared/borradores  /shared/borradores
                                   │
                                   ▼
                          TRONCO consolida ──► ¿crítica? ──► gate aprobación
```

---

## 3. 🌿 Las Ramas (Agentes Especializados)

Cada rama es un área independiente (patrón `MODULOS.md`): `agente.py` + `servidor_mcp.py`
+ `system_prompts/` + `context/`. Herramientas y límites de autonomía por rama:

| Rama | Rol | Herramientas MCP | Modelo | Autonomía (puede hacer sin aprobación) | NO puede sin aprobación |
|------|-----|------------------|--------|----------------------------------------|--------------------------|
| **Contenido** | Copywriter multiformato | `generar_brief`, `adaptar_tono`, `reutilizar`, `revisar_ortografia` | rutina (borradores) / estrategia (copy final) | Crear **borradores** internos | Publicar en canales |
| **Redes Sociales** | Community Manager | `consultar_calendario`, `validar_hashtags`, `detectar_tendencias`, `programar_post` | estrategia | Curar y **preparar** calendario (borrador) | **Programar/publicar** |
| **Analítica** | Analista de KPIs | `extraer_metricas`, `calcular_roi`, `comparar_periodos`, `detectar_anomalias` | rutina (datos) / estrategia (interpretación) | Generar reportes | Modificar presupuesto/campañas pagadas |
| **Investigación** | Analista de mercado | `buscar_mercado`, `analizar_competencia`, `detectar_tendencias` | rutina (scraping) / estrategia (síntesis) | Investigar (solo lectura) | — |
| **Atención al Cliente** | Soporte y relaciones | `clasificar_mensaje`, `buscar_base`, `proponer_respuesta`, `escalar_queja` | rutina (triage) | Responder consultas **rutinarias** | Responder **quejas delicadas** |
| **Auditoría** (existente) | Auditor de huella digital | (reutiliza `primer_contacto/servidor_mcp.py`) | rutina / estrategia (Supervisor) | Auditar y generar JSON | — |

### 3.1 Regla de autonomía (principio rector)

> **"Una rama puede producir, nunca ejecutar lo irreversible."**
> Todo lo que produce un **borrador** o un **reporte** es autónomo.
> Todo lo que **publica, envía o gasta** requiere gate de aprobación (§4).

### 3.2 Herramientas y límites por rama (ejemplo)

```yaml
rama: atencion_cliente
límites:
  autonomo:
    - clasificar tickets
    - responder preguntas frecuentes (base de conocimiento)
    - escalar a humano
  requiere_aprobacion:
    - responder quejas/reclamos delicados   # 🔴 confidencialidad
    - ofrecer compensaciones o descuentos   # 🔴 impacto comercial
```

---

## 4. 🍎 Los Frutos (Entregables y Aprobación)

### 4.1 Qué se ejecuta AUTOMÁTICAMENTE (sin gate)

| Entregable | Rama |
|------------|------|
| Borradores de contenido, briefs, calendarios editoriales | Contenido / Redes |
| Reportes de análisis, KPIs, ROI | Analítica |
| Dossiers de investigación de mercado | Investigación |
| Respuestas a consultas rutinarias, triage de tickets | Atención al Cliente |
| Auditorías y propuestas internas (nunca se publican solas) | Auditoría |

### 4.2 Qué requiere APROBACIÓN EXPLÍCITA (gates de aprobación 🔴)

| Acción | Rama | Riesgo |
|--------|------|:---:|
| **Publicar** contenido en canales públicos | Contenido / Redes | Irreversible, expone la marca |
| **Programar/emitir** posts | Redes | Irreversible |
| **Enviar** campañas masivas (email, WhatsApp, ads) | Redes / Analítica | Costo real |
| **Responder quejas** o reclamos delicados | Atención al Cliente | Confidencialidad |
| **Gastar** (presupuesto de ads, compras) | Analítica | Impacto económico |
| **Cambiar** precios, promociones u ofertas públicas | Cualquiera | Comercial |
| **Compartir** datos de clientes / info confidencial | Cualquiera | Legal |

### 4.3 Implementación del gate de aprobación

Reutiliza `web_server.py` + `auth.py` (FastAPI + JWT) ya existentes. Se agrega la tabla
`aprobaciones` y endpoints:

```text
GET  /aprobaciones                → lista pendientes
POST /aprobaciones/{id}/aprobar   → {feedback}
POST /aprobaciones/{id}/rechazar  → {feedback}
```

```python
# orquestador/servidor_mcp.py
@mcp.tool()
def solicitar_aprobacion(tipo, detalle, borrador):
    """Registra entregable en la cola humana. El Tronco BLOQUEA hasta decisión."""
    return registrar_en_cola(ARBOL_ID, tipo, detalle, borrador)
```

Flujo de decisión de la Directora:

```
Tronco consolida fruto crítico
        │
        ▼
solicitar_aprobacion()  ──► cola (persistente en DB)
        │                     │
        │                     ▼
        │               Directora revisa (web/API)
        │              ├─ aprobar  → Tronco ejecuta la acción
        │              └─ rechazar → Tronco itera con feedback
```

> **Regla de oro**: `APROBACION_MODO=manual` en producción. El modo `auto` es solo de test
> y jamás se habilita con acciones 🔴.

---

## 5. 🌿➡️🌳 Replicación (Poda y Clonación)

Cada árbol = una instancia aislada (un cliente, una sucursal, un mercado). Todos comparten
la **misma semilla** pero tienen **datos y credenciales independientes**.

### 5.1 Qué se comparte y qué se aísla

| Recurso | Compartido (semilla) | Aislado (por árbol) |
|---------|----------------------|---------------------|
| Código / repo / manifiesto | ✅ read-only | — |
| `core/llm_router.py`, patrones | ✅ | — |
| Modelos (misma lista) | ✅ | — |
| `.env` (claves, `ARBOL_ID`) | ❌ | ✅ ÚNICA por árbol |
| Base de datos (`aprobaciones`, memoria) | ❌ | ✅ por árbol |
| `/shared` (borradores, memoria) | ❌ | ✅ por árbol |
| Usuarios de la Directora | ❌ | ✅ por árbol |

### 5.2 Paso a paso para clonar una semilla → nuevo árbol

> **La semilla es autónoma**: `sembrar.sh` crea sus propias dependencias y madura sola
> en un árbol completo en tres fases — **germinar** (instalar deps + modelo local),
> **crecer** (montar estructura: .env, /shared, DB, roles) y **madurar** (generar
> manifiesto Trinity + health check).

**Paso 0 — Precondiciones**: Git instalado, `uv` (o `pip`), Ollama corriendo
(`qwen3:27b` descargado), una API key de OpenRouter propia del nuevo árbol.

**Paso 1 — Clonar el repo semilla (solo código, sin secretos)**:
```bash
git clone <repo_semilla> arbol_cliente_01
cd arbol_cliente_01
# .env NO viene en el clone (está en .gitignore); se crea desde la plantilla
cp .env.example .env
```

**Paso 2 — Asignar identidad y credenciales únicas**:
```bash
# Editar .env:
#   ARBOL_ID=cliente_01
#   ARBOL_NOMBRE="Cliente X"
#   OPENROUTER_API_KEY=sk-or-...          # NUEVA, no reutilizar la de otro árbol
#   SERPAPI_KEY=...  GOOGLE_API_KEY=...
```

**Paso 3 — Preparar el volumen compartido aislado**:
```bash
mkdir -p shared/{borradores,memoria,aprobaciones,reportes}
```

**Paso 4 — Inicializar la base de datos del árbol**:
```bash
uv run python db.py init         # crea app_database.db + tablas (aprobaciones, memoria)
uv run python -c "from core.llm_router import get_llm; get_llm('rutina'); get_llm('estrategia')"
# verifica que los 2 modelos responden antes de continuar
```

**Paso 5 — Crear el usuario Directora del árbol**:
```bash
uv run python -c "from auth import crear_usuario; crear_usuario('directora@cliente01', 'CLAVE_MAESTRA', rol='directora_humana')"
```

**Paso 6 — Arrancar el Tronco + ramas**:
```bash
uv run python main.py --area orquestador     # servicio raíz
# Las ramas se registran automáticamente en el bus (patrón PersistentMCPClient)
```

**Paso 7 — Validación (smoke test)**:
```bash
# 1) Enviar tarea rutina → debe completarse SIN gate (Ollama).
# 2) Enviar tarea crítica "publicar campaña" → debe BLOQUEARSE en cola de aprobación.
# 3) Aprobar desde /aprobaciones → se ejecuta.
```

### 5.3 Despliegue en Trinity (por árbol)

```yaml
# manifiesto.yaml  (un árbol = un "namespace"/stack)
version: "1.0"
arbol:
  id: "cliente_01"
  rol: obrero                 # obrero | comandante  (ver §5.6 mente colmena)
  aprobacion: manual

# ---- ÁRBOL HIJO (OBRERO): servicios vivos 24/7 -----------------------
# El Tronco + todas las ramas corren de forma permanente, produciendo
# y atendiendo sin supervisión. Auto-reinicio + healthcheck siempre activos.
services:                      # (sección válida en árboles rol: obrero)
  orquestador:
    image: semilla-agen:orquestador
    env_file: .env                       # secretos por árbol, no en manifiesto
    volumes: ["shared:/shared"]          # aislado por árbol
    deploy: { replicas: 1, restart: always }
    healthcheck: { test: ["CMD", "python", "-c", "import db;db.init_db()"], interval: 30s, retries: 3 }
    permissions:
      ejecutar_accion_critica: false     # SIEMPRE false; lo hace la Directora
  contenido:     { image: semilla-agen:contenido,      env_file: .env, volumes: ["shared"], deploy: { restart: always } }
  redes:         { image: semilla-agen:redes,          env_file: .env, volumes: ["shared"], deploy: { restart: always } }
  analitica:     { image: semilla-agen:analitica,      env_file: .env, volumes: ["shared"], deploy: { restart: always } }
  investigacion: { image: semilla-agen:investigacion,  env_file: .env, volumes: ["shared"], deploy: { restart: always } }
  atencion:      { image: semilla-agen:atencion,       env_file: .env, volumes: ["shared"], deploy: { restart: always } }
  auditoria:     { image: semilla-agen:primer_contacto, env_file: .env, volumes: ["shared"], deploy: { restart: always } }

# ---- ÁRBOL PRINCIPAL (COMANDANTE): activo bajo demanda ---------------
# El comandante arranca en frío (cold start) solo cuando hay trabajo de
# coordinación/control. No mantiene ramas corriendo salvo cuando actúa como
# obrero temporal (fallback) para una tarea puntual.
services_comandante:           # (sección válida en árboles rol: comandante)
  comandante:
    image: semilla-agen:comandante
    env_file: .env
    volumes: ["shared:/shared"]
    deploy: { replicas: 0, restart: "no" }   # escala a 1 bajo demanda (cold start)
    permissions:
      ejecutar_accion_critica: false
      controlar_arboles: true                # único rol con permiso de SSH/control

permissions:
  trabajador:       [leer_briefs, escribir_borradores, publicar:false]
  orquestador:      [leer_todos, escribir_aprobaciones, ejecutar_accion_critica:false]
  comandante:       [controlar_arboles, ejecutar_tareas_agente]   # padre también es obrero (§5.6)
  directora_humana: [aprobar_acciones_criticas]     # único rol con permiso real
```

### 5.4 Reglas de replicación (poda segura)

1. **Nunca** clonar un `.env` de otro árbol; cada árbol genera el suyo desde `.env.example`.
2. **Nunca** compartir `/shared` entre árboles (memoria y datos aislados).
3. **Nunca** reutilizar la API key de OpenRouter de otro árbol (control de costos y límites
   por cliente).
4. Cada árbol es **stateless**: su estado vive en `shared/` y en su DB, no en el proceso
   → se puede replicar o migrar sin perder datos.
5. Para "podar" (eliminar un árbol): basta con detener sus servicios, respaldar/eliminar
   su `shared/` y su DB; la semilla queda intacta para futuros clones.

---

## 5.5 Comunicación raíz → árboles (canal privado)

El árbol principal controla y diagnostica a los árboles hijo por **canal privado**
(Tailscale o SSH puerto 22). Módulo `comunicacion/`:

- **Comandante** (`comunicacion/comandante_mcp.py`): corre en el árbol principal.
  Registra el inventario (tabla `arboles_remotos`), y via `ssh`/`scp` hace:
  `ping_arbol`, `estado_arbol` (hostname, ARBOL_ID, versión git, servicio, uptime),
  `ejecutar_comando`, `propagar_upgrade` (git fetch + reset hard + `uv sync`) y
  `propagar_archivo` (scp). Modo `COMANDANTE_DRY_RUN=1` para ensayar sin conectar.
- **Agente de Estado** (`comunicacion/servidor_estado_mcp.py`): corre en cada hijo.
  Expone `estado_local` y `aplicar_upgrade` (el Comandante los invoca de forma remota).

Requisitos: OpenSSH (`ssh`/`scp`) en el principal y llaves SSH configuradas para cada hijo
(hostname de Tailscale en el inventario). Estado online/offline se persiste por árbol.

```bash
uv run python main.py --arboles                                  # inventario
uv run python main.py --registrar-arbol --arb-id cliente_01 --arb-host cliente-01.tailnet.ts.net --arb-usuario root --arb-canal tailscale
```

## 5.6 🐝 Mente colmena: modelo operativo (obreros + comandante)

La agencia opera como una **colmena** donde cada nodo tiene un rol según el ciclo de
actividad, no solo una topología fija.

### Roles por perfil de actividad

| Rol | Nodo | Uptime | Carga | Responsabilidad |
|-----|------|--------|-------|-----------------|
| **Obrero** | Árboles hijo | 🟢 24/7 (aprox.) | Constante | Tronco + todas las ramas corriendo siempre: producen, atienden, publican tras gate. Son los servidores vivos. |
| **Comandante** | Árbol principal | 🔵 Bajo demanda (cold start) | Variable / picos | Coordina, diagnostica y controla a los obreros (vía `comunicacion/`). No mantiene ramas corriendo por defecto. |

### Reglas de la mente colmena

1. **Los obreros producen sin esperar al comandante.** Cada árbol hijo corre su propio
   Tronco 24/7, resuelve sus tareas locales (rutina/media/critica) y solo eleva lo que
   requiere a la Directora o necesita coordinación inter-árbol.

2. **El comandante se despierta cuando hay trabajo de colmena** (escala `replicas: 0 → 1`):
   - Diagnosticar/controlar obreros (`ping_arbol`, `estado_arbol`, `ejecutar_comando`).
   - Propagar upgrades (`propagar_upgrade`, `propagar_archivo`).
   - Coordinar campañas multi-cliente o mover trabajo de un obrero saturado a otro.

3. **El comandante también es un obrero (fallback).** Si la operación lo amerita, el padre
   puede **ejecutar tareas de agentes** (mismas ramas que un hijo): atender un pico de
   demanda, servir de respaldo si un obrero cae, o ejecutar una tarea que no justifica
   levantar un nodo nuevo. Permiso `comandante: [ejecutar_tareas_agente]`.

4. **División de permisos inalterable.** Aunque el comandante actúe como obrero, mantiene
   los gates: puede *producir* pero **no** publicar/enviar sin aprobación de la Directora.
   Solo `directora_humana` aprueba acciones críticas.

### Modelo de servicios (resumen)

```
┌───────────────────────┐   ┌─────────────────────────────────────────────┐
│  ÁRBOL PRINCIPAL       │   │  ÁRBOLES HIJO (N) — servidores vivos 24/7   │
│  rol: comandante       │   │  rol: obrero                                │
│  cold start            │   │                                            │
│                        │   │  ┌───────────┐  ┌───────────┐  ┌────────┐  │
│  comandante (ssh/scp) ─┼──▶│  │ orquestador│  │ contenido │  │ redes  │… │
│  ──► controla, diagnostica  │  └───────────┘  └───────────┘  └────────┘  │
│  ──► propaga upgrades       │  + analitica, investigacion, atencion     │
│  ──► (fallback) actúa como  │  + auditoria                              │
│      obrero si la operación │                                            │
│      lo amerita             │                                            │
└───────────────────────┘   └─────────────────────────────────────────────┘
        canal privado: Tailscale / SSH puerto 22
```

**Consecuencia operativa**: el costo de cómputo está en los **obreros** (siempre encendidos);
el **comandante** consume solo cuando se activa. Escalar la colmena = sembrar más obreros
(`sembrar.sh`) y registrarlos en el inventario del comandante.

## 5.7 👑 Heredero del comandante (failover)

Para evitar un único punto de fallo, se designa un nodo **heredero** que puede asumir la
comandancia si el comandante primario cae.

- **Rol**: `ARBOL_ROL=heredero` + `ARBOL_HEREDERO_DE=<host del primario>`.
- **Provisión**: `sembrar.sh <id> --rol heredero --heredero-de <host>`.
- **Failover** (herramientas MCP en `comunicacion/comandante_mcp.py`):
  1. `exportar_inventario()` — el primario expone su inventario (lista de obreros).
  2. `importar_inventario()` — el heredero replica ese inventario en su propia DB.
  3. `reclamar_comandancia()` — promueve al nodo a `ARBOL_ROL=comandante` (persistido en
     su `.env`) y asume el control de los obreros.

El heredero se siembra igual que un comandante (puede, si la operación lo amerita, actuar
también como obrero de respaldo), pero permanece frío hasta el failover. Si el primario
vuelve, se decide por política quién mantiene la comandancia (ej. el primario reconquista).

```bash
uv run python main.py --registrar-arbol --arb-id heredero_1 --arb-host heredero.tailnet.ts.net --arb-usuario root --arb-canal tailscale
# En el heredero (failover):
uv run python -c "from comunicacion.comandante_mcp import reclamar_comandancia; print(reclamar_comandancia())"
```

## 5.8 🖥️ Panel web del Comandante (localhost)

El árbol principal opera a los árboles hijo desde un **dashboard web en localhost**
(`comandante_web.py` + `comandante_web/static/index.html`):

- **API** (FastAPI): `GET/POST /api/arboles`, `POST /api/arboles/{id}/ping|estado|comando|upgrade|archivo`.
- **Frontend**: tabla de inventario con estado (online/offline) y botones Ping/Estado/Upgrade,
  formulario de registro y consola de comandos.
- **Auth opcional**: si se define `COMANDANTE_WEB_TOKEN`, todas las rutas exigen el header
  `X-Comandante-Token` (401 en caso contrario). Sin token, el panel opera abierto en localhost.

```bash
uv run uvicorn comandante_web:app --host 127.0.0.1 --port 8001
# o bien
uv run python comandante_web.py
```

## 5.9 🐳 Despliegue con Docker (cualquier máquina)

La semilla incluye Docker para que cada árbol corra en cualquier sistema:

- **`Dockerfile`** — contenedor autocontenido: instala todas las dependencias
  (filtrando `pywin32`, que es solo Windows) y monta las carpetas `/shared`.
- **`docker-compose.yml`** — perfiles por rol:
  - `--profile obrero` → Tronco + ramas 24/7 (`web_server`, puerto 8000, `restart: always`).
  - `--profile comandante` (y `heredero`) → panel de control (`comandante_web`, puerto 8001, cold start).
  - `--profile ollama` → contenedor Ollama local (opcional, requiere GPU/RAM).
- **`.dockerignore`** → excluye `.env`, `.venv`, DB, etc. (los secretos no entran a la imagen).

```bash
# Sembrar el árbol (genera .env) y luego:
docker compose --profile obrero up -d          # servidor vivo 24/7
docker compose --profile comandante up -d      # comandante bajo demanda
```

Los servicios se seleccionan por perfil; un solo `docker-compose.yml` sirve para toda la
colmena (obreros, comandante, heredero y Ollama).

## 5.10 🍄 Micelio: agente de mantenimiento (opción híbrida)

El **micelio** (`micelio/`) es el tejido conectivo de la colmena: un agente local de
mantenimiento que conecta los árboles y responde al árbol comandante. Como las raíces del
micelio, mantiene la estructura viva:

- **Salud**: `salud_estructura` (archivos, /shared, .env), `version_componentes` (git).
- **Mantenimiento**: `actualizar_componentes` (git fetch+reset+uv sync), `reparar_estructura`
  (recrea /shared, DB y manifiesto), `sincronizar_manifiesto`.
- **Parches**: `aplicar_parche` modifica un archivo de estructura **siempre con respaldo**.

A diferencia de las ramas de producción (que usan MCP por subproceso), el micelio ejecuta
sus herramientas **en-proceso** porque opera sobre el propio sistema local (git, archivos,
DB), lo que evita deadlocks de transporte.

Uso:
```bash
uv run python main.py --micelio            # diagnóstico + reparación local
docker compose --profile micelio up        # bajo demanda en Docker
```

El comandante puede invocar el micelio de un árbol remoto vía el canal privado
(`comunicacion`), o el micelio reporta su estado al comandante como sub-red.

## 5.11 🏛️ Doble sistema de árbol principal: Comandante vs Conservante

El nivel de árbol principal tiene DOS roles separados por permisos (RBAC):

| | **Comandante** | **Conservante** |
|---|---|---|
| Quién | Directora / operaciones de marketing | **Arquitecto / Dev** |
| Usa las ramas para campañas | ✅ | ✅ |
| Acceso al código / estructura | ❌ | ✅ |
| Micelio: revisar errores (salud/versión) | ✅ | ✅ |
| Micelio: upgrades (actualizar) | ✅ | ✅ |
| Micelio: reparar / sincronizar manifiesto | ❌ (403) | ✅ |
| Micelio: aplicar parches (modificar archivos) | ❌ (403) | ✅ |

**Implementación** (`core/permisos.py` + gating en `micelio/servidor_mcp.py`):
- `comandante` y `heredero`: micelio limitado (`salud_estructura`, `version_componentes`,
  `actualizar_componentes`). Cualquier herramienta de estructura devuelve **403**.
- `conservante`: micelio completo (`reparar_estructura`, `sincronizar_manifiesto`,
  `aplicar_parche`). Es el único con acceso a estructura/código.
- Panel **`conservante_web.py`** (puerto 8002): dashboard exclusivo del dev, requiere
  `CONSERVANTE_WEB_TOKEN` (sin él, se niega por defecto).

```bash
uv run python main.py --micelio                     # comandante: solo errores + upgrades
uv run uvicorn conservante_web:app --host 127.0.0.1 --port 8002   # conservante (dev)
```

Sembrar un árbol conservante: `sembrar.sh <id> --rol conservante` (genera manifiesto
con micelio completo).

## 6. 🗺️ Roadmap de implementación

| Fase | Alcance | Entregable |
|:---:|---------|-----------|
| 1 | ✅ `core/llm_router.py` + `.env` + **rotación automática 429** | ✅ Hecho (Ollama qwen3:27b / OpenRouter con fallbacks) |
| 2 | ✅ `orquestador/` + cola de aprobación + endpoints web | El Tronco + gates |
| 2b | ✅ Delegación real: Tronco → ramas (`delegar_rama` + `core/registro_ramas.py`) | Orquestación inter-agente |
| 3 | ✅ Rama `contenido/` (implementada y probada) | Flujo punta a punta (Directora→Tronco→Rama→gate) |
| 4 | ✅ Ramas `planeacion`, `redes`, `analitica`, `investigacion`, `atencion_cliente` + `auditoria` registradas | Equipo completo (7 ramas delegables) |
| 4b | ✅ Pipeline de campaña `orquestador/campana.py` (investigacion→planeacion→creacion→exposicion→analisis + gate) | Campaña orquestada multi-rama |
| 4c | ✅ Tronco → campaña: `ejecutar_campana_tool` detecta campaña y lanza el pipeline | Orquestación automática |
| 4d | ✅ Rotación con **fallback a Ollama local** cuando OpenRouter está 429 | Sin esperas de OpenRouter |
| 5 | ✅ `sembrar.sh` (germinar/crecer/madurar) + `core/manifiesto.py` + `manifiesto.yaml` | Replicación por cliente |
| 5b | ✅ Docker: `Dockerfile` + `docker-compose.yml` (perfiles obrero/comandante/ollama) | Despliegue en cualquier máquina |

---

## 7. ✅ Conclusión

La arquitectura "semilla-árbol" con lógica de **mente colmena** logra un equilibrio entre
**autonomía** (las ramas producen sin supervisión), **disponibilidad** (los obreros viven
24/7) y **seguridad** (nada irreversible se ejecuta sin la Directora). La clave operativa es:

1. **Semilla única** → coherencia y mantenibilidad entre árboles.
2. **Obreros 24/7** → los árboles hijo producen y atienden de forma permanente.
3. **Comandante bajo demanda** → coordina, controla y propaga upgrades solo cuando hace falta.
4. **El comandante también es obrero** → fallback: ejecuta tareas de agente si la operación lo amerita.
5. **Ramas autónomas para producir, bloqueadas para ejecutar** → no se publica nada por error.
6. **Gates de aprobación 🔴** → la Directora es la única autoridad para lo irreversible.
7. **Clonación limpia** → un servidor por cliente, datos y credenciales independientes,
   con la semilla intacta para crecer más árboles.