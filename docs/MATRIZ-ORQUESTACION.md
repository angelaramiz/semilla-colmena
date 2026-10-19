# Matriz de trabajo orquestado — Agencia (OpenBot + puente + memoria)

Plantilla aplicada a cada bot del tenant `examples/agencia`:
actúa como agente autónomo, lee contexto de memoria compartida, ejecuta,
guarda resultado, transfiere por eventos. Sin intervención humana en el ciclo.

## Mapeo plantilla → implementación real

| Plantilla | Implementación |
|---|---|
| Memoria compartida | mem0 + Qdrant (`scripts/memoria.py`, `user_id=directora`, colección agencia) |
| Leer contexto | `recordar "<tema>"` → top memorias con score |
| Guardar resultado | `guardar "<hecho>"` tras cada entrega |
| Herramientas | Endpoint AG-UI propio + herramientas del puente por rama |
| Evento salida / error | JSON `ENTREGABLE {...}` / `ERROR {...}` que devuelve el endpoint; el orquestador lo lee y delega al siguiente |
| Hooks que bloquean | Regla operativa: ningún bot publica, gasta ni aprueba; solo borradores (gate = Directora Humana) |

## Formato de eventos (todos los bots)

Salida:
```json
{"evento": "<EVENTO_SALIDA>", "rama": "<id>", "resultado": "<texto o JSON>",
 "memoria_guardada": true, "siguiente": "<id_bot>|directora|fin"}
```
Error:
```json
{"evento": "<EVENTO_ERROR>", "rama": "<id>", "error": "<causa>",
 "reintento": true|false, "siguiente": "orquestador"}
```

## 1. orquestador (Orquestador, remote-ag-ui → puente /ag-ui)

- **ROL:** clasifica el pedido, arma el plan (secuencia de ramas), delega, valida entregables, pide gate a Directora cuando hay exposición/gasto.
- **HERRAMIENTAS:** `delegar_rama`, `leer_memoria`, `guardar_memoria`, `pedir_gate`.
- **FLUJO:** lee pedido + memorias → plan → delega rama 1 → recibe ENTREGABLE → delega rama 2 → … → consolida → si exposición/gasto pide gate, si no entrega.
- **SALIDA:** `ORQUESTA_LISTO` (`siguiente: directora|fin`). **ERROR:** `ORQUESTA_ERROR`.

## 2. rama-investigacion (Analista Mercado)

- **ROL:** produce dossier de mercado: tema, ciudad, categoría. Solo lectura.
- **HERRAMIENTAS:** `buscar_mercado`, `leer_memoria`, `guardar_memoria`.
- **ENTRADA:** `{tema, ciudad, categoria}` o texto libre (→ tema).
- **SALIDA:** `DOSSIER_LISTO` con `{resumen, publico, competencia, oportunidades}` (`siguiente: rama-planeacion`). **ERROR:** `DOSSIER_ERROR`.

## 3. rama-planeacion (Estratega)

- **ROL:** convierte dossier en plan con KPIs, público y calendario.
- **HERRAMIENTAS:** `planificar`, `leer_memoria`, `guardar_memoria`.
- **ENTRADA:** dossier (`DOSSIER_LISTO`) + `{objetivo, presupuesto_ref}`.
- **SALIDA:** `PLAN_LISTO` con `{objetivos, kpis, publico, calendario}` (`siguiente: rama-contenido`). **ERROR:** `PLAN_ERROR`.

## 4. rama-contenido (Copywriter)

- **ROL:** piezas multiformato según plan: tema, marca, audiencia, plataformas, tono.
- **HERRAMIENTAS:** `redactar`, `leer_memoria`, `guardar_memoria`.
- **ENTRADA:** plan (`PLAN_LISTO`) + `{tema, marca, audiencia, plataformas, tono}`.
- **SALIDA:** `PIEZAS_LISTAS` con `{piezas: [{plataforma, texto}]}` (`siguiente: rama-redes`). **ERROR:** `PIEZAS_ERROR`.

## 5. rama-redes (Community Manager)

