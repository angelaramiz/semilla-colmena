# core/manifiesto.py
"""
Generador de manifiesto Trinity para un ÁRBOL (instancia de la colmena).

Según el rol (obrero | comandante | heredero) produce el manifiesto de despliegue:
- obrero     : servicios 24/7 (Tronco + todas las ramas con restart: always).
- comandante : servicio bajo demanda (replicas: 0, cold start) + control de árboles.
- heredero   : como comandante pero con referencia al primario (failover).

La semilla lo genera en su fase de MADUREZ (la semilla crea su propio manifiesto).
"""
import os


def _base_permissions() -> str:
    return """permissions:
  trabajador:       [leer_briefs, escribir_borradores, publicar:false]
  orquestador:      [leer_todos, escribir_aprobaciones, ejecutar_accion_critica:false]
  directora_humana: [aprobar_acciones_criticas]     # único rol con permiso real
"""


def _obrero(arbol_id: str, aprobacion: str) -> str:
    ramas = ["contenido", "redes", "analitica", "investigacion", "atencion_cliente", "planeacion", "auditoria"]
    servicios = (
        "  orquestador:\n"
        "    image: semilla-agen:orquestador\n"
        "    env_file: .env\n"
        "    volumes: [\"shared:/shared\"]\n"
        "    deploy: { replicas: 1, restart: always }\n"
        "    permissions:\n"
        "      ejecutar_accion_critica: false\n"
    )
    for r in ramas:
        servicios += f"  {r}: {{ image: semilla-agen:{r}, env_file: .env, volumes: [\"shared\"], deploy: {{ restart: always }} }}\n"
    return (
        f'version: "1.0"\n'
        f"arbol:\n  id: \"{arbol_id}\"\n  rol: obrero\n  aprobacion: {aprobacion}\n\n"
        f"# Árbol OBRERO: servicios vivos 24/7\nservices:\n{servicios}\n"
        + _base_permissions()
    )


def _comandante(arbol_id: str, aprobacion: str, heredero_de: str = "") -> str:
    heredero_line = f'  heredero_de: "{heredero_de}"\n' if heredero_de else ""
    return (
        f'version: "1.0"\n'
        f"arbol:\n  id: \"{arbol_id}\"\n  rol: comandante\n{heredero_line}  aprobacion: {aprobacion}\n\n"
        f"# Árbol COMANDANTE: activo bajo demanda (cold start)\n"
        f"services_comandante:\n"
        f"  comandante:\n"
        f"    image: semilla-agen:comandante\n"
        f"    env_file: .env\n"
        f"    volumes: [\"shared:/shared\"]\n"
        f"    deploy: {{ replicas: 0, restart: \"no\" }}\n"
        f"    permissions:\n"
        f"      ejecutar_accion_critica: false\n"
        f"      controlar_arboles: true\n\n"
        f"permissions:\n"
        f"  trabajador:       [leer_briefs, escribir_borradores, publicar:false]\n"
        f"  comandante:       [controlar_arboles, ejecutar_tareas_agente]   # el padre tambien es obrero\n"
        f"  directora_humana: [aprobar_acciones_criticas]\n"
    )


def _conservante(arbol_id: str, aprobacion: str) -> str:
    return (
        f'version: "1.0"\n'
        f"arbol:\n  id: \"{arbol_id}\"\n  rol: conservante\n  aprobacion: {aprobacion}\n\n"
        f"# Árbol CONSERVANTE: exclusivo del arquitecto/dev. Acceso completo al micelio y estructura.\n"
        f"services_conservante:\n"
        f"  micelio:\n"
        f"    image: semilla-agen:micelio\n"
        f"    env_file: .env\n"
        f"    volumes: [\"shared:/app/shared\"]\n"
        f"    deploy: {{ replicas: 0, restart: \"no\" }}   # bajo demanda\n"
        f"    permissions:\n"
        f"      mantenimiento_completo: true   # reparar, sincronizar, aplicar_parche\n"
        f"  conservante_web:\n"
        f"    image: semilla-agen:conservante_web\n"
        f"    env_file: .env\n"
        f"    volumes: [\"shared:/app/shared\"]\n"
        f"    deploy: {{ replicas: 0, restart: \"no\" }}\n"
        f"    permissions:\n"
        f"      acceso_estructura: true\n\n"
        f"permissions:\n"
        f"  conservante: [mantenimiento_completo, acceso_estructura, controlar_arboles, ejecutar_tareas_agente]\n"
        f"  directora_humana: [aprobar_acciones_criticas]\n"
    )


def generar_manifiesto(arbol_id: str, rol: str = "obrero", nombre: str = "",
                       aprobacion: str = "manual", heredero_de: str = "") -> str:
    rol = (rol or "obrero").lower()
    if rol == "conservante":
        return _conservante(arbol_id, aprobacion)
    if rol == "comandante":
        return _comandante(arbol_id, aprobacion)
    if rol == "heredero":
        return _comandante(arbol_id, aprobacion, heredero_de)
    return _obrero(arbol_id, aprobacion)


def guardar_manifiesto(ruta: str, arbol_id: str, rol: str = "obrero", nombre: str = "",
                       aprobacion: str = "manual", heredero_de: str = "") -> str:
    contenido = generar_manifiesto(arbol_id, rol, nombre, aprobacion, heredero_de)
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    return ruta