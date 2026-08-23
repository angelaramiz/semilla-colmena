# 🏢 Arquitectura de Agencia de Marketing Autónoma

**Directora Humana**: [Tu Nombre]
**Fecha**: 23 de agosto de 2026
**Estado**: Propuesta base de configuración (v1.0)
**Plataforma objetivo**: Trinity (despliegue multi-servidor)

---

## 0. Resumen Ejecutivo

Este documento define la arquitectura completa de una **agencia de marketing autónoma**
dirigida por un **Agente Orquestador** y un equipo de **agentes trabajadores**, con un
**nivel humano-in-the-loop** para acciones críticas.

La base técnica **ya existe y funciona** en el repo `agen_mrk` (CrewAI + FastMCP + Ollama).
Esta arquitectura **extiende** ese patrón en lugar de reemplazarlo, agregando:
1. Un **orquestador** que coordina agentes de negocio (no solo de auditoría).
2. **Asignación de modelo por tarea** (Ollama local vs OpenRouter cloud), no por crew.
3. **Capa de aprobación humana** con cola de autorización.
4. **Manifiesto de despliegue** replicable en Trinity.

> ⚠️ **Supuesto de plataforma**: "Trinity" se modela aquí como un orquestador de
> contenedores/agentes con manifiesto declarativo, carpetas compartidas y permisos.
> Si tu Trinity tiene un esquema de manifiesto distinto, solo hay que adaptar el §5;
> el resto (agentes, modelos, flujos, aprobación) es agnóstico de la plataforma.

---

## 1. 🧑‍💼 Organigrama de Agentes

### 1.1 Jerarquía general

```
                    ┌──────────────────────────────┐
                    │       DIRECTORA HUMANA        │  ← Autoridad final (aprobaciones)
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │      AGENTE ORQUESTADOR       │  ← Director de operaciones
                    │   (planifica, delega, revisa) │
                    └──────────────┬───────────────┘
                                   │ delega
        ┌─────────────┬─────────────┼─────────────┬─────────────┬─────────────┐
        ▼             ▼             ▼             ▼             ▼             ▼
   [CONTENIDO]   [REDES]      [ANALÍTICA]    [MERCADO]     [ATENCIÓN]   [AUDITORÍA]*
    ────────     ────────      ──────────     ─────────     ──────────   ──────────
   Copywriter   Community     Analista de    Investigador   Asistente   (Existente)
   Multiformato  Manager       Datos/KPIs     de Mercado     al Cliente
```
`*` El módulo `primer_contacto/` (auditoría de huella digital) se conserva como un **agente
especializado más**, reutilizando su código actual.

### 1.2 Tabla de agentes, rol, herramientas y salida

| Agente | Rol (CrewAI `role`) | Goal | Herramientas MCP clave | Salida |
|--------|---------------------|------|------------------------|--------|
| **Orquestador** | Director de Operaciones de la Agencia | Recibir objetivo del cliente → armar plan → delegar a trabajadores → consolidar → pedir aprobación | `crear_tarea`, `revisar_entregable`, `solicitar_aprobacion`, `enviar_a_cola`, `consultar_memoria` | Plan de trabajo + consolidado + solicitudes de aprobación |
| **Contenido** | Copywriter & Estratega de Contenido Multiformato | Redactar textos/guiones/piezas por plataforma y audiencia | `generar_brief`, `adaptar_tono`, `reutilizar_contenido`, `revisar_ortografia` | Brief + borradores (blog, email, ads, video) |
| **Redes Sociales** | Community Manager Autónomo | Programar/curar contenido y gestionar comunidad en cada canal | `consultar_calendario`, `validar_hashtags`, `detectar_tendencias`, `programar_post` | Calendario editorial + posts listos para aprobación |
| **Analítica** | Analista de Datos & KPIs | Medir resultados, detectar qué funciona y recomendar ajustes | `extraer_metricas`, `calcular_roi`, `comparar_periodos`, `detectar_anomalias` | Reporte de KPIs + recomendaciones accionables |
| **Investigación de Mercado** | Analista de Mercado y Competencia | Investigar audiencia, competencia, tendencias y oportunidades | `buscar_mercado`, `analizar_competencia`, `detectar_tendencias`, `encuestar_audiencia` | Dossier de mercado + oportunidades |
| **Atención al Cliente** | Agente de Soporte y Relaciones | Atender consultas, clasificar tickets y escalar quejas | `clasificar_mensaje`, `buscar_base_conocimiento`, `proponer_respuesta`, `escalar_queja` | Respuestas propuestas + tickets clasificados |
| **Auditoría (existente)** | Auditor de Huella Digital | Auditar presencia digital y competencia local | (reutiliza `primer_contacto/servidor_mcp.py`) | JSON triple de auditoría |

