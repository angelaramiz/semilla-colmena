#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
main.py - Punto de entrada para el Auditor de Huella Digital

Ejecutar con:
    uv run python main.py          # Abre la GUI
    uv run python main.py --cli    # Modo CLI
"""

import sys
import os

# Asegurar UTF-8 en Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        pass

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Auditor de Huella Digital")
    parser.add_argument("--cli", action="store_true", help="Modo CLI en lugar de GUI")
    parser.add_argument("--negocio", "-n", type=str, help="Nombre del negocio (solo CLI)")
    parser.add_argument("--ciudad", "-c", type=str, help="Ciudad y estado (solo CLI)")
    parser.add_argument("--sitio", type=str, default="", help="Sitio web (opcional)")
    parser.add_argument("--ig", type=str, default="", help="Instagram (opcional)")
    parser.add_argument("--fb", type=str, default="", help="Facebook (opcional)")
    parser.add_argument("--output", "-o", type=str, help="Archivo de salida JSON (solo CLI)")
    parser.add_argument("--modo", "-m", type=str, choices=["local", "produccion"], default="local", help="Modo de ejecución")
    parser.add_argument("--modelo-negocio", "-mn", type=str, default="", help="Modelo de negocio (opcional)")
    parser.add_argument("--contexto", "-ctx", type=str, default="", help="Contexto adicional de la empresa (opcional)")
    parser.add_argument("--orquestador", action="store_true", help="Modo TRONCO: ejecutar el Orquestador de la agencia")
    parser.add_argument("--instruccion", "-i", type=str, help="Instrucción para la Directora (solo con --orquestador)")
    parser.add_argument("--clasificar", type=str, default="", help="Clasifica una instrucción (rutina/media/critica) sin ejecutar")

    # Rama genérica (runner por registro)
    parser.add_argument("--rama", type=str, default="", help="Nombre de la rama (contenido|redes|analitica|investigacion|atencion_cliente|auditoria|planeacion)")
    parser.add_argument("--inputs", type=str, default="", help="Inputs para la rama en JSON (ej. '{\"tema\":\"x\"}')")

    # Campaña orquestada (pipeline de ramas)
    parser.add_argument("--campana", type=str, default="", help="Objetivo de la campaña (ejecuta pipeline investigacion→planeacion→creacion→exposicion→analisis)")

    # Micelio (agente de mantenimiento)
    parser.add_argument("--micelio", action="store_true", help="Ejecutar el Micelio (agente de mantenimiento)")

    # Rama Contenido
    parser.add_argument("--contenido", action="store_true", help="Ejecutar la Rama Contenido (obrero)")
    parser.add_argument("--tema", type=str, default="", help="Tema del contenido")
    parser.add_argument("--marca", type=str, default="", help="Marca")
    parser.add_argument("--audiencia", type=str, default="", help="Audiencia objetivo")
    parser.add_argument("--plataformas", type=str, default="instagram", help="Plataformas (coma)")
    parser.add_argument("--tono", type=str, default="profesional", help="Tono del copy")

    # Comunicación raíz → árboles
    parser.add_argument("--arboles", action="store_true", help="Listar árboles registrados en el inventario del Comandante")
    parser.add_argument("--registrar-arbol", action="store_true", help="Registrar un árbol hijo (usar --arb-*)")
    parser.add_argument("--arb-id", type=str, default="", help="ARBOL_ID del hijo")
    parser.add_argument("--arb-host", type=str, default="", help="Hostname (Tailscale) o IP del hijo")
    parser.add_argument("--arb-usuario", type=str, default="root", help="Usuario SSH")
    parser.add_argument("--arb-puerto", type=int, default=22, help="Puerto SSH")
    parser.add_argument("--arb-canal", type=str, default="ssh", help="ssh | tailscale")
    parser.add_argument("--arb-nombre", type=str, default="", help="Nombre del árbol")
    parser.add_argument("--arb-repo", type=str, default=".", help="Ruta del repo en el hijo")

    args = parser.parse_args()

    if args.arboles:
        from db import listar_arboles
        import json as _json
        print(_json.dumps(listar_arboles(), ensure_ascii=False, indent=2))
        return

    if args.registrar_arbol:
        from db import registrar_arbol
        if not args.arb_id or not args.arb_host:
            print("❌ Se requiere --arb-id y --arb-host")
            sys.exit(1)
        res = registrar_arbol(args.arb_id, args.arb_host, args.arb_usuario,
                              args.arb_puerto, args.arb_canal, args.arb_nombre, args.arb_repo)
        import json as _json
        print(_json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.clasificar:
        from orquestador.agente import clasificar
        import json
        print(json.dumps(clasificar(args.clasificar), ensure_ascii=False, indent=2))
        return

    if args.micelio:
        # Micelio: agente local de mantenimiento (salud/actualizar/reparar/sincronizar)
        from micelio import servidor_mcp as s

        def _r(fn, **kw):
            return fn(**kw) if kw else fn()

        print("🍄 MICELIO | mantenimiento local")
        print("-" * 60)
        import json as _json
        for nombre, fn, kw in [
            ("Salud de estructura", s.salud_estructura, {}),
            ("Versión de componentes", s.version_componentes, {}),
            ("Reparar estructura", s.reparar_estructura, {}),
            ("Sincronizar manifiesto", s.sincronizar_manifiesto, {}),
        ]:
            try:
                print(f"\n▶ {nombre}:")
                print(_json.dumps(_json.loads(_r(fn, **kw)), ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"  ⚠️ {nombre}: {e}")
        return
    elif args.campana:
        # Pipeline de campaña: investigacion→planeacion→creacion→exposicion→analisis
        from orquestador.campana import ejecutar_campana
        import json

        inputs = {}
        if args.inputs:
            try:
                inputs = json.loads(args.inputs)
            except Exception:
                print("⚠️  --inputs no es JSON válido; se ignora")
        print(f"🎯 Campaña: {args.campana}")
        print("-" * 60)
        try:
            resultado = ejecutar_campana(args.campana, inputs)
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
            print("\n[END_OF_CAMPANA_REPORT]")
            if args.output:
                os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(resultado, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Guardado en: {args.output}")
        except KeyboardInterrupt:
            print("\n⚠️ Cancelado por usuario"); sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc(); sys.exit(1)
    elif args.rama:
        # Runner genérico de rama vía registro (delegación directa)
        from core.registro_ramas import REGISTRO_RAMAS
        import importlib, json

        rama = args.rama
        if rama not in REGISTRO_RAMAS:
            print(f"❌ Rama desconocida: {rama}. Disponibles: {list(REGISTRO_RAMAS)}")
            sys.exit(1)

        if args.inputs:
            try:
                inputs = json.loads(args.inputs)
            except Exception:
                print("❌ --inputs no es JSON válido")
                sys.exit(1)
        else:
            inputs = {}

        print(f"🌿 Rama [{rama}] | inputs: {inputs}")
        print("-" * 60)
        spec = REGISTRO_RAMAS[rama]
        try:
            mod = importlib.import_module(spec["modulo"])
            crew = getattr(mod, spec["funcion_crew"])()
            resultado = crew.kickoff(inputs=inputs)
            reporte = getattr(mod, spec["funcion_extract"])(resultado)
            print("\n" + "=" * 60)
            print(f"📦 ENTREGABLE DE LA RAMA {rama.upper()}")
            print("=" * 60)
            print(reporte)
            print(f"\n[END_OF_{rama.upper()}_REPORT]")
            if args.output:
                os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(reporte)
                print(f"\n💾 Guardado en: {args.output}")
        except KeyboardInterrupt:
            print("\n⚠️ Cancelado por usuario"); sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc(); sys.exit(1)
    elif args.contenido:
        # Rama OBRERA: contenido (produce borradores, no publica)
        from contenido.agente import setup_crew, extract_crew_result
        import json

        tema = args.tema or input("📝 Tema: ").strip()
        if not tema:
            print("❌ Se requiere --tema")
            sys.exit(1)

        print(f"✍️  Rama Contenido | {tema} | marca='{args.marca or '—'}' | {args.plataformas} | tono={args.tono}")
        print("-" * 60)

        try:
            crew = setup_crew(args.modo)
            resultado = crew.kickoff(inputs={
                "tema": tema, "marca": args.marca, "audiencia": args.audiencia,
                "plataformas": args.plataformas, "tono": args.tono,
            })
            reporte = extract_crew_result(resultado)
            print("\n" + "=" * 60)
            print("📦 ENTREGABLE DE CONTENIDO")
            print("=" * 60)
            print(reporte)
            print("\n[END_OF_CONTENIDO_REPORT]")
            if args.output:
                os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(reporte)
                print(f"\n💾 Guardado en: {args.output}")
        except KeyboardInterrupt:
            print("\n⚠️ Cancelado por usuario"); sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc(); sys.exit(1)
    elif args.orquestador:
        # Modo TRONCO: orquestador de la agencia
        from orquestador.agente import setup_crew, extract_crew_result
        import json
        
        instruccion = args.instruccion
        if not instruccion:
            instruccion = input("📋 Instrucción para la agencia: ").strip()
        
        if not instruccion:
            print("❌ Se requiere --instruccion")
            sys.exit(1)
        
        from orquestador.agente import clasificar
        clas = clasificar(instruccion)
        print(f"🌳 TRONCO | Clasificación: {clas['complejidad']} | Modelo: {clas['modelo']} | Gate: {clas['requiere_aprobacion']}")
        print("-" * 60)
        
        try:
            crew = setup_crew(args.modo)
            resultado = crew.kickoff(inputs={"instruccion": instruccion})
            reporte = extract_crew_result(resultado)
            print("\n" + "=" * 60)
            print("📦 ENTREGABLE DEL TRONCO")
            print("=" * 60)
            print(reporte)
            print("\n[END_OF_TRONCO_REPORT]")
            
            if args.output:
                os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(reporte)
                print(f"\n💾 Guardado en: {args.output}")
        
        except KeyboardInterrupt:
            print("\n⚠️ Cancelado por usuario")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    elif args.cli:
        # Modo CLI: ejecutar primer_contacto
        from primer_contacto.agente import setup_crew, extract_crew_result
        import json
        
        negocio = args.negocio
        ciudad = args.ciudad
        
        if not negocio or not ciudad:
            negocio = input("📛 Negocio: ").strip()
            ciudad = input("📍 Ciudad: ").strip()
        
        if not negocio or not ciudad:
            print("❌ Se requiere --negocio y --ciudad")
            sys.exit(1)
        
        # Construir recursos_extra si hay datos adicionales
        recursos = []
        if args.sitio: recursos.append(f"Sitio Web: {args.sitio}")
        if args.ig: recursos.append(f"Instagram: {args.ig}")
        if args.fb: recursos.append(f"Facebook: {args.fb}")
        recursos_extra = f"Recursos provistos directamente por el cliente: {', '.join(recursos)}." if recursos else ""
        
        print(f"🔍 Iniciando auditoría para: {negocio} en {ciudad} (Modo: {args.modo.upper()})")
        print("-" * 60)
        
        try:
            inputs = {
                "negocio": negocio,
                "ciudad": ciudad,
                "recursos_extra": recursos_extra,
                "modelo_negocio": args.modelo_negocio or "",
                "contexto_empresa": args.contexto or ""
            }
            crew = setup_crew(args.modo)
            resultado = crew.kickoff(inputs=inputs)
            reporte = extract_crew_result(resultado)
            
            print("\n" + "=" * 60)
            print("📋 REPORTE DE AUDITORÍA")
            print("=" * 60)
            print(reporte)
            print("\n[END_OF_JSON_REPORT]")
            
            if args.output:
                os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
                try:
                    reporte_dict = json.loads(reporte)
                    with open(args.output, "w", encoding="utf-8") as f:
                        json.dump(reporte_dict, f, ensure_ascii=False, indent=2)
                    print(f"\n💾 Guardado en: {args.output}")
                except json.JSONDecodeError:
                    print("\n⚠️ No se pudo guardar: reporte no es JSON válido")
        
        except KeyboardInterrupt:
            print("\n⚠️ Cancelado por usuario")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # Modo GUI: ejecutar gui.py
        try:
            from gui import main as gui_main
            gui_main()
        except ImportError:
            print("❌ Error: No se pudo importar gui.py")
            print("Verifica que customtkinter esté instalado:")
            print("    pip install customtkinter")
            sys.exit(1)


if __name__ == "__main__":
    main()
