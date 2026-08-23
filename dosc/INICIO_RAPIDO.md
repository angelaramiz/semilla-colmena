# 🚀 INICIO RÁPIDO

## ¿Qué es esto?

**Auditor de Huella Digital**: Herramienta IA que analiza automáticamente la presencia online de negocios locales y genera reportes JSON accionables.

---

## ⚡ Configuración (5 minutos)

### 1. Crear `.env`
```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env y agregar:
# - SERPAPI_KEY (obtener en https://serpapi.com)
# - GOOGLE_API_KEY (opcional, obtener en Google Cloud)
# - O usar DATA_PROVIDER=mock para pruebas
```

### 2. Verificar Ollama (o OpenAI)
```bash
# Opción A: Ollama local
curl http://localhost:11434/api/tags
# Si no funciona, descargar: https://ollama.ai

# Opción B: OpenAI (agregar OPENAI_API_KEY en .env)
```

### 3. Instalar dependencias
```bash
uv sync
```

---

## 🎯 Ejecutar

### Opción A: GUI (recomendado)
```bash
uv run python main.py
```
✅ Se abre ventana con formularios  
✅ Log en vivo  
✅ Guardar reportes

### Opción B: CLI (una auditoría)
```bash
uv run python agente.py -n "Burgers Perronas" -c "Monterrey, Nuevo León"
```

### Opción C: CLI con archivo JSON
```bash
# Crear clientes.json
cat > clientes.json << 'EOF'
{
  "auditorias": [
    {"negocio": "Burgers Perronas", "ciudad": "Monterrey, Nuevo León"},
    {"negocio": "Dental Smarts", "ciudad": "Monterrey, NL"}
  ]
}
EOF

# Ejecutar lote desde GUI o:
# uv run python main.py --cli < clientes.json
```

---

## 📊 Resultado

Cada auditoría genera JSON como este:

```json
{
  "score": 78,
  "resumen_ejecutivo": "Presencia sólida en Google Maps pero ausencia en redes",
  "hallazgos_criticos": [
    "Google Maps actualizado (rating 4.5, 28 reseñas)",
    "Sin perfil de Instagram",
    "Sin perfil de Facebook"
  ],
  "oportunidades": [
    "Crear Instagram Business",
    "Activar WhatsApp Business",
    "Solicitar más reseñas"
  ]
}
```

---

## 🔧 Troubleshooting

| Error | Solución |
|-------|----------|
| "No se puede conectar a Ollama" | Instala Ollama o usa OpenAI (OPENAI_API_KEY) |
| "Falta SERPAPI_KEY" | Obtén en https://serpapi.com (100 búsquedas gratis) |
| "TaskGroup error" | Reinicia la app (ya está blindado, pero a veces necesita restart) |
| "ImportError: customtkinter" | `pip install customtkinter` |

---

## 📁 Archivos importantes

- `main.py` - Punto de entrada (GUI/CLI)
- `agente.py` - Lógica IA + herramientas
- `servidor_mcp.py` - Backend de búsqueda
- `gui.py` - Interfaz gráfica
- `README.md` - Documentación completa
- `FIXES_COMPLETADOS.md` - Qué se arregló

---

## 🎓 Ejemplo real

### Input:
- Negocio: "Burgers Perronas"
- Ciudad: "Monterrey, Nuevo León"

### Proceso:
1. Busca en Google Maps → extrae datos públicos
2. Verifica Instagram/Facebook → busca perfiles
3. Calcula Score Digital (0-100)
4. Genera recomendaciones

### Output:
```json
{
  "score": 82,
  "resumen_ejecutivo": "Excelente presencia en Google Maps (4.5⭐) pero NO tiene redes sociales",
  "hallazgos_criticos": [
    "✅ Google Maps completo: teléfono, horario, dirección",
    "✅ 45 reseñas positivas",
    "❌ Sin Instagram",
    "❌ Sin Facebook"
  ],
  "oportunidades": [
    "1. URGENTE: Crear Instagram con galería de burgers",
    "2. Activar WhatsApp Business (crítico en MX)",
    "3. Pedir reviews en Google Maps cada compra"
  ]
}
```

---

## 💡 Tips

- **Prueba rápida**: `DATA_PROVIDER=mock` en `.env` (datos ficticios, no gasta API)
- **Lotes grandes**: GUI maneja múltiples auditorías sin problemas
- **Reportes**: Se guardan en `reportes/` automáticamente
- **Debug**: Revisa el log en vivo para ver qué hace la IA

---

## 📞 Soporte

Revisa `README.md` para:
- Instalación detallada
- API keys (cómo obtenerlas)
- Arquitectura técnica
- Troubleshooting avanzado

---

**¿Listo?** → `uv run python main.py` 🚀
