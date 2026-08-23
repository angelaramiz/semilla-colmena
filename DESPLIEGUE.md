# 🚀 Despliegue de la Colmena — Guía operativa completa

Cómo levantar una agencia de marketing autónoma (mente colmena) desde `git clone` hasta
una colmena operando: **semilla → árboles → ramas → micelio → comandante/conservante**.

---

## 0. Concepto (30 segundos)

| Rol | Nodo | Uptime | Acceso |
|-----|------|--------|--------|
| **Obrero** | Árbol hijo | 🟢 24/7 | Produce (7 ramas) |
| **Comandante** | Árbol principal | 🔵 bajo demanda | Campañas + micelio limitado (errores/upgrades) |
| **Conservante** | Árbol principal | 🔵 bajo demanda | **Dev/arquitecto**: micelio completo + estructura |
| **Heredero** | Respaldo del comandante | ⚫ frío | Failover |
| **Micelio** | Agente de mantenimiento | 🔵 bajo demanda | Conecta, diagnostica y mantiene los árboles |

### 🎯 Objetivo principal (misión de semillas + micelio)

1. **Siempre conectado y operando** (aunque la máquina se apague y encienda).
2. **Siempre en buena salud**: el micelio ejecuta **diagnósticos de estado sobre sí mismo
   y sobre su árbol asignado**; si detecta errores o falta de conexión, solicita permiso de
   mantenimiento al **CONSERVANTE**.
3. **Sin modificación sin autorización**: el micelio NO altera su árbol sin la aprobación
   del **CONSERVANTE** (jerarquía más alta). Sistema auth para operadores.
4. **Siempre conectado a la red privada** y en comunicación con los árboles.

Modelos: **Ollama local** (rutina, `qwen3:27b`) + **OpenRouter** (estrategia, con rotación
automática y fallback a Ollama). Búsqueda de código: **CodeGraph** (`.codegraph/`).

---

## 1. Requisitos de la máquina

- **Git**
- **Python 3.12+** con `uv` (o `pip`)
- **Docker** + Docker Compose (despliegue por contenedor)
- **Ollama** (opcional, para el modelo local `qwen3:27b`)
- **npm** (opcional, para instalar el CLI de CodeGraph)
- **Tailscale** / llaves SSH (opcional, para comunicar el comandante con los obreros)

Verificación rápida:

```bash
git --version; uv --version 2>/dev/null || python --version
docker --version 2>/dev/null
ollama --version 2>/dev/null || echo "ollama no instalado (opcional)"
npm --version 2>/dev/null || echo "npm no instalado (opcional)"
```

---

## 2. Sembrar un árbol (germinar → crecer → madurar)

La semilla crea **sus propias dependencias** e indexa su código. `sembrar.sh` hace las
3 fases del ciclo de vida.

```bash
# Clonar la semilla
git clone <repo_semilla> arbol_cliente_01
cd arbol_cliente_01

# Sembrar según el rol deseado
bash sembrar.sh cliente_01 --rol obrero        --nombre "Cliente X"
bash sembrar.sh cmd_01        --rol comandante
bash sembrar.sh dev_01        --rol conservante   # exclusivo del arquitecto/dev
bash sembrar.sh backup_01     --rol heredero --heredero-de cmd-01.tailnet.ts.net
```

Lo que hace por ti:
1. **Germinar**: instala dependencias (`uv sync`/pip), descarga `qwen3:27b` (si hay Ollama)
   e instala/indexa **CodeGraph** (`npm install` + `codegraph init`).
2. **Crecer**: crea `.env`, `/shared`, la DB, y los roles (admin + Directora).
3. **Madurar**: genera `manifiesto.yaml` (Trinity) y hace health check.

Resultado: `.env` + `/shared` + `app_database.db` + `manifiesto.yaml` + `.codegraph/`.

> ⚠️ Nunca copiar `.env` ni `/shared` entre árboles: cada árbol es aislado.

### DB en la nube (Supabase) — opcional

Por defecto cada árbol usa SQLite local (`app_database.db`). Para centralizar el estado
(auth, aprobaciones, memoria, inventario) en **Supabase** (la "colmena" en la nube):

1. En tu proyecto Supabase, copia la **connection string Postgres**:
   `Settings → Database → Connection string → URI`.
2. Pégala en `.env`:
   ```env
   DATABASE_URL=postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres
   SUPABASE_URL=https://<project>.supabase.co
   ```
3. Crea las tablas ejecutando (usa `init_db`, que crea `users`, `aprobaciones`,
   `arboles_remotos`):
   ```bash
   uv run python -c "from db import init_db; init_db()"
   ```