### 1.3 Mapeo al código existente

Sigue el patrón de `MODULOS.md`. Cada agente trabajador es un **área** independiente:

```
agen_mrk/
├── orquestador/
│   ├── agente.py              # setup_crew del Orquestador (patrón primer_contacto/agente.py:157)
│   ├── servidor_mcp.py        # tools de coordinación (cola, aprobación, memoria)
│   └── system_prompts/orquestador.md
├── contenido/                 # Contenido
├── redes_sociales/            # Redes Sociales
├── analitica/                 # Analítica
├── mercado/                   # Investigación de Mercado
├── atencion_cliente/          # Atención al Cliente
└── primer_contacto/           # [EXISTENTE] Auditoría → se conserva
```

---

## 2. 🧠 Asignación de Modelos (Ollama local vs OpenRouter cloud)

### 2.1 Principio

Cada **tarea** de cada agente declara en qué "nivel" corre:

- **🟢 Ollama (local)** = tareas **rutinarias, deterministas y de alto volumen**:
  scraping, extracción/normalización de datos, resúmenes, clasificación, formateo JSON,
  deduplicación. Ventajas: gratis, privado, sin latencia de red, sin costo por token.
- **🔵 OpenRouter (cloud)** = tareas de **estrategia, redacción creativa y decisión**:
  tono de marca, copy final, planes estratégicos, priorización, recomendaciones sensibles.
  Ventajas: calidad superior (Claude, GPT, Gemini vía un solo API key).

### 2.2 Matriz agente → modelo por tipo de tarea

| Agente | 🟢 Ollama (local) — rutina | 🔵 OpenRouter — estrategia/creatividad |
|--------|---------------------------|----------------------------------------|
| **Orquestador** | Consolidar entregables, formatear reportes | Planificar el plan de trabajo, priorizar, decidir qué delegar |
| **Contenido** | Reutilizar/adaptar plantillas, corregir gramática, SEO tags | Redacción creativa del copy, tono de marca, guiones |
| **Redes Sociales** | Normalizar formatos, validar hashtags, armar calendario | Definir voz del canal, elegir piezas destacadas, storytelling |
| **Analítica** | Extraer métricas, calcular KPIs, generar tablas | Interpretar resultados, recomendar ajustes de presupuesto/estrategia |
| **Investigación de Mercado** | Scraping, extraer datos de competencia, deduplicar | Sintetizar dossier, detectar oportunidades, redactar informe |
| **Atención al Cliente** | Clasificar mensaje, buscar en base de conocimiento | Redactar respuesta a queja compleja (aún así requiere aprobación) |
| **Auditoría (existente)** | Investigar, auditar mapas/redes, analizar competencia (como hoy) | Síntesis del Supervisor (JSON triple) con mayor calidad |

### 2.3 Implementación (abstracción por tarea)

Se agrega un **resolvedor de LLM** que reemplaza la lógica monolítica actual de
`get_local_llm()` (`primer_contacto/agente.py:31`). Ahora el modelo se elige por tarea:

