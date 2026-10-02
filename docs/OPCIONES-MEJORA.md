# OPCIONES DE MEJORA — Catálogo

> Fecha: 2026-10-01 · Origen: propuestas evaluadas contra el stack real (CrewAI + Ollama + OpenRouter + Supabase + Tailscale + SearXNG).
> Cada opción es open source y auto-hospedable. Este archivo describe QUÉ hace cada una.
> El plan de implementación progresiva (pros, contras, por qué y cuándo) está en `PLAN-MEJORA-PROGRESIVA.md`.

## A. Flujo de trabajo y herramientas

### A1. Langfuse — Observabilidad de LLM
Plataforma de trazas y métricas para llamadas a modelos: registra cada invocación (prompt, respuesta, tokens, costo, latencia) agrupada por crew, etapa y árbol. Permite comparar modelos, detectar degradaciones (como un modelo que deja de ser gratis o un timeout nuevo) y auditar qué hizo cada agente. Se integra con CrewAI/OpenAI-client en minutos y se auto-hospeda con Docker.

### A2. n8n — Automatización y pegamento
Orquestador visual de flujos (workflows por nodos): programa campañas recurrentes, dispara `ejecutar_campana` por webhook o calendario, envía el gate de aprobación a Telegram/WhatsApp, publica piezas aprobadas y conecta la agencia con cientos de servicios. Reemplaza scripts sueltos de pegamento con flujos versionables y reintentables.

### A3. Qdrant — Memoria vectorial (documentos)
Base de datos vectorial liviana: guarda dossieres, piezas, reportes y manifiestos como embeddings para recuperación semántica (RAG). Las ramas de investigación y planeación podrían consultar el trabajo pasado de la agencia en vez de empezar de cero en cada campaña. Cliente Python oficial, API simple, corre en un contenedor.

### A4. Mautic — Automatización de marketing
Suite de marketing automation: email marketing, segmentación de contactos, lead nurturing, páginas de aterrizaje y seguimiento de campañas. Es el eslabón de "exposición" real: hoy la etapa 4 de la campaña es solo un gate que no emite nada; Mautic sería el destino operativo de lo aprobado.

### A5. Matomo — Analítica web propia
Plataforma de analítica sin terceros: mide tráfico, fuentes y conversiones de los sitios de clientes con los datos bajo control propio. Alimentaría la rama analítica con métricas reales en vez del `metricas_json` manual actual.

### A6. Uptime Kuma — Monitoreo de servicios
Monitor de disponibilidad liviano: hace ping/HTTP a `:8000`, `:8001`, `:11434` de cada árbol y avisa (Telegram, etc.) cuando algo cae. Evita descubrir caídas por casualidad. Setup de minutos en Docker.

### A7. Listmonk / MinIO — Newsletter y almacenamiento
Listmonk: envío de newsletters y listas de correo simple, alternativa ligera si Mautic resulta excesivo. MinIO: almacenamiento de objetos compatible S3 para piezas, borradores y artefactos de campaña, alternativa al `/shared` local de cada árbol.

## B. Entorno del agente IA

### B1. mem0 — Memoria persistente del agente
Capa de memoria para agentes: recuerda preferencias de la Directora, decisiones de campañas pasadas y contexto entre sesiones y crews. Usa el Ollama local para embeddings. Diferencia entre un agente que ejecuta tareas aisladas y uno que acumula criterio.

### B2. AnythingLLM — Chat RAG listo para usar
Aplicación de chat con retrieval sobre documentos usando el Ollama local, sin programar. La Directora podría consultar manifiestos, reportes y entregables en lenguaje natural sin tocar paneles ni APIs.

### B3. mcpo / ToolHive — Gateway MCP
Centraliza los `servidor_mcp.py` dispersos por rama en un solo gateway con autenticación y logs. `mcpo` además expone las herramientas como API OpenAPI, consumible por n8n u otros sistemas sin cliente MCP.

### B4. E2B — Sandbox de ejecución
Entorno aislado por ejecución para código generado o acciones del agente: si algo sale mal, muere en la sandbox y no en el árbol. Relevante porque el comportamiento de siembra ya fue marcado una vez por Defender como sospechoso.

### B5. LibreChat / Open WebUI — Frontend de chat multi-modelo
Interfaces de chat contra Ollama + OpenRouter, con usuarios y conversaciones. Operación diaria más usable que curl a los paneles para la Directora y el equipo.

## C. Árboles y semillas

### C1. Ansible — Siembra declarativa
Gestión de configuración idempotente: describe el estado deseado del árbol (paquetes, servicios, tareas, firewall) en playbooks versionables. Correrlo N veces da el mismo resultado, a diferencia del `sembrar.ps1` imperativo actual (368 líneas, 6 rondas de parches en el lab). Es el reemplazo natural del sistema de siembra.

### C2. Packer (+ Vagrant) — Imágenes versionadas
Construye la imagen base del árbol una vez (Windows desatendido, dependencias, Guest Additions) y versionada. Sembrar pasa de "instalar 2h + OOBE manual" a "clonar imagen + Ansible en minutos". Elimina para siempre el dolor vivido con la OOBE de Windows 11 24H2.

### C3. Headscale — Malla propia
Servidor de coordinación Tailscale-compatible y auto-hospedado: misma red `100.x`, mismos clientes, pero bajo control propio en vez de depender de la infraestructura gratuita de un tercero. Soberanía sobre la red que une a todos los árboles.

### C4. SOPS + age — Secretos cifrados en git
Cifra los `.env` dentro del repositorio: commiteable y auditable, cada árbol descifra con su llave. Mantiene la regla "cero secretos en claro" mientras elimina el malabarismo actual de `vm.env` fuera del repo.

### C5. Restic / Kopia — Respaldo de árboles
Backups cifrados e incrementales del árbol a cualquier destino (disco externo, S3, otro nodo). Los snapshots de VirtualBox son locales y frágiles; esto salva de un disco muerto.

### C6. Plane — Gestión de trabajo
Gestor de proyectos self-hosted estilo Jira/Linear que reflejaría el Kanban actual (`Pending → onProces → Audit`) con vistas, responsables y fechas, visible para la Directora sin entrar a archivos markdown.
