# core/permisos.py
"""
Roles y permisos de la colmena (RBAC).

Dos niveles en el árbol principal:
- COMANDANTE : operaciones de marketing. Usa los árboles y sus ramas para campañas.
               NO accede al código ni a la estructura. Sobre el micelio SOLO puede
               revisar errores (salud/versión) y aplicar upgrades (actualizar).
- CONSERVANTE: exclusivo del arquitecto/dev. Acceso COMPLETO al micelio y a la
               estructura (reparar, sincronizar manifiesto, aplicar parches).

Además: OBRERO (árbol hijo, produce 24/7) y HEREDERO (comandante de respaldo).
"""
ROLES_ARBOL = ["obrero", "comandante", "conservante", "heredero"]

# Micelio: qué herramientas puede usar cada rol de árbol principal.
# El comandante SOLO: revisar errores (salud/versión) y upgrades (actualizar).
# El conservante: TODO (full, incluida estructura/código).
MICELIO_ACCESO = {
    "comandante": ["salud_estructura", "version_componentes", "actualizar_componentes"],
    "heredero": ["salud_estructura", "version_componentes", "actualizar_componentes"],
    "conservante": ["salud_estructura", "version_componentes", "actualizar_componentes",
                    "reparar_estructura", "sincronizar_manifiesto", "aplicar_parche"],
    "obrero": [],
}

# Qué es "acceso a estructura/código" (exclusivo del conservante).
MICELIO_ESTRUCTURA = ["reparar_estructura", "sincronizar_manifiesto", "aplicar_parche"]


def rol_tiene_micelio(rol: str | None, herramienta: str) -> bool:
    """¿El rol puede usar esa herramienta del micelio?"""
    rol = (rol or "comandante").lower()
    return herramienta in MICELIO_ACCESO.get(rol, [])


def es_conservante(rol: str | None) -> bool:
    return (rol or "").lower() == "conservante"


def rol_descripcion(rol: str | None) -> str:
    return {
        "comandante": "Opera campañas de marketing; micelio limitado (errores + upgrades).",
        "conservante": "Arquitecto/dev: acceso completo al micelio y a la estructura.",
        "heredero": "Comandante de respaldo (failover).",
        "obrero": "Árbol hijo: produce 24/7, no accede al micelio central.",
    }.get((rol or "").lower(), "rol desconocido")