```python
# core/llm_router.py (nuevo)
import os
from crewai import LLM

def get_llm(nivel: str = "rutina") -> LLM:
    """Elige modelo según el nivel de la tarea."""
    if nivel == "estrategia":                       # 🔵 OpenRouter
        return LLM(
            model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            temperature=0.7,                        # creatividad
            max_tokens=4096,
        )
    # 🟢 Ollama local (default, rutina)
    return LLM(
        model=os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b"),
        base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
        api_key="not-needed",
        temperature=0.01,                           # determinista
        top_p=0.9,
        timeout=120,
        max_tokens=2048,
    )
```

Ejemplo de uso en un agente:
```python
agente_creativo = Agent(..., llm=get_llm("estrategia"))
agente_extraccion = Agent(..., llm=get_llm("rutina"))
```

### 2.4 Variables de entorno nuevas (`.env`)

```env
# === Modelos ===
# Rutina (local, gratis, privado)
USE_LOCAL_LLM=true
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=llama3.1:8b

# Estrategia/Creatividad (OpenRouter)
OPENROUTER_API_KEY=sk-or-...                # https://openrouter.ai/keys
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# === Aprobación humana ===
APROBACION_MODO=manual                      # manual | auto (nunca auto en producción)
```

> **Política de fallback**: si `OPENROUTER_API_KEY` falta, el router degrada
> "estrategia" a Ollama local con una advertencia en logs, para que el sistema nunca se rompa.

---

## 3. 🔄 Flujos de Trabajo

### 3.1 Ciclo principal (objetivo → entregable)

```
Directora Humana
      │  objetivo del cliente (mensaje / API)
      ▼
[ORQUESTADOR] ── plan de trabajo (tareas + responsable + modelo)
      │  delega en paralelo
      ├──▶ CONTENIDO         ─┐
      ├──▶ REDES SOCIALES    ─┤  cada uno resuelve su entregable
      ├──▶ MERCADO           ─┤  con su MCP local (scraping) + LLM
      └──▶ ANALÍTICA         ─┘
      │  cada uno notifica al Orquestador
      ▼
[ORQUESTADOR] consolida → redacta propuesta final
      ▼
solicita APROBACIÓN HUMANA (si la acción lo requiere, ver §4)
      ▼
Directora aprueba/rechaza → Orquestador ejecuta o itera
```

### 3.2 Comunicación entre agentes (eventos, no acoplamiento)

Los agentes **no se llaman entre sí directamente**; se comunican por eventos/mensajes
a través del Orquestador y de **carpetas/memoria compartida**:

```
Canal                    Uso
────────────────────────────────────────────────────────────
Cola de tareas           Orquestador emite tareas; trabajadores consumen
Buzón de resultados      Trabajador publica entregable; Orquestador consume
Memoria compartida       Contexto reutilizable (briefs, estilo de marca, histórico)
Base de conocimiento     Fuente para Atención al Cliente y Contenido
Cola de aprobaciones     Entregables críticos → cola → Directora → decisión
```

Este es exactamente el patrón ya probado de `PersistentMCPClient`
(`primer_contacto/agente.py:70`): cada área expone tools FastMCP y se conecta vía
stdio. La novedad es que ahora hay **nodos de mensajería** (cola + buzón) en lugar de
un único crew secuencial.

### 3.3 Ejemplo de flujo concreto (campaña "Lanzamiento de restaurante")

1. Directora: "Lanza la campaña de apertura de La Parroquia en IG, en 2 semanas."
2. **Orquestador** (OpenRouter): arma plan → 4 tareas paralelas.
3. **Mercado** (Ollama scraper + OpenRouter informe): audiencia + competencia en la zona.
4. **Contenido** (OpenRouter): 10 piezas de copy con tono de marca.
5. **Redes Sociales** (Ollama normaliza + OpenRouter storytelling): calendario de 14 días.
6. Orquestador consolida un **Paquete de Publicación**.
7. Como **publicar** es crítica → **solicita aprobación** → la Directora revisa → aprueba.
8. Redes Sociales ejecuta la programación; Analítica monitorea KPIs.

---

## 4. 🛡️ Aprobación Humana (Human-in-the-loop)