- **ROL:** calendario de publicación: marca, audiencia, plataformas, periodo, objetivo. No publica.
- **HERRAMIENTAS:** `calendarizar`, `leer_memoria`, `guardar_memoria`.
- **ENTRADA:** piezas (`PIEZAS_LISTAS`) + `{periodo, objetivo}`.
- **SALIDA:** `CALENDARIO_LISTO` con `{slots: [{fecha, plataforma, pieza}]}` (`siguiente: orquestador|directora` para gate). **ERROR:** `CALENDARIO_ERROR`.

## 6. rama-analitica (Analista KPI)

- **ROL:** reportes y ROI desde métricas. Reporta, no modifica presupuesto.
- **HERRAMIENTAS:** `reportar`, `leer_memoria`, `guardar_memoria`.
- **ENTRADA:** `{objetivo, periodo, metricas_json}`.
- **SALIDA:** `REPORTE_LISTO` con `{hallazgos, roi, recomendaciones}` (`siguiente: orquestador`). **ERROR:** `REPORTE_ERROR`.

## 7. rama-atencion (Soporte)

- **ROL:** responde lo rutinario al cliente, escala quejas al humano.
- **HERRAMIENTAS:** `responder`, `leer_memoria`, `guardar_memoria`.
- **ENTRADA:** `{mensaje, cliente}`.
- **SALIDA:** `RESPUESTA_LISTA` con `{respuesta, escala_humano: true|false}` (`siguiente: fin|directora` si escala). **ERROR:** `RESPUESTA_ERROR`.

## 8. rama-auditoria (Auditor Huella)

- **ROL:** auditoría digital del negocio (ciudad, recursos) → JSON triple.
- **HERRAMIENTAS:** `auditar`, `leer_memoria`, `guardar_memoria`.
- **ENTRADA:** `{negocio, ciudad, recursos}`.
- **SALIDA:** `AUDITORIA_LISTA` con `{presencia, brechas, prioridades}` (`siguiente: rama-planeacion`). **ERROR:** `AUDITORIA_ERROR`.

## 9. asistente-marketing (built-in, trabajo diario)

- **ROL:** ayuda general en español claro. Sin pipeline: atiende directo.
- **HERRAMIENTAS:** `bot-creator`, `skill-creator`, `leer_memoria`, `guardar_memoria`.
- **SALIDA:** respuesta directa (no emite evento de pipeline). **ERROR:** mensaje claro al usuario.

## 10. conocimiento-agencia (built-in, documentos internos)

- **ROL:** responde desde fuentes con cita. Nunca inventa fuente.
- **HERRAMIENTAS:** `find-a-document`, `check-a-claim`, `whats-changed`, `who-owns-this`, `leer_memoria`, `guardar_memoria`.
- **SALIDA:** respuesta con citas. **ERROR:** declara qué fuente falló.

## Reglas globales (hooks del sistema)

1. Ninguna rama publica, pauta ni gasta por sí sola → gate de Directora Humana.
2. Si una herramienta falla: guarda el error en memoria, emite `<EVENTO_ERROR>`, detente (no reintentes a ciegas).
3. Todo ENTREGABLE guarda antes en memoria (`memoria_guardada: true` obligatorio).
4. Idioma: español claro y conciso (memoria: preferencia de Directora).
5. Secrets solo por variables de entorno; nada en prompts ni eventos.

## Activación (completada 2026-10-18)

- Prompts con ROL/FLUJO/eventos en `system_prompts/<rama>.md` de las 7 ramas
  (planeacion, contenido, redes, analitica, investigacion, atencion_cliente)
  + cierre de evento en `primer_contacto/.../supervisor.md` (auditoria) y
  `orquestador/system_prompts/orquestador.md`.
- Endpoints `POST /ag-ui/rama/<nombre>` en `puente_agui/servidor.py`:
  validan token, inyectan contexto de memoria, ejecutan
  `main.py --rama <nombre> --inputs ... --modo local`, emiten el evento
  de la matriz como delta final y guardan el resultado en memoria.
  Rellenan todos los `{campos}` (CrewAI los exige; los no provistos van vacíos).
- Probado end-to-end: `atencion_cliente` → `RESPUESTA_LISTA` + `RUN_FINISHED`
  + memoria guardada y recuperada (score 0.719).
