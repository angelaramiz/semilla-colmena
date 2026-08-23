# gui.py
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import json
import os
import threading
from datetime import datetime

# Configuración de apariencia
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AuditoriaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configuración de ventana
        self.title("🔍 Auditor de Huella Digital - Agencia MCP")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # Variables de estado
        self.ejecutando = False
        
        # Layout principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self.crear_header()
        self.crear_tabs()
        self.crear_panel_resultados()
        self.crear_status_bar()
        
    def crear_header(self):
        """Header con título y logo"""
        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))
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
        subtitulo.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")
        
    def crear_tabs(self):
        """Tabs: Individual y Lote"""
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        
        # Tab Individual
        self.tab_individual = self.tabview.add("📋 Auditoría Individual")
        self.crear_form_individual()
        
        # Tab Lote/Batch
        self.tab_lote = self.tabview.add("📦 Auditoría por Lote")
        self.crear_form_lote()
        
    def crear_form_individual(self):
        """Formulario para auditoría individual"""
        self.tab_individual.grid_columnconfigure(1, weight=1)
        
        # Nombre del negocio
        ctk.CTkLabel(self.tab_individual, text="📛 Nombre del negocio:").grid(
            row=0, column=0, padx=20, pady=(20, 5), sticky="w")
        self.entry_negocio = ctk.CTkEntry(self.tab_individual, placeholder_text="Ej: Dental Smarts")
        self.entry_negocio.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 15), sticky="ew")
        
        # Ciudad
        ctk.CTkLabel(self.tab_individual, text="📍 Ciudad y estado:").grid(
            row=2, column=0, padx=20, pady=(5, 5), sticky="w")
        self.entry_ciudad = ctk.CTkEntry(self.tab_individual, placeholder_text="Ej: Monterrey, Nuevo León")
        self.entry_ciudad.grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 15), sticky="ew")
        
        # Archivo de salida (opcional)
        ctk.CTkLabel(self.tab_individual, text="📄 Guardar reporte en (opcional):").grid(
            row=4, column=0, padx=20, pady=(5, 5), sticky="w")
        
        frame_output = ctk.CTkFrame(self.tab_individual, fg_color="transparent")
        frame_output.grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")
        frame_output.grid_columnconfigure(0, weight=1)
        
        self.entry_output = ctk.CTkEntry(frame_output, placeholder_text="reportes/auditoria.json")
        self.entry_output.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        btn_browse = ctk.CTkButton(frame_output, text="📁", width=40, command=self.browse_output)
        btn_browse.grid(row=0, column=1)
        
        # Botón ejecutar
        self.btn_ejecutar = ctk.CTkButton(
            self.tab_individual, 
            text="🚀 Ejecutar Auditoría", 
            command=self.ejecutar_individual,
            height=40,
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_ejecutar.grid(row=6, column=0, columnspan=2, padx=20, pady=20, sticky="ew")
        
        # Ejemplos rápidos
        ctk.CTkLabel(self.tab_individual, text="💡 Ejemplos rápidos:").grid(
            row=7, column=0, padx=20, pady=(20, 5), sticky="w")
        
        frame_ejemplos = ctk.CTkFrame(self.tab_individual, fg_color="transparent")
        frame_ejemplos.grid(row=8, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")
        
        ejemplos = [
            ("Dental Smarts", "Monterrey, NL"),
            ("Gimnasio FitLife", "San Pedro, NL"),
            ("Tacos El Güero", "Guadalupe, NL")
        ]
        
        for i, (negocio, ciudad) in enumerate(ejemplos):
            btn = ctk.CTkButton(
                frame_ejemplos,
                text=f"{negocio}",
                width=150,
                command=lambda n=negocio, c=ciudad: self.llenar_ejemplo(n, c),
                font=ctk.CTkFont(size=10)
            )
            btn.grid(row=i//2, column=i%2, padx=5, pady=2)
            
    def crear_form_lote(self):
        """Formulario para auditorías por lote"""
        self.tab_lote.grid_columnconfigure(0, weight=1)
        
        # Selector de archivo JSON
        ctk.CTkLabel(
            self.tab_lote, 
            text="📄 Selecciona archivo JSON con lista de negocios:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        frame_selector = ctk.CTkFrame(self.tab_lote, fg_color="transparent")
        frame_selector.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        frame_selector.grid_columnconfigure(0, weight=1)
        
        self.entry_archivo_lote = ctk.CTkEntry(frame_selector, placeholder_text="clientes.json")
        self.entry_archivo_lote.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        btn_browse = ctk.CTkButton(frame_selector, text="📁 Buscar", command=self.browse_lote)
        btn_browse.grid(row=0, column=1)
        
        # Vista previa del JSON
        ctk.CTkLabel(self.tab_lote, text="👁️ Vista previa:").grid(
            row=2, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.text_preview = ctk.CTkTextbox(self.tab_lote, height=100, font=ctk.CTkFont(size=11))
        self.text_preview.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="ew")
        
        btn_preview = ctk.CTkButton(self.tab_lote, text="🔄 Cargar Vista Previa", command=self.cargar_preview)
        btn_preview.grid(row=4, column=0, padx=20, pady=(0, 20))
        
        # Botón ejecutar lote
        self.btn_ejecutar_lote = ctk.CTkButton(
            self.tab_lote,
            text="🚀 Ejecutar Lote Completo",
            command=self.ejecutar_lote,
            height=40,
            font=ctk.CTkFont(weight="bold"),
            state="disabled"
        )
        self.btn_ejecutar_lote.grid(row=5, column=0, padx=20, pady=20, sticky="ew")
        
        # Progreso del lote
        self.progress_lote = ctk.CTkProgressBar(self.tab_lote)
        self.progress_lote.grid(row=6, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.progress_lote.set(0)
        
        self.label_progreso = ctk.CTkLabel(self.tab_lote, text="Listo para iniciar")
        self.label_progreso.grid(row=7, column=0, padx=20, pady=(0, 20))
        
    def crear_panel_resultados(self):
        """Panel para mostrar resultados"""
        panel = ctk.CTkFrame(self)
        panel.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(panel, text="📋 Resultados:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.text_resultados = ctk.CTkTextbox(panel, font=ctk.CTkFont(family="Consolas", size=10))
        self.text_resultados.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Botones de acción sobre resultados
        frame_acciones = ctk.CTkFrame(panel, fg_color="transparent")
        frame_acciones.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="e")
        
        btn_copiar = ctk.CTkButton(frame_acciones, text="📋 Copiar", width=80, command=self.copiar_resultados)
        btn_copiar.pack(side="left", padx=5)
        
        btn_guardar = ctk.CTkButton(frame_acciones, text="💾 Guardar", width=80, command=self.guardar_resultados)
        btn_guardar.pack(side="left", padx=5)
        
        btn_limpiar = ctk.CTkButton(frame_acciones, text="🗑️ Limpiar", width=80, command=self.limpiar_resultados, fg_color="gray")
        btn_limpiar.pack(side="left", padx=5)
        
    def crear_status_bar(self):
        """Barra de estado inferior"""
        self.status_bar = ctk.CTkLabel(self, text="✅ Listo | Ollama: Conectado", anchor="w")
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 20))
        
    # ==================== MÉTODOS DE INTERFAZ ====================
    
    def browse_output(self):
        """Selector de archivo para guardar reporte"""
        archivo = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir="reportes",
            title="Guardar reporte como"
        )
        if archivo:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, archivo)
            
    def browse_lote(self):
        """Selector de archivo JSON para lote"""
        archivo = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Seleccionar archivo de lote"
        )
        if archivo:
            self.entry_archivo_lote.delete(0, tk.END)
            self.entry_archivo_lote.insert(0, archivo)
            self.cargar_preview()
            
    def cargar_preview(self):
        """Cargar y mostrar vista previa del JSON de lote"""
        archivo = self.entry_archivo_lote.get()
        if not archivo or not os.path.exists(archivo):
            messagebox.showwarning("Archivo no encontrado", "Selecciona un archivo JSON válido")
            return
            
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
            
            auditorias = datos.get("auditorias", [])
            preview = f"📊 Total de auditorías: {len(auditorias)}\n\n"
            
            for i, item in enumerate(auditorias[:5], 1):  # Mostrar solo primeros 5
                preview += f"{i}. {item.get('negocio', 'N/A')} - {item.get('ciudad', 'N/A')}\n"
                if item.get('nota'):
                    preview += f"   💬 {item['nota']}\n"
            
            if len(auditorias) > 5:
                preview += f"\n... y {len(auditorias) - 5} más"
                
            self.text_preview.delete("1.0", tk.END)
            self.text_preview.insert("1.0", preview)
            self.btn_ejecutar_lote.configure(state="normal")
            
        except Exception as e:
            messagebox.showerror("Error al cargar", f"No se pudo leer el archivo:\n{e}")
            self.btn_ejecutar_lote.configure(state="disabled")
            
    def llenar_ejemplo(self, negocio, ciudad):
        """Llenar formulario con ejemplo rápido"""
        self.entry_negocio.delete(0, tk.END)
        self.entry_negocio.insert(0, negocio)
        self.entry_ciudad.delete(0, tk.END)
        self.entry_ciudad.insert(0, ciudad)
        
    def actualizar_status(self, mensaje, tipo="info"):
        """Actualizar barra de estado con colores"""
        colores = {"info": "white", "success": "#2ecc71", "error": "#e74c3c", "warning": "#f39c12"}
        self.status_bar.configure(text=mensaje, text_color=colores.get(tipo, "white"))
        self.update()
        
    def agregar_resultado(self, texto):
        """Agregar texto al panel de resultados"""
        self.text_resultados.insert(tk.END, texto + "\n")
        self.text_resultados.see(tk.END)
        
    def copiar_resultados(self):
        """Copiar resultados al portapapeles"""
        contenido = self.text_resultados.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(contenido)
        self.update_status("✅ Resultados copiados al portapapeles", "success")
        
    def guardar_resultados(self):
        """Guardar resultados en archivo"""
        archivo = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Guardar resultados"
        )
        if archivo:
            try:
                contenido = self.text_resultados.get("1.0", tk.END)
                with open(archivo, "w", encoding="utf-8") as f:
                    f.write(contenido)
                self.actualizar_status(f"✅ Guardado en {os.path.basename(archivo)}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
                
    def limpiar_resultados(self):
        """Limpiar panel de resultados"""
        self.text_resultados.delete("1.0", tk.END)
        
    # ==================== LÓGICA DE EJECUCIÓN ====================
    
    def ejecutar_individual(self):
        """Ejecutar auditoría individual en hilo separado"""
        negocio = self.entry_negocio.get().strip()
        ciudad = self.entry_ciudad.get().strip()
        output = self.entry_output.get().strip()
        
        if not negocio or not ciudad:
            messagebox.showwarning("Campos requeridos", "Ingresa nombre del negocio y ciudad")
            return
            
        if self.ejecutando:
            messagebox.showinfo("En proceso", "Ya hay una auditoría en ejecución")
            return
            
        # Preparar comando
        cmd = ["uv", "run", "python", "agente.py", "-n", negocio, "-c", ciudad]
        if output:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            cmd.extend(["-o", output])
            
        self.ejecutando = True
        self.btn_ejecutar.configure(state="disabled", text="⏳ Ejecutando...")
        self.actualizar_status(f"🔄 Auditando: {negocio}...", "info")
        self.limpiar_resultados()
        self.agregar_resultado(f"🚀 Iniciando: {negocio} en {ciudad}\n" + "-"*50)
        
        # Ejecutar en hilo separado para no congelar la UI
        threading.Thread(target=self._run_subprocess, args=(cmd, output), daemon=True).start()
        
    def _run_subprocess(self, cmd, output_file):
        """Ejecutar subprocesso y capturar output"""
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
            
            # Leer output en tiempo real
            for line in process.stdout:
                # Filtrar líneas muy verbosas de CrewAI para la UI
                if any(x in line for x in ["╭─", "│", "╰─", "Crew Execution", "Task Started"]):
                    continue
                self.after(0, lambda l=line: self.agregar_resultado(l.rstrip()))
                
            process.wait()
            
            if process.returncode == 0:
                self.after(0, lambda: self.actualizar_status("✅ Auditoría completada", "success"))
                # Si se guardó archivo, mostrar mensaje
                if output_file and os.path.exists(output_file):
                    self.after(0, lambda: self.agregar_resultado(f"\n💾 Reporte guardado: {output_file}"))
            else:
                self.after(0, lambda: self.actualizar_status("❌ Error en ejecución", "error"))
                
        except Exception as e:
            self.after(0, lambda: self.actualizar_status(f"❌ Error: {e}", "error"))
            self.after(0, lambda: self.agregar_resultado(f"Error: {e}"))
        finally:
            self.ejecutando = False
            self.after(0, lambda: self.btn_ejecutar.configure(state="normal", text="🚀 Ejecutar Auditoría"))
            
    def ejecutar_lote(self):
        """Ejecutar auditorías en lote"""
        archivo = self.entry_archivo_lote.get()
        if not archivo or not os.path.exists(archivo):
            messagebox.showwarning("Archivo requerido", "Selecciona un archivo JSON válido")
            return
            
        if self.ejecutando:
            messagebox.showinfo("En proceso", "Ya hay una auditoría en ejecución")
            return
            
        # Cargar lista de auditorías
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
            auditorias = datos.get("auditorias", [])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el archivo:\n{e}")
            return
            
        if not auditorias:
            messagebox.showwarning("Sin datos", "El archivo no contiene auditorías para procesar")
            return
            
        # Confirmar ejecución
        if not messagebox.askyesno("Confirmar", f"¿Ejecutar {len(auditorias)} auditorías?\n\nEsto puede tomar varios minutos."):
            return
            
        self.ejecutando = True
        self.btn_ejecutar_lote.configure(state="disabled", text="⏳ Procesando...")
        self.limpiar_resultados()
        self.agregar_resultado(f"🚀 Iniciando lote: {len(auditorias)} auditorías\n" + "="*50)
        
        # Ejecutar en hilo separado
        threading.Thread(target=self._run_lote, args=(auditorias,), daemon=True).start()
        
    def _run_lote(self, auditorias):
        """Ejecutar lote en background"""
        os.makedirs("reportes", exist_ok=True)
        
        for i, item in enumerate(auditorias, 1):
            negocio = item.get("negocio", "")
            ciudad = item.get("ciudad", "")
            
            if not negocio or not ciudad:
                self.after(0, lambda: self.agregar_resultado(f"❌ [{i}] Saltando: datos incompletos"))
                continue
                
            self.after(0, lambda i=i, n=negocio: self.actualizar_status(f"🔄 [{i}] {n}...", "info"))
            self.after(0, lambda: self.progress_lote.set(i / len(auditorias)))
            self.after(0, lambda: self.label_progreso.configure(text=f"Procesando {i}/{len(auditorias)}"))
            
            self.after(0, lambda: self.agregar_resultado(f"\n📋 [{i}/{len(auditorias)}] {negocio}"))
            
            # Ejecutar auditoría individual
            cmd = ["uv", "run", "python", "agente.py", "-n", negocio, "-c", ciudad]
            output_file = f"reportes/{negocio.replace(' ', '_').lower()}.json"
            cmd.extend(["-o", output_file])
            
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
                
                # Capturar solo líneas relevantes
                for line in process.stdout:
                    if "REPORTE DE AUDITORÍA" in line or '"score"' in line:
                        self.after(0, lambda l=line: self.agregar_resultado(l.rstrip()))
                        
                process.wait()
                
                if process.returncode == 0 and os.path.exists(output_file):
                    self.after(0, lambda: self.agregar_resultado(f"✅ Guardado: {output_file}"))
                else:
                    self.after(0, lambda: self.agregar_resultado(f"❌ Falló: {negocio}"))
                    
            except Exception as e:
                self.after(0, lambda e=e: self.agregar_resultado(f"❌ Error: {e}"))
                
        # Finalizar lote
        self.after(0, lambda: self.progress_lote.set(1.0))
        self.after(0, lambda: self.actualizar_status(f"✅ Lote completado: {len(auditorias)} auditorías", "success"))
        self.after(0, lambda: self.label_progreso.configure(text="Completado"))
        self.after(0, lambda: self.btn_ejecutar_lote.configure(state="normal", text="🚀 Ejecutar Lote Completo"))
        self.ejecutando = False
        
        # Mostrar resumen
        self.after(0, lambda: self.agregar_resultado(f"\n{'='*50}\n📊 RESUMEN: {len(auditorias)} auditorías procesadas"))
        self.after(0, lambda: self.agregar_resultado(f"📁 Reportes guardados en: reportes/"))


def main():
    app = AuditoriaApp()
    app.mainloop()


if __name__ == "__main__":
    main()