> ⚠️ La **publishable key** de Supabase es para el SDK del cliente (con RLS), NO para que
> el driver de `db.py` se conecte. La conexión real usa la **connection string** con password.

---

## 3. Roles y sus servicios

| Rol | Qué corre | Acceso |
|-----|-----------|--------|
| **obrero** | `web_server.py` (Tronco + 7 ramas) | puerto 8000 |
| **comandante** | `comandante_web.py` (panel de control) | puerto 8001 |
| **conservante** | `conservante_web.py` (panel dev) + micelio | puerto 8002 |
| **micelio** | `main.py --micelio` (mantenimiento) | bajo demanda |

El **comandante** opera campañas y ramas, pero **no** accede al código/estructura
(`aplicar_parche`, `reparar`, `sincronizar` → **403**). El **conservante** es el único
con acceso completo al micelio y a la estructura.

---

## 4. Desplegar con Docker (cualquier máquina)

Un solo `docker-compose.yml` sirve para toda la colmena (se selecciona el rol por perfil).

```bash
# Árbol obrero (servidor vivo 24/7)
docker compose --profile obrero up -d

# Comandante (panel de control, bajo demanda)
docker compose --profile comandante up -d

# Conservante (panel del arquitecto/dev)
docker compose --profile conservante up -d

# Ollama local (opcional, requiere GPU/RAM)
docker compose --profile ollama up -d

# Micelio (mantenimiento bajo demanda)
docker compose --profile micelio up -d
```

El contenedor incluye todas las dependencias (filtra `pywin32`, que es Windows-only),
monta `/shared` y (si hay npm) indexa CodeGraph.

---

## 5. Levantar la colmena completa (multi-nodo)

Topología recomendada: **1 comandante + 1 heredero + N obreros**, cada uno en su máquina,
comunicados por **Tailscale/SSH** (canal privado).

```bash
# 1) En el comandante, registrar cada obrero (y el heredero)
uv run python main.py --registrar-arbol --arb-id cliente_01 --arb-host cliente-01.tailnet.ts.net --arb-usuario root --arb-canal tailscale

# 2) Verificar el inventario
uv run python main.py --arboles

# 3) Diagnosticar / actualizar un obrero (desde el panel del comandante)
#    Panel: http://localhost:8001  → botones Ping / Estado / Upgrade
```

Failover del heredero (si el comandante cae):

```bash
uv run python -c "from comunicacion.comandante_mcp import reclamar_comandancia; print(reclamar_comandancia())"
```

---

## 6. Operar la colmena

| Acción | Cómo |
|--------|------|
| Clasificar una instrucción | `uv run python main.py --clasificar "publica la campaña"` |
| Delegar a una rama | `uv run python main.py --rama contenido --inputs '{"tema":"cafe"}'` |
| Ejecutar una campaña (pipeline) | `uv run python main.py --campana "Lanzar Cafe en Monterrey" --inputs '{"marca":"La Parroquia","ciudad":"Monterrey"}'` |
| Mantenimiento (micelio) | `uv run python main.py --micelio` |
| Consultar el grafo de código | `codegraph explore "estructura del orquestador"` |
| Aprobar acciones críticas | Panel web del obrero/comandante → `/aprobaciones` |

---

## 7. Verificación final (checklist)

- [ ] `.env` generado con `ARBOL_ROL` y claves únicas por árbol
- [ ] `/shared` + DB creados
- [ ] `manifiesto.yaml` generado según rol
- [ ] `.codegraph/` indexado (CodeGraph)
- [ ] Modelos: `qwen3:27b` (local) y `z-ai/glm-5.2:free` + fallbacks (OpenRouter)
- [ ] Panel del comandante en `:8001` (ping/estado/upgrade de obreros)
- [ ] Panel del conservante en `:8002` (mantenimiento + grafo de código)
- [ ] Gate de aprobación: una acción crítica se bloquea hasta la Directora
- [ ] Micelio con permisos: comandante **403** en estructura; conservante acceso completo

---

## 8. Poda y escalado

- **Añadir un obrero**: `sembrar.sh <id> --rol obrero` + `--registrar-arbol` en el comandante.
- **Actualizar un nodo**: panel del comandante → `Actualizar` (git) o `conservante_web` → parche.
- **Retirar un árbol**: detener servicios + respaldar/eliminar su `/shared` y su DB; la semilla queda intacta.
- **Nunca** compartir `.env`, `/shared` ni la API key de OpenRouter entre árboles.