### 4.1 Acciones críticas (SIEMPRE requieren aprobación explícita)

| Acción | Nivel de riesgo | Motivo |
|--------|:---:|--------|
| **Publicar contenido** en canales públicos (IG, FB, X, web) | 🔴 | Expone la marca; irreversible |
| **Enviar campañas** masivas (email, WhatsApp, ads con presupuesto) | 🔴 | Costo real + riesgo reputacional |
| **Responder quejas / mensajes delicados** de clientes | 🔴 | Confidencialidad y tono |
| **Gastos** (comprar anuncios, contratar servicios) | 🔴 | Impacto económico |
| **Cambiar precio, promociones u ofertas públicas** | 🟠 | Impacto comercial |
| **Compartir datos de clientes / info confidencial** | 🟠 | Legal |

### 4.2 Acciones autónomas (NO requieren aprobación)

- Investigación y scraping (solo lectura).
- Borradores y propuestas internas (nunca se publican solas).
- Generación de reportes de análisis.
- Clasificación y triage de tickets.
- Agenda interna y recordatorios.

### 4.3 Implementación de la cola de aprobación

Se reutiliza la infraestructura ya existente de `auth.py` + `web_server.py`
(FastAPI + JWT). Se agrega una tabla `aprobaciones` y endpoints:

```python
# orquestador/servidor_mcp.py (tools nuevas)
@mcp.tool()
def solicitar_aprobacion(tipo: str, detalle: str, borrador: str) -> str:
    """Registra un entregable en la cola de aprobación humana.
    El Orquestador NO continúa hasta recibir decision. Devuelve id."""
    ...

@mcp.tool()
def consultar_aprobacion(aprobacion_id: str) -> str:
    """Consulta estado: pendiente | aprobada | rechazada (con feedback)."""
    ...
```

Flujo de la Directora (web):

```
[web_server.py] ── GET /aprobaciones  (lista pendientes)
                   ├── POST /aprobaciones/{id}/aprobar  {feedback}
                   └── POST /aprobaciones/{id}/rechazar {feedback}
[Orquestador]    ── bloquea hasta decisión; si rechaza, itera con feedback
```

**Regla de oro**: `APROBACION_MODO` debe ser `manual` en producción. El modo `auto`
solo existe para tests y nunca se activa con acciones 🔴.

---

## 5. 🚀 Despliegue en Trinity (manifiesto, carpetas, permisos)

### 5.1 Modelo de despliegue propuesto

Cada **agente** es un servicio/worker independiente que Trinity orquesta. El
**Orquestador** es el servicio raíz que se comunica con los trabajadores a través de
**carpetas compartidas** (volúmenes comunes) y **cola de mensajes**.

```
Servidor A (control):  orquestador + cola + aprobaciones
Servidor B (trabajo):  contenido + redes + atención
Servidor C (trabajo):  analítica + mercado + auditoría
Carpeta compartida:    /shared/{briefs,borradores,aprobaciones,memoria}
```

### 5.2 Estructura de carpetas compartidas (volumen)

```
/shared/
├── briefs/          # inputs de campaña y estilo de marca (leídos por todos)
├── borradores/      # entregables en progreso
├── aprobaciones/    # cola de autorización (JSON por item)
├── memoria/         # memoria de largo plazo (historial, decisiones)
└── reportes/        # salidas finales (reportes, calendarios)
```

> Coincide con las carpetas ya existentes `reportes/`, `reportes_web/`, `agent_memory/`
> del repo; se centralizan bajo un volumen compartido.

### 5.3 Manifiesto inicial (ejemplo conceptual para Trinity)

