# 🔍 Auditor de Huella Digital - Agencia de Marketing MCP

Auditor autónomo de presencia digital para pequeños negocios locales en México.

## 🎯 Características

- ✅ **Búsqueda en Google Maps**: Extrae datos públicos de negocio (rating, reseñas, dirección, teléfono)
- ✅ **Verificación de redes sociales**: Instagram y Facebook
- ✅ **Score de Madurez Digital**: Calificación 0-100 basada en criterios de marketing
- ✅ **Análisis inteligente con IA**: CrewAI con Llama 3.1 local o OpenAI
- ✅ **Interfaz gráfica**: GUI con CustomTkinter para facilidad de uso
- ✅ **Modo CLI**: Para automatización y scripts
- ✅ **Procesamiento por lote**: Audita múltiples negocios en una sesión

## 🚀 Instalación

### Prerequisites
- **Python 3.11+**
- **uv** (gestor de dependencias): https://docs.astral.sh/uv/getting-started/
- **Ollama** (para LLM local) o API key de OpenAI

### Setup

```bash
# 1. Clonar/descargar el proyecto
cd agen_mrk

# 2. Instalar dependencias
uv sync

# 3. Configurar variables de entorno
cp .env.example .env   # Si existe
# O crear .env manualmente:
```

### Archivo `.env`

```env
# === API Keys ===
GOOGLE_API_KEY=AIzaSy...          # Google Places API (opcional, fallback a SerpAPI)
SERPAPI_KEY=...                    # SerpAPI (si usas como proveedor)
OPENAI_API_KEY=sk-...              # Solo si usas OpenAI en lugar de Ollama

# === LLM Local (Ollama) ===
USE_LOCAL_LLM=true
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=llama3.1:8b        # O qwen2.5:7b, mistral, etc.

# === Proveedor de datos ===
DATA_PROVIDER=serpapi              # serpapi, google, o mock
```

## 📖 Uso

### Modo GUI (Recomendado para usuarios finales)

```bash
uv run python main.py
```

Abre una ventana con:
- **Tab 1**: Auditoría individual (un negocio)
- **Tab 2**: Auditoría por lote (múltiples negocios desde JSON)
- **Consola en vivo** con colores y resultados

### Modo CLI (Para scripts/automatización)

```bash
# Auditoría individual con salida en pantalla
uv run python agente.py -n "Burgers Perronas" -c "Monterrey, Nuevo León"

# Guardar reporte en JSON
uv run python agente.py -n "Dental Smarts" -c "Monterrey, NL" -o reportes/dental.json

# Modo interactivo
uv run python agente.py -i
```

### Auditoría por lote (GUI o CLI)

**Archivo `clientes.json`**:
```json
{
  "auditorias": [
    {"negocio": "Burgers Perronas", "ciudad": "Monterrey, Nuevo León"},
    {"negocio": "Dental Smarts", "ciudad": "Monterrey, NL"},
    {"negocio": "Café La Esquina", "ciudad": "San Pedro Garza García, NL"}
  ]
}
```

**En GUI**: Selecciona archivo → Ejecutar Lote

## 📊 Resultado

Cada auditoría genera un JSON con:

```json
{
  "score": 75,
  "resumen_ejecutivo": "Negocio bien establecido con buena presencia en Google Maps pero ausente en redes sociales",
  "hallazgos_criticos": [
    "Google Maps actualizado con teléfono y horario",
    "Sin perfil de Instagram",
    "Sin presencia en Facebook"
  ],
  "oportunidades": [
    "Crear perfil de Instagram enfocado en portfolio de trabajo",
    "Implementar WhatsApp Business para contacto directo",
    "Publicar reseñas en Google Maps"
  ]
}
```

## 🔧 Troubleshooting

### Error: "No se puede conectar a Ollama"

Verifica que Ollama esté corriendo:
```bash
curl http://localhost:11434/api/tags
```

Si no funciona, instala Ollama: https://ollama.ai

### Error: "Falta SERPAPI_KEY / GOOGLE_API_KEY"

- **SerpAPI**: Registra en https://serpapi.com (gratis primeras 100 búsquedas)
- **Google Places API**: Habilita en https://cloud.google.com/console

O usa modo `mock` cambiando `DATA_PROVIDER=mock` en `.env`

### Error: "TaskGroup" o "unhandled errors"

El servidor MCP falló. Soluciones:
1. Verifica que el archivo `servidor_mcp.py` existe
2. Reinicia la aplicación
3. Revisa que todas las excepciones están siendo atrapadas internamente

## 📁 Estructura del Proyecto

```
agen_mrk/
├── main.py                 # Punto de entrada (GUI/CLI)
├── gui.py                  # Interfaz gráfica (CustomTkinter)
├── agente.py              # Orquestación CrewAI + llamadas MCP
├── servidor_mcp.py        # Servidor de herramientas MCP
│
├── context/               # Contexto del proyecto
│   ├── context.md         # Arquitectura técnica
│   └── chat-*.txt         # Notas contextuales
│
├── reportes/              # Resultados de auditorías (JSON)
├── salida/                # Outputs adicionales
│
├── .env                   # Configuración (NO subir a git)
├── .gitignore
├── pyproject.toml         # Dependencias
└── README.md              # Este archivo
```

## 🔗 Dependencias Principales

- **crewai**: Orquestación de agentes IA
- **fastmcp**: Model Context Protocol (herramientas para IA)
- **requests**: Llamadas HTTP a APIs
- **customtkinter**: GUI moderna
- **ollama**: LLM local (instalable aparte)

## 📝 Licencia

Este proyecto es de código abierto. Úsalo libremente.

## 🤝 Contribuciones

¿Sugerencias o mejoras? Abre un issue o PR.

---

**Última actualización**: 9 de mayo de 2026  
**Versión**: 1.0 (MVP)  
**Estado**: 🟢 Funcional con blindaje de errores
