# 🌱 Sembrar un ÁRBOL OBRERO (hijo, 24/7)

> Semilla del **obrero**: servidor vivo que produce con las 7 ramas (contenido, redes,
> analítica, investigación, atención, planeación, auditoría). No accede al micelio central.

## Pasos en la máquina del obrero

1. **Clonar / auto-sembrar la semilla**:
   ```bash
   # La semilla se auto-clona e instala deps. Si ya está clonado:
   git clone https://github.com/angelaramiz/semilla-colmena.git
   cd semilla-colmena
   ```

2. **Crear el entorno** desde la plantilla del semillero:
   ```bash
   cp semillero/obreros/plantilla.env.example .env
   # Edita: ARBOL_ID, ARBOL_NOMBRE, TAILSCALE_TOKEN, claves de APIs, JWT_SECRET_KEY
   ```

3. **Sembrar** (germinar→crecer→madurar):
   ```bash
   bash sembrar.sh cliente_01 --rol obrero --nombre "Cliente X"
   ```

4. **Verificar redes**:
   ```bash
   tailscale status
   tailscale ip -4
   ```

5. **Levantar el árbol 24/7**:
   ```bash
   docker compose --profile obrero up -d
   ```

6. **Registrarlo en el conservante/comandante** (desde el entorno controlador):
   ```bash
   uv run python main.py --registrar-arbol --arb-id cliente_01 --arb-host <IP_Tailscale> --arb-usuario root --arb-canal tailscale
   ```

> ✅ El obrero queda produciendo 24/7, unido a la tailnet, sin acceso al micelio central
> (solo su mantenimiento lo autoriza el conservante).