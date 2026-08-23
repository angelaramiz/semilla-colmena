#!/bin/bash
# checklist.sh - Verificar que el proyecto esté completo

echo "🔍 Verificando estructura del proyecto agen_mrk..."
echo "=================================================="
echo

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
        return 0
    else
        echo -e "${RED}❌${NC} $1 (FALTA)"
        return 1
    fi
}

check_directory() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✅${NC} $1/"
        return 0
    else
        echo -e "${RED}❌${NC} $1/ (FALTA)"
        return 1
    fi
}

echo "📄 Archivos principales:"
check_file "agente.py"
check_file "servidor_mcp.py"
check_file "gui.py"
check_file "main.py"
check_file "pyproject.toml"
check_file "README.md"
check_file "FIXES_COMPLETADOS.md"
check_file ".env.example"

echo
echo "📁 Directorios:"
check_directory "context"
check_directory "reportes"
check_directory "salida"

echo
echo "📋 Archivos de configuración:"
check_file ".gitignore" || true
check_file ".env" || echo -e "${RED}⚠️${NC}  .env (Crear desde .env.example)"

echo
echo "✅ Verificación completada"
echo "=================================================="
echo
echo "📝 Próximos pasos:"
echo "1. Crear .env desde .env.example"
echo "2. Instalar dependencias: uv sync"
echo "3. Ejecutar: uv run python main.py"
