# 🌱 Semilla Colmena — Agencia de Marketing Autónoma (Mente Colmena)

Sistema multi-agente autónomo (CrewAI + FastMCP + Ollama/OpenRouter) organizado como
**colmena**: una semilla germina árboles (instancias) que operan 24/7 conectados por
red privada Tailscale, con paneles web por rol y registro central en Supabase.

## 🏗️ Arquitectura (resumen)

| Capa | Código | Función |
|------|--------|---------|
| Semilla | `core/`, `sembrar.ps1/.sh` | Enrutador LLM, clasificador, manifiesto, bootstrap de árboles |
| Tronco | `orquestador/` | Orquestador + pipeline de campañas |
| Ramas obreras | `contenido/`, `redes/`, `analitica/`, `investigacion/`, `atencion_cliente/`, `planeacion/`, `auditoria/` (`primer_contacto/`) | Agentes CrewAI + servidores MCP |
| Micelio | `micelio/` | Mantenimiento (salud/reparar, con autorización del Conservante) |
| Red | `comunicacion/` + Tailscale/SSH | Comandante controla árboles hijos |
| Paneles | `:8000` árbol · `:8001` comandante · `:8002` conservante | FastAPI/Uvicorn |

Modelos: **Ollama local** (rutina — `qwen3:4b`, `qwen2.5:1.5b`) + **OpenRouter** (estrategia,
con rotación y fallback). Búsqueda de código: **CodeGraph** (`.codegraph/`).

## 🌳 Árboles desplegados

| Árbol | Máquina | Rol | Paneles |
|-------|---------|-----|---------|
| `conservante_principal` | Esta PC | conservante | `:8002` Conservante · `:8000` Árbol |
| `arbol_obrero_01` | yazminlap `100.93.118.23` | obrero | `:8000` (+ `/arbol.html`) |
| `cmd_01` | ruti `100.114.102.85` | comandante | `:8001` Comandante · `:8000` |

Registro vivo: tabla Supabase `arboles_remotos` (visible en el Conservante con estado EN LÍNEA/OFFLINE).

## 🚀 Inicio rápido

**En cualquier árbol Windows:** doble clic a **`Levantar Colmena.bat`** (Escritorio) —
actualiza código (`fetch+reset`), sincroniza dependencias (`uv sync`), verifica
Tailscale/Ollama, arranca servicios 24/7 y abre el panel. También corre solo al
iniciar sesión (acceso directo en `Startup/`).

```bash
# Alternativas por terminal
uv run python main.py --orquestador "instrucción"    # Tronco
uv run python main.py --campana "objetivo"           # pipeline de campaña
uv run python main.py --rama <nombre> --inputs '{}'  # rama individual
uv run python main.py --micelio                      # mantenimiento
uv run python main.py --clasificar "texto"           # clasificación
uv run python main.py --arboles                      # inventario
uv sync                                              # dependencias
```

**Modos de ejecución** (panel Auditor → *Modo de Ejecución*, o `main.py -m`):
`local` (Ollama) · `produccion` (cloud) · `obrero` (vía `core/registro_ramas`, LLM local).

## 📦 Semillas (ejecutables Windows, solo locales — gitignored)

| Exe | Germina | Generar con |
|-----|---------|-------------|
| `semilla-colmena.exe` | obrero (`arbol_obrero_01`) | `empaquetado/empaquetar.ps1` |
| `semilla-comandante.exe` | comandante (`cmd_01`) | `empaquetado/empaquetar.ps1 -ArbolId cmd_01 -Rol comandante -Salida semilla-comandante.exe` |
| `preparar-arbol.exe` | — (prepara máquina: OpenSSH + usuario + firewall + IP) | `empaquetado/empaquetar_preparar.ps1` |

Los `.exe` hornean `semillero/heredado.env` (credenciales reales, gitignored).
Enviar por Taildrop: `tailscale file cp <exe> <nodo>:` → recibir con
`tailscale file get ([Environment]::GetFolderPath('Desktop'))`.

## ⚙️ Variables clave (`.env`, gitignored — ver `.env.example`)

`AUTO_OPEN_BROWSER` (abrir panel al arrancar, solo local) ·
`LEVANTAR_URL` (qué abre *Levantar*; vacío = `:8000`) ·
`DATABASE_URL` / `SUPABASE_URL` · `TAILSCALE_TOKEN` ·
`CONSERVANTE_WEB_TOKEN` / `COMANDANTE_WEB_TOKEN` · `JWT_SECRET_KEY`.

## 📁 Estructura

```
agen_mrk/
├── core/            # semilla: llm_router, clasificador, registro_ramas, manifiesto, auto_open
├── orquestador/     # tronco + pipeline de campaña
├── contenido/ redes/ analitica/ investigacion/ atencion_cliente/ planeacion/
├── primer_contacto/ # rama auditoría (auditor huella digital)
├── micelio/         # mantenimiento        comunicacion/     # SSH/Tailscale
├── web_server.py    # panel árbol :8000 (+ /arbol.html: métricas y tareas de estación)
├── comandante_web.py conservante_web.py     # paneles :8001 / :8002
├── levantar.ps1     # botón de encendido (actualiza + arranca todo)
├── sembrar.ps1/.sh  # germinación          empaquetado/      # SFX + preparar
├── static/          # frontend auditor + arbol.html
├── db.py auth.py main.py gui.py
└── .agents/         # protocolo multi-agente Gate (TPM ↔ Dev Jr) + memoria
```

## 📚 Docs

- `DESPLIEGUE.md` — guía operativa completa · `CHECKLIST_DESPLIEGUE.md`
- `ARQUITECTURA_SEMILLA_ARBOL.md` · `ARQUITECTURA_AGENCIA.md` · `AGENTS.md` (reglas para IAs)
- `.agents/` — protocolo Gate/DB-TO-DO-LIST, roles y memoria

## 🔒 Seguridad

`.env`, `heredado.env`, `*.exe`, `*.db` están gitignored; pre-commit `scripts/check_secrets.py`
bloquea secretos. El micelio no modifica árboles sin el Conservante; los gates críticos
los aprueba solo la Directora Humana.
