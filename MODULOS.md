# 📦 Estructura Modular de Áreas de Agentes

## 🎯 Visión General

El proyecto está organizado en **módulos especializados** (áreas), cada uno con sus propios agentes, herramientas y contexto. Esto permite:

✅ **Escalabilidad**: Agregar nuevas áreas sin afectar existentes  
✅ **Mantenibilidad**: Código separado y organizado  
✅ **Reutilización**: Herramientas compartidas entre áreas  
✅ **Flexibilidad**: Cada área usa su propio LLM y configuración  

## 📁 Estructura Estándar de un Módulo

Cada área de agentes sigue este patrón:

```
agen_mrk/
├── area_agentes/                     # Nueva área
│   ├── __init__.py                   # Exports públicos
│   ├── agente.py                     # Orquestador CrewAI
│   ├── servidor_mcp.py               # Herramientas MCP
│   ├── system_prompts/
│   │   ├── agente1.md
│   │   ├── agente2.md
│   │   └── ...
│   └── context/
│       └── reglas_generales.md
└── main.py                           # Unificador (CLI/GUI)
```

## 🏢 Módulos Existentes

### 1️⃣ `primer_contacto/` ✅ (Implementado)

**Descripción**: Departamento de investigación previa para primer contacto con clientes

**Agentes**:
- 🔍 Investigador (Reputación web)
- 🔧 Auditor (Google Maps + Redes)
- 📊 Analista (Competencia)
- 🎯 Supervisor (Síntesis + Propuesta)

**Entrada**: Nombre de negocio + Ciudad  
**Salida**: JSON triple (cliente_gancho, interno_mercadologa, interno_ingeniero)

**Ubicación**: [`primer_contacto/`](primer_contacto/)

---

## 🚀 Cómo Agregar una Nueva Área

### Paso 1: Crear estructura de directorios

```bash
mkdir -p nueva_area/system_prompts
mkdir -p nueva_area/context
touch nueva_area/__init__.py
```

### Paso 2: Crear `agente.py`

Usa este template:

```python
# nueva_area/agente.py
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import os, json

def get_local_llm(modo: str) -> LLM:
    """Configurar LLM"""
    # ... (copiar de primer_contacto/agente.py)
    pass

class PersistentMCPClient:
    """Cliente MCP persistente"""
    # ... (copiar de primer_contacto/agente.py)
    pass

def setup_crew(modo: str) -> Crew:
    """Crear crew con agentes especializados"""
    # Definir agentes aquí
    pass

def extract_crew_result(output):
    """Extraer resultado"""
    # ... (copiar de primer_contacto/agente.py)
    pass
```

### Paso 3: Crear herramientas MCP en `servidor_mcp.py`

```python
# nueva_area/servidor_mcp.py
from fastmcp import FastMCP
import os, json

mcp = FastMCP("AreaEspecializada")

@mcp.tool()
def herramienta_1(param: str) -> str:
    """Descripción de herramienta 1"""
    # Implementación
    pass

if __name__ == "__main__":
    mcp.run()
```

### Paso 4: Crear system_prompts

```bash
# nueva_area/system_prompts/
agente1.md
agente2.md
agente3.md
```

Cada archivo con el backstory (cómo debe pensar el agente).

### Paso 5: Crear contexto global

```bash
# nueva_area/context/
reglas_generales.md
# Incluir reglas, tonos, criterios de evaluación
```

### Paso 6: Crear `__init__.py`

```python
# nueva_area/__init__.py
"""
Módulo: Nueva Área

[Descripción breve]
"""

__version__ = "1.0.0"

from .agente import setup_crew, extract_crew_result

__all__ = ["setup_crew", "extract_crew_result"]
```

### Paso 7: Actualizar `main.py`

Agregar comandos para la nueva área:

```python
# En main.py
def main():
    parser = argparse.ArgumentParser()
    
    # Agregar subcomandos
    subparsers = parser.add_subparsers(dest="area", help="Área de agentes")
    
    # Subcomando para primer_contacto
    primer_subparser = subparsers.add_parser("primer-contacto", help="Investigación previa")
    primer_subparser.add_argument("-n", "--negocio", required=True)
    primer_subparser.add_argument("-c", "--ciudad", required=True)
    # ... más args
    
    # Subcomando para nueva_area
    nueva_subparser = subparsers.add_parser("nueva-area", help="Nueva área especializada")
    nueva_subparser.add_argument("--arg1", required=True)
    # ... más args
    
    args = parser.parse_args()
    
    if args.area == "primer-contacto":
        from primer_contacto.agente import setup_crew
        # ... ejecución
    elif args.area == "nueva-area":
        from nueva_area.agente import setup_crew
        # ... ejecución
```

## 📋 Checklist para Nueva Área

- [ ] Carpeta creada: `area_nombre/`
- [ ] Archivos creados:
  - [ ] `__init__.py`
  - [ ] `agente.py` con `setup_crew()` y `extract_crew_result()`
  - [ ] `servidor_mcp.py` con tools decoradas con `@mcp.tool()`
  - [ ] `system_prompts/*.md` (mínimo 1 agente)
  - [ ] `context/reglas_*.md` (contexto global)
- [ ] main.py actualizado con soporte para nueva área
- [ ] gui.py actualizado (si aplica)
- [ ] MÓDULOS.md actualizado

## 🔄 Flujo Típico de una Área

```
INPUT (parámetros CLI/GUI)
    ↓
setup_crew() → Crear agentes + tareas
    ↓
crew.kickoff() → Ejecutar orquestación
    ↓
extract_crew_result() → Extraer resultado
    ↓
OUTPUT (JSON, texto, archivo)
```

## 🛠️ Herramientas Compartidas

Posibles herramientas reutilizables entre áreas:

```python
# utils/shared_tools.py (futuro)

@tool("buscar_google")
def buscar_google(query: str) -> str:
    """Búsqueda general en Google"""
    pass

@tool("extraer_emails")
def extraer_emails(texto: str) -> str:
    """Extraer emails de texto"""
    pass

@tool("validar_sitio")
def validar_sitio(url: str) -> str:
    """Validar accesibilidad de sitio web"""
    pass
```

## 📚 Documentación de Cada Área

Crear `area_nombre/README.md`:

```markdown
# [Nombre del Área]

**Descripción**: [Qué hace esta área]

## Agentes

1. **Agente 1**: [Rol y responsabilidades]
2. **Agente 2**: [Rol y responsabilidades]

## Entrada/Salida

**Entrada**: [Parámetros esperados]
**Salida**: [Formato de resultado]

## Ejemplo

[Ejemplo de uso]

## Configuración

[Variables de entorno necesarias]
```

## 🚀 Roadmap de Áreas Futuras

- **gestion_redes**: Crear estrategias de redes sociales
- **seo_audit**: Auditoría SEO completa
- **contenido**: Generación de contenido estratégico
- **vendedor_bot**: Automatización de ventas
- **email_campaigns**: Diseño de campañas de email

---

## ✅ Conclusión

Esta estructura permite que el proyecto crezca de forma **modular, escalable y mantenible**. Cada área es independiente pero puede reutilizar código compartido y coordinarse vía `main.py`.

**Principios clave**:
- 🎯 Una responsabilidad por módulo
- 🔧 Herramientas especializadas
- 📦 Fácil de agregar nuevas áreas
- 🔄 Orquestación centralizada en main.py
