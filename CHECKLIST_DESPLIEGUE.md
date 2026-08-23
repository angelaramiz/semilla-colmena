# 📋 Checklist de despliegue — "Manos a la obra"

Dos fases. **Primero** se inicia el árbol principal **conservante** en este entorno (local),
luego se despliega la semilla en la máquina remota (obrero/comandante).

---

## PUNTO 1 — EN ESTE ENTORNO (local): iniciar el árbol conservante

El conservante es la **jerarquía más alta** (dev/arquitecto): autoriza el mantenimiento del
micelio y tiene acceso completo a la estructura. Se inicia ANTES de sembrar las máquinas remotas.

### 1.1 Configurar el rol conservante en `.env`
```bash
# Verifica que el .env local tenga rol conservante
ARBOL_ROL=conservante
```
Si no está, agrega o ajusta la línea `ARBOL_ROL=conservante` en tu `.env`.

### 1.2 Confirmar la DB en la nube (Supabase)
- [ ] `DATABASE_URL` apunta a Supabase (`db.nyaocuuxmihifzqbpjqd.supabase.co`)
- [ ] Las tablas `users`, `aprobaciones`, `arboles_remotos` existen (se crearon con `init_db`)

```bash
uv run python -c "from db import init_db; init_db()"
```

### 1.3 Crear/usar el usuario conservante (jerarquía más alta)
```bash
# Si aún no existe:
uv run python -c "from db import SessionLocal; from auth import crear_usuario; \
db=SessionLocal(); \
crear_usuario(db, 'conservante', 'angelaramiz22@gmail.com', 'TU_CLAVE_SEGURA', role='conservante', status='approved'); \
db.close()"
```
- [ ] El usuario `conservante` existe con rol `conservante` y `approved`
- [ ] Cambia la contraseña si usaste una temporal

### 1.4 Definir el token del panel del conservante
```bash
# En .env:
CONSERVANTE_WEB_TOKEN=TU_TOKEN_SECRETO
CONSERVANTE_WEB_PORT=8002
```

### 1.5 Arrancar el panel del conservante (segundo plano)
```bash
uv run uvicorn conservante_web:app --host 127.0.0.1 --port 8002
```
- [ ] El panel responde en http://localhost:8002
- [ ] Pide `X-Conservante-Token` (el que pusiste)
- [ ] Puedes ver `/api/mantenimiento/pendientes` (aprobaciones de mantenimiento)

> ✅ El **conservante** ya está activo y escuchando solicitudes de mantenimiento del micelio.
> Cualquier obrero remoto que pida permiso lo verá aquí.

---

## PUNTO 2 — MÁQUINA REMOTA: sembrar y operar

### 2.1 Requisitos de la máquina remota
- [ ] Git, `uv` o `pip`, Docker + Compose, `curl`, `ssh-keygen`(¿opcional?)
- [ ] (Opcional) Ollama si quieres modelo local

### 2.2 Clonar la semilla
```bash
git clone https://github.com/angelaramiz/semilla-colmena.git
cd semilla-colmena
```

### 2.3 Generar el `.env` desde la plantilla
```bash
cp .env.example .env
# Editar .env con valores propios (claves, rol, tokens, DB, TAILSCALE_TOKEN)
nano .env    # o vim/vi
```
Campos mínimos según rol:
- `ARBOL_ID`, `ARBOL_ROL` (obrero en una máquina de campaña), `ARBOL_NOMBRE`
- `OPENROUTER_API_KEY`, `SERPAPI_KEY`/`SERPER_API_KEY`, `GOOGLE_API_KEY`
- `DATABASE_URL` (Supabase), `TAILSCALE_TOKEN` (para red privada)
- `ADMIN_PASSWORD`, `DIRECTORA_PASSWORD`, `JWT_SECRET_KEY`, `CONSERVANTE_WEB_TOKEN`
> ⚠️ Define `JWT_SECRET_KEY`, `CONSERVANTE_WEB_TOKEN`, `TAILSCALE_TOKEN` para que no queden vacíos.

### 2.4 Ejecutar la semilla (germinar → crecer → madurar)
```bash
# Árbol hijo (obrero) que produce 24/7:
bash sembrar.sh cliente_01 --rol obrero --nombre "Cliente X"

# O si este nodo será el comandante de operaciones (respaldado por el conservante):
bash sembrar.sh cmd_01 --rol comandante
```
`seembrar.sh` hará: instalar deps Python → ollama (si hay) → CodeGraph → **Tailscale** → **key SSH** → `.env`/`/shared`/DB → `manifiesto.yaml` → health

- [ ] Terminó sin errores críticos ("Árbol XXX MADURO")
- [ ] `/shared` creado
- [ ] `manifiesto.yaml` generado según rol

### 2.5 Verificar redes (Tailscale / SSH)
```bash
# Tailscale:
tailscale status                      # debe mostrar el nodo en la tailnet
tailscale ip -4                       # IP privada del árbol
# SSH (alternativa):
ls -l ~/.ssh/id_ed25519.pub           # clave pública generada
cat ~/.ssh/id_ed25519.pub             # → autoriza en el comandante/conservante
```
- [ ] `tailscale status` OK
- [ ] (Alternativa) clave SSH pública visible para autorizarla

### 2.6 Levantar los servicios con Docker
```bash
# Obrero (servidor vivo 24/7):
docker compose --profile obrero up -d

# Comandante (panel de control / ops):
docker compose --profile comandante up -d
```
- [ ] `docker compose ... up -d` sin errores
- [ ] Puerto 8000 (obrero) / 8001 (comandante) escuchando

### 2.7 Registrar el nodo en el inventario del conservante (local)
Desde el entorno del conservante (el que tiene el inventario con `--arboles`):
```bash
uv run python main.py --registrar-arbol --arb-id cliente_01 --arb-host <IP_Tailscale> --arb-usuario root --arb-canal tailscale
uv run python main.py --arboles          # confirmar
```
- [ ] El nodo aparece en `--arboles`

### 2.8 Conectar el panel del conservante para operar
```bash
# Desde el local:
uv run uvicorn conservante_web:app --host 0.0.0.0 --port 8002   # o Docker
```
- [ ] Puedes `ping`/`estado`/`upgrade` del nodo remoto
- [ ] Las solicitudes de mantenimiento del micelio del nodo llegan a `/pendientes`

---

## ✅ Checklist final
- [ ] Conservante activo en local (red.), rol `conservante`, panel en :8002 con token
- [ ] DB conectada (Supabase) con el usuario conservante
- [ ] Máquina remota clonada, sembrada, unida a Tailscale/SSH
- [ ] Servicios Docker arriba (obrero/comandante según rol)
- [ ] Nodo registrado y controlable desde el conservante
- [ ] Micelio del nodo solicita permiso y el conservante aprueba (flujo de autorización)

---

*El conservante es la **mayor jerarquía** que autoriza mantenimiento; el resto de nodos
(obrero, comandante, heredero) operan contra él.*