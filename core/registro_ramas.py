# core/registro_ramas.py
"""
Registro de RAMAS (agentes obreros) de la colmena.

Permite al TRONCO delegar trabajo a una rama de forma genérica:
- modulo         : paquete de la rama (importable con importlib).
- funcion_crew   : nombre de la función que construye el Crew.
- funcion_extract: nombre de la función que extrae el resultado del Crew.
- descripcion    : qué hace la rama y qué inputs espera (para el LLM del Tronco).
- campos         : lista de campos de input que la rama consume.

Nueva rama = añadir una entrada aquí (es el contrato de delegación).
"""
REGISTRO_RAMAS = {
    "planeacion": {
        "modulo": "planeacion.agente",
        "funcion_crew": "setup_crew",
        "funcion_extract": "extract_crew_result",
        "descripcion": ("Estratega de Campañas. Inputs: objetivo, dossier_json, ciudad, "
                        "presupuesto. Traduce el dossier en plan ejecutable (KPIs, público, "
                        "calendario, presupuesto). Produce el plan; no expone."),
        "campos": ["objetivo", "dossier_json", "ciudad", "presupuesto"],
    },
    "contenido": {
        "modulo": "contenido.agente",
        "funcion_crew": "setup_crew",
        "funcion_extract": "extract_crew_result",
        "descripcion": ("Copywriter multiformato. Inputs: tema, marca, audiencia, "
                        "plataformas (coma), tono. Produce borradores, no publica."),
        "campos": ["tema", "marca", "audiencia", "plataformas", "tono"],
    },
    "redes": {
        "modulo": "redes.agente",
        "funcion_crew": "setup_crew",
        "funcion_extract": "extract_crew_result",
        "descripcion": ("Community Manager. Inputs: marca, audiencia, plataformas, "
                        "periodo_dias, objetivo. Prepara calendarios y piezas; no publica."),
        "campos": ["marca", "audiencia", "plataformas", "periodo_dias", "objetivo"],
    },
    "analitica": {
        "modulo": "analitica.agente",
        "funcion_crew": "setup_crew",
        "funcion_extract": "extract_crew_result",
        "descripcion": ("Analista de KPIs. Inputs: objetivo, periodo, metricas_json. "
                        "Genera reportes y recomendaciones; no modifica presupuesto."),
        "campos": ["objetivo", "periodo", "metricas_json"],
    },
    "investigacion": {
        "modulo": "investigacion.agente",
        "funcion_crew": "setup_crew",
        "funcion_extract": "extract_crew_result",
        "descripcion": ("Analista de Mercado. Inputs: tema, ciudad, categoria. "
                        "Solo lectura; produce dossiers."),
        "campos": ["tema", "ciudad", "categoria"],
    },
    "atencion_cliente": {
        "modulo": "atencion_cliente.agente",
        "funcion_crew": "setup_crew",
        "funcion_extract": "extract_crew_result",
        "descripcion": ("Soporte al cliente. Inputs: mensaje, cliente. Responde consultas "
                        "rutinarias y escala quejas (que requieren aprobación)."),
        "campos": ["mensaje", "cliente"],
    },
    "auditoria": {
        "modulo": "primer_contacto.agente",
        "funcion_crew": "setup_crew",
        "funcion_extract": "extract_crew_result",
        "descripcion": ("Auditor de Huella Digital. Inputs: negocio, ciudad, recursos_extra, "
                        "modelo_negocio, contexto_empresa. Genera JSON triple de auditoría."),
        "campos": ["negocio", "ciudad", "recursos_extra", "modelo_negocio", "contexto_empresa"],
    },
}

RAMAS_DISPONIBLES = list(REGISTRO_RAMAS.keys())