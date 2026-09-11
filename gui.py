# gui.py
# Interfaz gráfica para el Auditor de Huella Digital
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import subprocess
import json
import os
import threading
import time
import requests
import io
from PIL import Image
from urllib.parse import urlparse

# Configuración de apariencia
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AuditoriaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("🔍 Auditor de Huella Digital - Agencia MCP")
        self.geometry("1000x800")
        self.minsize(900, 700)
        
        self.ejecutando = False
        
        # Layout principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.crear_header()
        self.crear_tabs()
        self.crear_panel_log()
        self.crear_status_bar()
        
    def crear_header(self):
        """Header con título"""
        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        
        titulo = ctk.CTkLabel(
            header, 
            text="🔍 Auditor de Huella Digital", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        titulo.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        subtitulo = ctk.CTkLabel(
            header,
            text="Agencia de Marketing con Orquestación IA | Monterrey, NL",
            font=ctk.CTkFont(size=12)
        )
        subtitulo.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        
    def crear_tabs(self):
        """Tabs: Individual y Lote"""
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        self.tab_individual = self.tabview.add("📋 Auditoría Individual")
        self.crear_form_individual()
        
        self.tab_lote = self.tabview.add("📦 Auditoría por Lote")
        self.crear_form_lote()
        
        self.tab_log = self.tabview.add("💻 Consola de Log")
        
    def crear_form_individual(self):
        """Formulario Individual"""
        self.tab_individual.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.tab_individual, text="📛 Nombre del negocio:").grid(row=0, column=0, padx=20, pady=(10, 0), sticky="w")
        self.entry_negocio = ctk.CTkEntry(self.tab_individual, placeholder_text="Ej: Dental Smarts")
        self.entry_negocio.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")
        
        ctk.CTkLabel(self.tab_individual, text="📍 Ciudad y estado:").grid(row=2, column=0, padx=20, pady=(5, 0), sticky="w")
        self.entry_ciudad = ctk.CTkEntry(self.tab_individual, placeholder_text="Ej: Monterrey, Nuevo León")
        self.entry_ciudad.grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")
        
        ctk.CTkLabel(self.tab_individual, text="🌐 Sitio Web (opcional):").grid(row=4, column=0, padx=20, pady=(5, 0), sticky="w")
        self.entry_sitio = ctk.CTkEntry(self.tab_individual, placeholder_text="Ej: www.dentalsmarts.com")
        self.entry_sitio.grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(self.tab_individual, text="📸 Instagram (opcional):").grid(row=6, column=0, padx=20, pady=(5, 0), sticky="w")
        self.entry_ig = ctk.CTkEntry(self.tab_individual, placeholder_text="Ej: @dentalsmarts")
        self.entry_ig.grid(row=7, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(self.tab_individual, text="📘 Facebook (opcional):").grid(row=8, column=0, padx=20, pady=(5, 0), sticky="w")
        self.entry_fb = ctk.CTkEntry(self.tab_individual, placeholder_text="Ej: facebook.com/dentalsmarts")
        self.entry_fb.grid(row=9, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(self.tab_individual, text="📄 Guardar reporte en (opcional):").grid(row=10, column=0, padx=20, pady=(5, 0), sticky="w")
        
        frame_output = ctk.CTkFrame(self.tab_individual, fg_color="transparent")
        frame_output.grid(row=11, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="ew")
        frame_output.grid_columnconfigure(0, weight=1)
        
        self.entry_output = ctk.CTkEntry(frame_output, placeholder_text="reportes/auditoria.json")
        self.entry_output.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        btn_browse = ctk.CTkButton(frame_output, text="📁", width=40, command=self.browse_output)
        btn_browse.grid(row=0, column=1)

        ctk.CTkLabel(self.tab_individual, text="⚙️ Modo de Ejecución:").grid(row=12, column=0, padx=20, pady=(5, 0), sticky="w")
        self.var_modo = ctk.StringVar(value="local")
        self.combo_modo = ctk.CTkOptionMenu(
            self.tab_individual, 
            values=["local", "produccion", "obrero"],
            variable=self.var_modo,
            fg_color="#34495e",
            button_color="#2c3e50"
        )
        self.combo_modo.grid(row=13, column=0, columnspan=2, padx=20, pady=(0, 15), sticky="ew")
        
        self.btn_ejecutar = ctk.CTkButton(
            self.tab_individual, 
            text="🚀 Ejecutar Auditoría", 
            command=self.ejecutar_individual,
            height=40,
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_ejecutar.grid(row=14, column=0, columnspan=2, padx=20, pady=15, sticky="ew")
        
    def crear_form_lote(self):
        """Formulario Lote"""
        self.tab_lote.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.tab_lote, text="📄 Archivo JSON:").grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        
        frame_lote = ctk.CTkFrame(self.tab_lote, fg_color="transparent")
        frame_lote.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        frame_lote.grid_columnconfigure(0, weight=1)
        
        self.entry_archivo_lote = ctk.CTkEntry(frame_lote, placeholder_text="clientes.json")
        self.entry_archivo_lote.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        btn_browse = ctk.CTkButton(frame_lote, text="📁 Buscar", command=self.browse_lote)
        btn_browse.grid(row=0, column=1)
        
        self.btn_ejecutar_lote = ctk.CTkButton(
            self.tab_lote,
            text="🚀 Ejecutar Lote",
            command=self.ejecutar_lote,
            height=40,
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_ejecutar_lote.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
    def crear_panel_log(self):
        """Panel de Log / Consola de salida"""
        panel_log = ctk.CTkFrame(self.tab_log)
        panel_log.pack(fill="both", expand=True)
        panel_log.grid_columnconfigure(0, weight=1)
        panel_log.grid_rowconfigure(1, weight=1)
        
        header_log = ctk.CTkFrame(panel_log, fg_color="transparent")
        header_log.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        header_log.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(header_log, text="💻 Consola de Salida / Log", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=10, pady=5, sticky="w")
        
        btn_limpiar_log = ctk.CTkButton(header_log, text="🗑️ Limpiar", width=80, command=self.limpiar_log, fg_color="gray", height=25)
        btn_limpiar_log.grid(row=0, column=1, padx=10, pady=5)
        
        self.text_log = ctk.CTkTextbox(panel_log, font=ctk.CTkFont(family="Consolas", size=11))
        self.text_log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        
    def crear_status_bar(self):
        """Barra de estado inferior"""
        self.status_bar = ctk.CTkLabel(self, text="✅ Listo", anchor="w")
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 20))
        
    # ==================== MÉTODOS DE INTERFAZ ====================
    
    def browse_output(self):
        # Crear carpeta reportes si no existe
        os.makedirs("reportes", exist_ok=True)
        
        archivo = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.abspath("reportes"),
            initialfile="auditoria.json",
            title="Guardar reporte como"
        )
        if archivo:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, archivo)
            
    def browse_lote(self):
        archivo = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Seleccionar archivo JSON de clientes"
        )
        if archivo:
            self.entry_archivo_lote.delete(0, tk.END)
            self.entry_archivo_lote.insert(0, archivo)
            
    def limpiar_log(self):
        self.text_log.delete("1.0", tk.END)
        self.agregar_log("🧹 Log limpiado.")
        
    def agregar_log(self, texto, tipo="info"):
        """Agrega texto al log con colores"""
        self.text_log.insert(tk.END, texto + "\n", tipo)
        self.text_log.see(tk.END)
        
        # Configurar colores
        self.text_log.tag_config("info", foreground="white")
        self.text_log.tag_config("success", foreground="#2ecc71")
        self.text_log.tag_config("error", foreground="#e74c3c")
        self.text_log.tag_config("warning", foreground="#f39c12")
        self.text_log.tag_config("json", foreground="#3498db")
        
    def actualizar_status(self, mensaje, tipo="info"):
        colores = {"info": "white", "success": "#2ecc71", "error": "#e74c3c", "warning": "#f39c12"}
        self.status_bar.configure(text=mensaje, text_color=colores.get(tipo, "white"))
        self.agregar_log(f"[{tipo.upper()}] {mensaje}", tipo)
        
    # ==================== LÓGICA DE EJECUCIÓN ====================
    
    def ejecutar_individual(self):
        negocio = self.entry_negocio.get().strip()
        ciudad = self.entry_ciudad.get().strip()
        sitio_web = self.entry_sitio.get().strip()
        instagram = self.entry_ig.get().strip()
        facebook = self.entry_fb.get().strip()
        output = self.entry_output.get().strip()
        modo = self.var_modo.get()
        
        if not negocio or not ciudad:
            self.actualizar_status("❌ Faltan datos: Nombre y Ciudad son obligatorios", "error")
            return
            
        if self.ejecutando:
            return
            
        cmd = ["uv", "run", "python", "main.py", "--cli", "-n", negocio, "-c", ciudad, "-m", modo]
        if sitio_web:
            cmd.extend(["--sitio", sitio_web])
        if instagram:
            cmd.extend(["--ig", instagram])
        if facebook:
            cmd.extend(["--fb", facebook])
            
        if not output:
            output = "reportes/auditoria.json"
            
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        cmd.extend(["-o", output])
            
        self.ejecutando = True
        self.btn_ejecutar.configure(state="disabled", text="⏳ Ejecutando...")
        self.tabview.set("💻 Consola de Log")
        self.actualizar_status(f"🔄 Iniciando auditoría para: {negocio} (Modo: {modo.upper()})...", "info")
        
        threading.Thread(target=self._run_subprocess, args=(cmd, True, output), daemon=True).start()
        
    def ejecutar_lote(self):
        archivo = self.entry_archivo_lote.get()
        if not archivo or not os.path.exists(archivo):
            self.actualizar_status("❌ Archivo JSON no encontrado", "error")
            return
            
        if self.ejecutando:
            return
            
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
            auditorias = datos.get("auditorias", [])
        except Exception as e:
            self.actualizar_status(f"❌ Error leyendo JSON: {e}", "error")
            return
            
        if not auditorias:
            self.actualizar_status("❌ Lista vacía en JSON", "error")
            return
            
        self.ejecutando = True
        self.btn_ejecutar_lote.configure(state="disabled", text="⏳ Ejecutando...")
        self.tabview.set("💻 Consola de Log")
        modo = self.var_modo.get()
        self.actualizar_status(f"🔄 Iniciando lote: {len(auditorias)} empresas (Modo: {modo.upper()})...", "info")
        
        threading.Thread(target=self._run_lote, args=(auditorias,), daemon=True).start()
        
    def _run_subprocess(self, cmd, es_individual=False, output_path=None):
        """Ejecuta el comando y redirige la salida al log"""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )
            
            full_output_lines = []
            
            for line in process.stdout:
                # Filtramos líneas vacías
                if not line.strip():
                    continue
                # Mostrar en log inmediatamente (tiempo real)
                self.after(0, lambda l=line: self.agregar_log(l.rstrip()))
                full_output_lines.append(line)
                
            process.wait()
            
            if process.returncode == 0:
                self.after(0, lambda: self.actualizar_status("✅ Auditoría completada exitosamente", "success"))
                
                # Intentar procesar JSON si es una auditoría individual
                if es_individual:
                    json_cargado = False
                    if output_path:
                        # Dar una fracción de segundo para asegurar la escritura del archivo
                        time.sleep(0.5)
                        if os.path.exists(output_path):
                            try:
                                with open(output_path, "r", encoding="utf-8") as f:
                                    json_text = f.read()
                                # Validar JSON
                                json.loads(json_text)
                                self.after(0, lambda j=json_text: self.procesar_json_resultado(j))
                                json_cargado = True
                            except Exception as e:
                                self.after(0, lambda err=e: self.agregar_log(f"⚠️ Error leyendo archivo JSON: {err}", "warning"))
                    
                    if not json_cargado:
                        # Fallback: Extraer JSON del stdout
                        texto_completo = "".join(full_output_lines)
                        json_extraido = self.extraer_json_de_texto(texto_completo)
                        if json_extraido:
                            try:
                                json.loads(json_extraido)
                                self.after(0, lambda j=json_extraido: self.procesar_json_resultado(j))
                                json_cargado = True
                            except:
                                pass
                                
                    if not json_cargado:
                        self.after(0, lambda: self.agregar_log("❌ No se pudo encontrar un reporte JSON válido de los agentes.", "error"))
            else:
                self.after(0, lambda: self.actualizar_status("❌ La ejecución terminó con errores", "error"))
                
        except Exception as e:
            self.after(0, lambda e=e: self.actualizar_status(f"❌ Error fatal: {e}", "error"))
        finally:
            self.ejecutando = False
            self.after(0, lambda: self.btn_ejecutar.configure(state="normal", text="🚀 Ejecutar Auditoría"))
            self.after(0, lambda: self.btn_ejecutar_lote.configure(state="normal", text="🚀 Ejecutar Lote"))

    def extraer_json_de_texto(self, texto):
        """Intenta extraer un bloque JSON válido de un texto con ruido"""
        if not texto:
            return None
            
        # Buscar usando delimitadores
        if "[END_OF_JSON_REPORT]" in texto:
            parts = texto.split("[END_OF_JSON_REPORT]")
            candidate = parts[0]
            start_idx = candidate.rfind("📋 REPORTE DE AUDITORÍA")
            if start_idx != -1:
                candidate = candidate[start_idx:]
            
            first_brace = candidate.find("{")
            last_brace = candidate.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                return candidate[first_brace:last_brace+1]
                
        # Fallback general: primer { y último }
        first_brace = texto.find("{")
        last_brace = texto.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return texto[first_brace:last_brace+1]
            
        return None

    def procesar_json_resultado(self, json_text):
        """Procesa y muestra el JSON de resultado"""
        try:
            # Limpiar posibles markdown blocks y etiquetas de CrewAI
            clean_json = json_text.replace("```json", "").replace("```", "").replace("[END_OF_JSON_REPORT]", "").strip()
            
            # Intentar parsear JSON
            data = json.loads(clean_json)
            
            # Mostrar JSON formateado
            json_formateado = json.dumps(data, indent=2, ensure_ascii=False)
            self.agregar_log("\n" + "="*60, "json")
            self.agregar_log("📊 REPORTE ESTRATÉGICO MULTI-AGENTE", "json")
            self.agregar_log("="*60, "json")
            self.agregar_log(json_formateado, "json")
            self.agregar_log("="*60 + "\n", "json")
            
            # Extraer información de los 3 bloques
            cliente = data.get("cliente_gancho", {})
            mercadologa = data.get("interno_mercadologa", {})
            ingeniero = data.get("interno_ingeniero", {})
            
            # Si tiene el nuevo esquema
            if cliente or mercadologa or ingeniero:
                if cliente:
                    score = cliente.get("score", "N/A")
                    resumen = cliente.get("resumen_ejecutivo", "N/A")
                    self.agregar_log(f"🏢 [CLIENTE] Score Digital: {score}/100", "success")
                    self.agregar_log(f"📝 [CLIENTE] Resumen: {str(resumen)[:120]}...", "info")
                    
                if mercadologa:
                    estrategia = mercadologa.get("estrategia_recomendada", "N/A")
                    self.agregar_log(f"🎯 [AGENCIA] Estrategia: {str(estrategia)[:120]}...", "warning")
                    
                if ingeniero:
                    viabilidad = ingeniero.get("viabilidad_automatizacion", "N/A")
                    self.agregar_log(f"⚙️ [SISTEMAS] Viabilidad n8n: {str(viabilidad)[:120]}...", "json")
            else:
                # Fallback para el esquema viejo (por compatibilidad)
                score = data.get("score", "N/A")
                resumen = data.get("resumen_ejecutivo", "N/A")
                self.agregar_log(f"🏆 Score de Madurez Digital: {score}/100", "success")
                self.agregar_log(f"📝 Resumen: {str(resumen)[:100]}...", "info")
            
            # Lanzar ventana visual
            self.mostrar_ventana_resultados(data)
            
        except json.JSONDecodeError as e:
            self.agregar_log(f"❌ Error parseando JSON: {e}", "error")
            self.agregar_log(json_text, "error")

    def mostrar_ventana_resultados(self, data):
        """Muestra una ventana emergente con los resultados y el logo"""
        ventana = ctk.CTkToplevel(self)
        ventana.title("📊 Resultados de Auditoría")
        ventana.geometry("700x800")
        ventana.transient(self)
        
        # Parse data
        cliente = data.get("cliente_gancho", {})
        mercadologa = data.get("interno_mercadologa", {})
        
        score = cliente.get("score", "N/A")
        resumen = cliente.get("resumen_ejecutivo", "Sin resumen.")
        plataformas = cliente.get("plataformas_encontradas", {})
        
        # Frame superior (Logo y Score)
        frame_top = ctk.CTkFrame(ventana, fg_color="transparent")
        frame_top.pack(fill="x", padx=20, pady=20)
        
        # Intentar obtener dominio del input
        dominio = "placeholder"
        sitio_web_str = self.entry_sitio.get().strip()
        if sitio_web_str:
            if not sitio_web_str.startswith("http"):
                sitio_web_str = "http://" + sitio_web_str
            dominio = urlparse(sitio_web_str).netloc
            dominio = dominio.replace("www.", "")
        
        # Descargar Logo
        logo_image = None
        if dominio and dominio != "placeholder":
            try:
                response = requests.get(f"https://logo.clearbit.com/{dominio}", timeout=5)
                if response.status_code == 200:
                    image_data = Image.open(io.BytesIO(response.content))
                    logo_image = ctk.CTkImage(light_image=image_data, dark_image=image_data, size=(64, 64))
            except:
                pass
                
        if logo_image:
            lbl_logo = ctk.CTkLabel(frame_top, image=logo_image, text="")
            lbl_logo.pack(side="left", padx=(0, 20))
            
        lbl_score = ctk.CTkLabel(frame_top, text=f"Score Digital: {score}/100", font=ctk.CTkFont(size=24, weight="bold"), text_color="#2ecc71")
        lbl_score.pack(side="left", anchor="w")
        
        # Resumen
        frame_resumen = ctk.CTkFrame(ventana)
        frame_resumen.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_resumen, text="Resumen Ejecutivo", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        text_resumen = ctk.CTkTextbox(frame_resumen, height=80)
        text_resumen.pack(fill="x", padx=10, pady=(0, 10))
        text_resumen.insert("0.0", str(resumen))
        text_resumen.configure(state="disabled")
        
        # Checklist de Plataformas
        frame_check = ctk.CTkFrame(ventana)
        frame_check.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_check, text="Checklist de Plataformas", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        if isinstance(plataformas, dict) and plataformas:
            for plat, found in plataformas.items():
                icon = "✅" if found else "❌"
                color = "#2ecc71" if found else "#e74c3c"
                ctk.CTkLabel(frame_check, text=f"{icon} {plat.capitalize()}", text_color=color).pack(anchor="w", padx=20, pady=2)
        else:
            ctk.CTkLabel(frame_check, text="No se generó información de plataformas.", text_color="gray").pack(anchor="w", padx=20, pady=2)
            
        # Estrategia Recomendada
        estrategia = mercadologa.get("estrategia_recomendada", "Sin estrategia.")
        frame_est = ctk.CTkFrame(ventana)
        frame_est.pack(fill="both", expand=True, padx=20, pady=10)
        ctk.CTkLabel(frame_est, text="Estrategia (Agencia)", font=ctk.CTkFont(weight="bold"), text_color="#f39c12").pack(anchor="w", padx=10, pady=5)
        text_est = ctk.CTkTextbox(frame_est)
        text_est.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        text_est.insert("0.0", str(estrategia))
        text_est.configure(state="disabled")
        
        # Botón Cerrar
        ctk.CTkButton(ventana, text="Cerrar", command=ventana.destroy).pack(pady=20)
            
    def _run_lote(self, auditorias):
        modo = self.var_modo.get()
        for i, item in enumerate(auditorias):
            negocio = item.get("negocio", "")
            ciudad = item.get("ciudad", "")
            
            if not negocio or not ciudad:
                self.after(0, lambda: self.agregar_log(f"❌ [{i+1}] Saltando: datos incompletos", "error"))
                continue
                
            self.after(0, lambda n=negocio, idx=i+1, tot=len(auditorias): self.agregar_log(f"\n--- 🔄 [{idx}/{tot}] Procesando: {n} ---", "info"))
            
            cmd = ["uv", "run", "python", "agente.py", "-n", negocio, "-c", ciudad, "-m", modo]
            # En lote guardamos automáticamente en reportes/
            output_file = f"reportes/{negocio.replace(' ', '_').lower()}.json"
            cmd.extend(["-o", output_file])
            
            self._run_subprocess(cmd, es_individual=False, output_path=output_file)
            
        self.after(0, lambda: self.actualizar_status(f"✅ Lote completado: {len(auditorias)} auditorías", "success"))
        self.after(0, lambda: self.agregar_log(f"\n{'='*60}", "success"))
        self.after(0, lambda: self.agregar_log(f"📊 RESUMEN: {len(auditorias)} auditorías procesadas", "success"))
        self.after(0, lambda: self.agregar_log(f"📁 Reportes guardados en: reportes/", "success"))
        self.after(0, lambda: self.agregar_log(f"{'='*60}\n", "success"))


def main():
    app = AuditoriaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
