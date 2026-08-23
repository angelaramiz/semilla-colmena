# 🌳 Sembrar el Árbol COMANDANTE (directora de mercadotecnia)

> Semilla del **comandante**: opera campañas y ramas, micelio limitado (solo errores/upgrades).
> No accede a estructura/código (403). El conservante la siembra.

## Pasos en la máquina del comandante

1. **Clonar o auto-sembrar** la semilla:
   ```bash
   # Opción A: la semilla se auto-clona al ejecutar sembrar.sh desde donde sea:
   #   (descarga el repo y se siembra; ver Uso de sembrar.sh)
   # Opción B: clonar manualmente el repo:
   git clone https://github.com/angelaramiz/semilla-colmena.git
   cd semilla-colmena
   ```

2. **Preparar el `.env`** desde la plantilla del semillero:
   ```bash
   cp semillero/comandante/plantilla.env.example .env
   # Edita: ARBOL_ID, TAILSCALE_TOKEN, COMANDANTE_WEB_TOKEN, JWT_SECRET_KEY, claves de APIs
   ```

3. **Sembrar** (germinar→crecer→madurar):
   ```bash
   bash sembrar.sh cmd_principal --rol comandante --nombre "Comandante — Directora de Mercadotecnia"
   ```

4. **Verificar redes**:
   ```bash
   tailscale status                 # en la tailnet
   tailscale ip -4
   ```

5. **Levantar el panel del comandante** (operaciones):
   ```bash
   docker compose --profile comandante up -d     # o:
   uv run uvicorn comandante_web:app --host 0.0.0.0 --port 8001
   ```

6. **Registrar obreros** en el inventario (los que la directora operará):
   ```bash
   uv run python main.py --registrar-arbol --arb-id cliente_01 --arb-host <IP_Tailscale> --arb-usuario root --arb-canal tailscale
   uv run python main.py --arboles
   ```

> ✅ El comandante (directora de mercadotecnia) queda operando campañas, con panel en :8001
> y micelio limitado (salud/upgrades), SIN acceso a estructura/código.