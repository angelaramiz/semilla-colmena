"""
Módulo comunicacion: control y estado entre el árbol PRINCIPAL y los árboles HIJO.

- comandante_mcp.py      : MCP del principal (registra, diagnostica, controla y
                           propaga upgrades a los hijos vía SSH/Tailscale).
- servidor_estado_mcp.py : MCP que corre en cada hijo (expone estado local y
                           aplica upgrades vía git).

Transporte privado: OpenSSH (puerto 22) sobre Tailscale.
"""

__version__ = "0.1.0"