```yaml
# trinity-agencia.yaml
version: "1.0"
agencia:
  nombre: "Agencia Autónoma de Marketing"
  directora: "nombre@dominio.com"
  aprobacion: manual              # ver §4

# Orquestador = servicio raíz (control)
services:
  orquestador:
    image: agen_mrk:orquestador
    agent: orquestador
    modelo_estrategia: openrouter/claude-3.5-sonnet
    modelo_rutina: ollama/llama3.1:8b
    volumes:
      - shared:/shared
    permissions:
      cola: ["crear_tarea", "solicitar_aprobacion"]
      ejecutar_accion_critica: false        # SIEMPRE false; delega a Directora

# Trabajadores (replicables a N servidores)
  contenido:      { image: agen_mrk:contenido,      agent: contenido,      volumes: [shared], deploy: {replicas: 2} }
  redes:          { image: agen_mrk:redes,          agent: redes,          volumes: [shared] }
  analitica:      { image: agen_mrk:analitica,      agent: analitica,      volumes: [shared] }
  mercado:        { image: agen_mrk:mercado,        agent: mercado,        volumes: [shared] }
  atencion:       { image: agen_mrk:atencion,       agent: atencion,       volumes: [shared] }
  auditoria:      { image: agen_mrk:primer_contacto, agent: auditoria,     volumes: [shared] }

# Permisos por rol (RBAC)
permissions:
  trabajador:
    - escribir_borradores
    - leer_briefs
    - publicar: false            # 🔴 los trabajadores NUNCA publican directo
  orquestador:
    - leer_todos
    - escribir_aprobaciones
    - ejecutar_accion_critica: false
  directora_humana:
    - aprobar_acciones_criticas   # único rol con permiso true
```

### 5.4 Puntos clave para replicar en múltiples servidores

1. **Volumen compartido único** (`/shared`): es la columna vertebral de comunicación;
   cualquier servidor nuevo solo necesita montarlo.
2. **Stateless por trabajador**: cada agente guarda estado en `memoria/` (compartido),
   no localmente → se pueden escalar réplicas sin duplicar estado.
3. **RBAC estricto**: el permiso `publicar` y `ejecutar_accion_critica` está **solo**
   en el rol `directora_humana`. Esto garantiza el §4 incluso si un agente se desvía.
4. **Secrets** via Trinity: `OPENROUTER_API_KEY`, `SERPAPI_KEY`, etc. se inyectan como
   variables de entorno por servicio, nunca en el manifiesto.
5. **Healthchecks**: cada servicio expone `/health`; Trinity reinicia si un worker cae
   y el Orquestador reencola la tarea pendiente.

### 5.5 Checklist de despliegue

- [ ] Manifiesto `trinity-agencia.yaml` validado
- [ ] Volumen `/shared` creado y montado en todos los servicios
- [ ] Secrets inyectados (OpenRouter, SerpAPI, Google, DB)
- [ ] Permisos RBAC: solo `directora_humana` puede publicar/aprobar
- [ ] `APROBACION_MODO=manual`
- [ ] Test de réplica: levantar 2× contenido → misma memoria, sin conflicto

---

## 6. 🗺️ Roadmap de implementación

| Fase | Alcance | Entregable |
|:---:|---------|-----------|
| **1** | `core/llm_router.py` + `.env` OpenRouter | Router por tarea (Ollama/OpenRouter) |
| **2** | `orquestador/` (agente + cola + aprobaciones + web endpoints) | Orquestador + cola de aprobación |
| **3** | 1er trabajador: `contenido/` | Flujo completo de punta a punta |
| **4** | `redes/`, `analitica/`, `mercado/`, `atencion/` | Equipo completo |
| **5** | Manifiesto Trinity + volumen compartido | Despliegue multi-servidor |

---

## 7. Conclusión

La agencia se construye **sobre la base sólida ya existente** (`primer_contacto/`,
patrón `MODULOS.md`, `PersistentMCPClient`, stack FastAPI+auth). Las tres innovaciones
clave son:

1. **Router de modelos por tarea** (§2) — calidad donde importa, costo cero donde no.
2. **Orquestador + cola de aprobación** (§3, §4) — autónoma pero segura.
3. **Manifiesto Trinity con RBAC** (§5) — replicable y con la Directora Humana como
   única autoridad para acciones críticas.