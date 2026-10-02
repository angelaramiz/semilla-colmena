# PLAN DE MEJORA PROGRESIVA

> Fecha: 2026-10-01 · Complementa `OPCIONES-MEJORA.md` (el QUÉ).
> Este archivo define el CUÁNDO, el POR QUÉ, los PROS/CONTRAS y el criterio de éxito de cada opción.
> Principio rector: primero ver lo que hay, luego automatizarlo, luego darle memoria,
> luego soberanía, y al final escalar el negocio encima.

## Fase 0 — Deuda inmediata (antes de agregar nada)

- Fijar `OPENROUTER_MODEL` del repo (el `z-ai/glm-5.2:free` murió: 404 solo-pago; el lab ya usa `qwen/qwen3.8-27b:free`).
- Extender la rotación de `core/llm_router.py` a 404 además de 429 (hoy un modelo muerto mata la estrategia sin fallback).
- Commitear los timeouts 600s ya aplicados en el lab.

## Fase 1 — Ver lo que hay (observabilidad y respuesta)

### 1. Uptime Kuma
- **Por qué ahora:** es lo más barato y ya hubo congelamientos y caídas silenciosas. Sin esto, todo lo demás se construye sobre una base que puede estar caída sin que nadie lo note.
- **Pros:** setup de minutos, costo cero, avisa por Telegram, cubre todos los árboles desde un solo punto.
- **Contras:** solo dice "está caído", no por qué; otro contenedor que operar.
- **Éxito:** los 3 puertos de cada árbol monitoreados con alerta en < 2 min.

### 2. Langfuse
- **Por qué ahora:** ya hubo 3 incidentes de LLM (modelo muerto 404, 429s masivos, timeout local 60s) detectados a mano por logs. Con trazas se ven en un dashboard con costo y latencia por etapa.
- **Pros:** ahorra dinero (detecta modelos caros/lentos), acelera el debug de crews, audita decisiones del agente.
- **Contras:** suma Postgres/ClickHouse al stack; hay que instrumentar cada llamada (cambio pequeño pero toca `llm_router` y crews).
- **Éxito:** cada etapa de campaña visible con tokens, costo y latencia; alerta ante rachas de 429.

## Fase 2 — Automatizar el flujo (pegamento)

### 3. n8n
- **Por qué ahora:** con visibilidad (Fase 1), lo siguiente es dejar de operar a mano: campañas programadas, gates que llegan solos a Telegram, publicación de lo aprobado.
- **Pros:** cientos de integraciones sin código, reintentos y logs incluidos, reemplaza scripts sueltos.
- **Contras:** un workflow mal diseñado dispara campañas solas (riesgo: gates siempre primero); otro servicio con credenciales que cuidar.
- **Éxito:** una campaña semanal programada + gate de exposición llegando a Telegram sin intervención.

### 4. mcpo / ToolHive (gateway MCP)
- **Por qué ahora:** n8n y otros sistemas necesitan consumir las herramientas de las ramas sin cliente MCP a medida; además centraliza auth y logs de herramientas.
- **Pros:** un solo endpoint para todo, OpenAPI gratis con mcpo, ordena el caos de `servidor_mcp.py` por rama.
- **Contras:** capa extra (latencia, punto de falla); hay que mantener el catálogo al día.
- **Éxito:** n8n ejecuta `buscar_negocio` y `ejecutar_campana` vía gateway sin código custom.

## Fase 3 — Memoria y conocimiento (el agente aprende)

### 5. Qdrant
- **Por qué ahora:** con el flujo automatizado, el desperdicio visible es que cada campaña investiga desde cero. RAG sobre dossieres y piezas pasadas mejora calidad sin cambiar crews.
- **Pros:** liviano, rápido, cliente Python oficial, se llena solo con cada campaña.
- **Contras:** necesita pipeline de ingesta (quién trocea y etiqueta); sin higiene se vuelve basurero vectorial.
- **Éxito:** la etapa de investigación cita material de campañas anteriores.

### 6. mem0
- **Por qué ahora:** Qdrant guarda documentos; mem0 guarda *criterio* (gustos de la Directora, decisiones, contexto entre sesiones). Es lo que convierte al comandante en un operador con memoria.
- **Pros:** se integra a CrewAI, usa Ollama local para embeddings (costo cero), efecto compuesto con el tiempo.
- **Contras:** la memoria mala también persiste (hay que curarla); otra dependencia en el path crítico del agente.
- **Éxito:** la Directora corrige algo una vez y no tiene que repetirlo.

### 7. AnythingLLM / LibreChat (elegir uno)
- **Por qué ahora:** con memoria y RAG listos, falta la puerta de entrada humana usable: preguntar en lenguaje natural en vez de curl.
- **Pros:** cero código, la Directora opera sin intermediarios, usa los modelos ya pagados/en local.
- **Contras:** dos herramientas solapadas (elegir UNA); permisos por usuario que configurar.
- **Éxito:** la Directora consulta un reporte pasado en chat sin ayuda.

## Fase 4 — Soberanía y repetibilidad (infraestructura propia)

### 8. Headscale
- **Por qué ahora:** toda la operación (árboles, paneles, n8n, alertas) ya corre sobre la malla; que dependa de un tercero gratuito es el riesgo estructural mayor.
- **Pros:** mismos clientes y red `100.x`, control total, sin costo.
- **Contras:** migrar N nodos coordinadamente (ventana de corte); operar el servidor (backups, updates).
- **Éxito:** todos los árboles en Headscale propio con la misma latencia de hoy.

### 9. SOPS + age
- **Por qué ahora:** con más servicios (n8n, Langfuse, Mautic...) el malabarismo de `.env` fuera del repo se vuelve inmanejable; cifrados en git se auditan y replican.
- **Pros:** mantiene "cero secretos en claro", un secreto por entorno, funciona con Ansible.
- **Contras:** gestión de llaves age por árbol (si se pierde, se re-cifra todo); curva inicial.
- **Éxito:** `vm.env` desaparece como archivo suelto; todo secreto vive cifrado en el repo.

### 10. E2B (sandbox)
- **Por qué ahora:** antes de que el agente ejecute más cosas solo (n8n + memoria), aislar la ejecución. Ya hubo un susto con Defender.
- **Pros:** blast radius cero por ejecución, trazabilidad, barato.
- **Contras:** latencia por arranque de sandbox; código con dependencia de red local no corre igual aislado.
- **Éxito:** todo código generado por agentes corre en sandbox, nunca en el árbol.

### 11. Ansible
- **Por qué ahora:** el `sembrar.ps1` cumplió pero es frágil (6 parches en una semana lo prueban). Con la infra creciendo, la siembra debe ser idempotente y estar en git.
- **Pros:** correrlo N veces es seguro, documenta el estado deseado, ecosistema enorme de roles.
- **Contras:** reescribir 368 líneas probadas (riesgo de regresión); PowerShell-remoting/WinRM en Windows es más áspero que SSH.
- **Éxito:** `ansible-playbook arbol.yml` reproduce `cmd_vm_01` desde cero sin intervención.

### 12. Packer (+ Vagrant)
- **Por qué ahora:** con Ansible listo, el paso lento restante es la instalación de Windows (2h + OOBE). La imagen se construye una vez y se clona.
- **Pros:** árbol nuevo en minutos, imágenes versionadas, adiós OOBE manual para siempre.
- **Contras:** construir imágenes Windows es lento y pesado (decenas de GB); otro artefacto que almacenar.
- **Éxito:** clonar comandante nuevo < 15 min.

## Fase 5 — Escalar el negocio (operar clientes de verdad)

### 13. Mautic
- **Por qué ahora:** la etapa de exposición hoy no emite nada. Para vender operación (no solo auditorías), el destino del gate aprobado debe existir.
- **Pros:** es el negocio mismo (email, nurturing, tracking), open source maduro, se integra con n8n.
- **Contras:** el más pesado de operar (PHP/MySQL, reputación IP para email, warm-up de dominio); sin clientes que lo usen es costo hundido.
- **Éxito:** primera campaña real de un cliente emitida desde el gate aprobado.

### 14. Matomo
- **Por qué ahora:** la rama analítica necesita datos reales, no `metricas_json` a mano; y los datos de clientes no deberían ir a Google.
- **Pros:** sin cookies de terceros, compatible con Mautic, auto-hospedado.
- **Contras:** otro PHP/MySQL; sin tráfico que medir no aporta.
- **Éxito:** reporte de campaña con datos Matomo sin intervención manual.

### 15. Plane
- **Por qué ahora:** con 5 fases y varios sistemas, el Kanban en markdown se queda corto para coordinar trabajo y fechas visibles a la Directora.
- **Pros:** Jira-like sin costo, vistas y responsables, se expone en la malla.
- **Contras:** migrar el protocolo Gate actual sin romperlo; disciplina de uso o muere vacío.
- **Éxito:** `Pending/onProces/Audit` reflejados en Plane y consultados por la Directora.

### 16. Restic / Kopia
- **Por qué ahora:** con todo lo anterior, perder un árbol duele de verdad. Snapshots locales no son backup.
- **Pros:** cifrado, incremental, a cualquier destino, barato.
- **Contras:** hay que probar restauraciones (backup no probado = no backup); consume ancho de banda.
- **Éxito:** restauración completa de un árbol desde backup en ejercicio trimestral.

### 17. Listmonk / MinIO (condicionales)
- **Por qué solo si hace falta:** Listmonk si Mautic sobra para solo newsletters; MinIO cuando `/shared` local se quede corto para piezas y artefactos.
- **Pros:** pequeños, una sola función, sin sorpresas.
- **Contras:** sumar servicios por si acaso es anti-Fase 1 (cada servicio es superficie que monitorear).
- **Éxito:** se adoptan solo ante necesidad medida, no antes.

## Orden resumido

0. Deuda LLM → 1. Uptime Kuma → 2. Langfuse → 3. n8n → 4. gateway MCP → 5. Qdrant → 6. mem0 → 7. chat (uno) → 8. Headscale → 9. SOPS → 10. E2B → 11. Ansible → 12. Packer → 13. Mautic → 14. Matomo → 15. Plane → 16. Restic → 17. condicionales.
