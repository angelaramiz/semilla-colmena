# primer_contacto/servidor_mcp.py
import os, json, time, sys, traceback
try:
    import requests
except ImportError:
    # venv desincronizado: mensaje accionable en vez de traceback crudo.
    # Seguro porque este módulo corre standalone (stdio); nadie lo importa
    # como librería (los agentes usan cliente MCP).
    print("ERROR: falta el paquete 'requests'. Ejecuta: uv sync", file=sys.stderr)
    sys.exit("ModuleNotFoundError: requests — ejecuta 'uv sync' en la raíz del repo")
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()
mcp = FastMCP("AgenciaHuellaDigital")

# Configuración del proveedor
PROVIDER = os.getenv("DATA_PROVIDER", "mock").lower()  # Default a mock, no a serpapi
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8080").rstrip("/")  # sin key; "" = deshabilitado

# Logging helper para debug
def log_error(msg: str):
    """Log errors to stderr for debugging"""
    print(f"[MCP_ERROR] {msg}", file=sys.stderr)
    sys.stderr.flush()

def _buscar_con_serpapi(nombre: str, ciudad: str) -> dict:
    """Busca negocio usando SerpAPI (Google Maps wrapper)"""
    if not SERPAPI_KEY:
        return {"error": "Falta SERPAPI_KEY en .env", "fallback": "mock"}
    
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_maps",
        "q": f"{nombre} en {ciudad}",
        "type": "search",
        "api_key": SERPAPI_KEY,
        "hl": "es",
        "gl": "mx"
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        
        if not data.get("local_results"):
            return {"error": "Negocio no encontrado", "query": f"{nombre} en {ciudad}", "fallback": "mock"}
        
        lugar = data["local_results"][0]
        return {
            "nombre": lugar.get("title", "Desconocido"),
            "rating": lugar.get("rating", "N/A"),
            "total_resenas": lugar.get("reviews", 0),
            "direccion": lugar.get("address", "N/A"),
            "tiene_web": "website" in lugar,
            "telefono": lugar.get("phone", "No disponible"),
            "horario": lugar.get("hours", "No disponible"),
            "categorias": lugar.get("type", "N/A"),
            "fuente": "serpapi"
        }
    except requests.exceptions.Timeout:
        log_error(f"Timeout en SerpAPI para {nombre}")
        return {"error": "Timeout en SerpAPI (>15s)", "fallback": "mock"}
    except requests.exceptions.HTTPError as e:
        log_error(f"HTTP Error en SerpAPI: {e.response.status_code}")
        if e.response.status_code == 403:
            return {"error": "SerpAPI: Forbidden (check API key)", "fallback": "mock"}
        elif e.response.status_code == 429:
            return {"error": "SerpAPI: Rate limited (quota exceeded)", "fallback": "mock"}
        return {"error": f"Error HTTP SerpAPI: {e.response.status_code}", "fallback": "mock"}
    except Exception as e:
        log_error(f"Error en SerpAPI: {str(e)}\n{traceback.format_exc()}")
        return {"error": f"Error SerpAPI: {str(e)[:100]}", "fallback": "mock"}

def _buscar_con_google(nombre: str, ciudad: str) -> dict:
    """Busca negocio usando Google Places API nativa"""
    if not GOOGLE_API_KEY:
        return {"error": "Falta GOOGLE_API_KEY en .env", "fallback": "mock"}
    
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{nombre} en {ciudad}",
        "key": GOOGLE_API_KEY,
        "language": "es"
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        if not data.get("results"):
            return {"error": "Negocio no encontrado", "query": f"{nombre} en {ciudad}", "fallback": "mock"}
        
        lugar = data["results"][0]
        return {
            "nombre": lugar.get("name", "Desconocido"),
            "rating": lugar.get("rating", "N/A"),
            "total_resenas": lugar.get("user_ratings_total", 0),
            "direccion": lugar.get("formatted_address", "N/A"),
            "tiene_web": "website" in lugar,
            "telefono": lugar.get("formatted_phone_number", "No disponible"),
            "coordenadas": lugar.get("geometry", {}).get("location", {}),
            "fuente": "google"
        }
    except requests.exceptions.Timeout:
        log_error(f"Timeout en Google API para {nombre}")
        return {"error": "Timeout en Google API (>10s)", "fallback": "mock"}
    except requests.exceptions.HTTPError as e:
        log_error(f"HTTP Error en Google API: {e.response.status_code}")
        if e.response.status_code == 403:
            return {"error": "Google API: Forbidden (check API key)", "fallback": "mock"}
        elif e.response.status_code == 429:
            return {"error": "Google API: Rate limited", "fallback": "mock"}
        return {"error": f"Error HTTP Google: {e.response.status_code}", "fallback": "mock"}
    except Exception as e:
        log_error(f"Error en Google API: {str(e)}\n{traceback.format_exc()}")
        return {"error": f"Error Google API: {str(e)[:100]}", "fallback": "mock"}

def _buscar_con_serper(nombre: str, ciudad: str) -> dict:
    """Busca negocio usando Serper.dev (Google Maps wrapper)"""
    if not SERPER_API_KEY:
        return {"error": "Falta SERPER_API_KEY en .env", "fallback": "mock"}
    
    url = "https://google.serper.dev/maps"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": f"{nombre} en {ciudad}",
        "gl": "mx",
        "hl": "es"
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        res.raise_for_status()
        data = res.json()
        results = data.get("maps", [])
        if not results:
            return {"error": "Negocio no encontrado", "query": f"{nombre} en {ciudad}", "fallback": "mock"}
        
        lugar = results[0]
        return {
            "nombre": lugar.get("title", "Desconocido"),
            "rating": lugar.get("rating", "N/A"),
            "total_resenas": lugar.get("reviews", 0),
            "direccion": lugar.get("address", "N/A"),
            "tiene_web": "website" in lugar,
            "telefono": lugar.get("phoneNumber", "No disponible"),
            "categorias": lugar.get("category", "N/A"),
            "fuente": "serper"
        }
    except Exception as e:
        log_error(f"Error en Serper Maps: {e}")
        return {"error": f"Error Serper Maps: {str(e)}", "fallback": "mock"}

def _buscar_mock(nombre: str, ciudad: str) -> dict:
    """Datos de prueba para desarrollo sin API keys funcionales"""
    time.sleep(0.3)
    return {
        "nombre": nombre,
        "rating": 4.3,
        "total_resenas": 28,
        "direccion": f"Av. Ejemplo 123, {ciudad}",
        "tiene_web": True,
        "telefono": "+52 81 1234 5678",
        "horario": "Lun-Dom 11:00-22:00",
        "categorias": "Restaurante / Comida rápida",
        "fuente": "mock",
        "nota": "⚠️ Datos de prueba - configurar API keys en .env para datos reales"
    }

@mcp.tool()
def buscar_negocio(nombre: str, ciudad: str) -> str:
    """Busca negocio en Google Maps usando el proveedor configurado"""
    try:
        # Lógica de fallback inteligente
        if PROVIDER == "google" and GOOGLE_API_KEY:
            datos = _buscar_con_google(nombre, ciudad)
            if "error" in datos and datos.get("fallback") == "mock":
                log_error(f"Google API falló, usando mock para: {nombre}")
                datos = _buscar_mock(nombre, ciudad)
        elif PROVIDER == "serpapi" and SERPAPI_KEY:
            datos = _buscar_con_serpapi(nombre, ciudad)
            if "error" in datos and datos.get("fallback") == "mock":
                log_error(f"SerpAPI falló, usando mock para: {nombre}")
                datos = _buscar_mock(nombre, ciudad)
        elif PROVIDER == "serper" and SERPER_API_KEY:
            datos = _buscar_con_serper(nombre, ciudad)
            if "error" in datos and datos.get("fallback") == "mock":
                log_error(f"Serper API falló, usando mock para: {nombre}")
                datos = _buscar_mock(nombre, ciudad)
        else:
            # Default a mock si no hay provider válido
            datos = _buscar_mock(nombre, ciudad)
        
        return json.dumps(datos, ensure_ascii=False)
    
    except Exception as e:
        # ⚠️ ÚLTIMA LÍNEA DE DEFENSA: Nunca lanzar excepción
        log_error(f"EXCEPCIÓN EN buscar_negocio: {str(e)}\n{traceback.format_exc()}")
        return json.dumps({
            "error": f"Error crítico en buscar_negocio: {str(e)[:80]}", 
            "fallback": "mock",
            "debug": str(e)[:100]
        }, ensure_ascii=False)

def _buscar_red_con_serpapi(red: str, nombre_negocio: str) -> dict:
    if not SERPAPI_KEY:
        return {"url": "", "existe": False, "status": "no_key"}
        
    url = "https://serpapi.com/search.json"
    domain = "instagram.com" if red == "instagram" else "facebook.com"
    params = {
        "engine": "google",
        "q": f"{nombre_negocio} site:{domain}",
        "api_key": SERPAPI_KEY,
        "num": 1,
        "hl": "es"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            resultados = data.get("organic_results", [])
            if resultados:
                link = resultados[0].get("link", "")
                if domain in link:
                    return {"url": link, "existe": True, "status": 200, "fuente": "serpapi"}
        return {"url": f"https://www.{domain}/", "existe": False, "status": 404, "fuente": "serpapi"}
    except Exception as e:
        log_error(f"Error SerpAPI web search para {red}: {e}")
        return {"url": f"https://www.{domain}/", "existe": False, "status": "error"}

def _buscar_red_con_serper(red: str, nombre_negocio: str) -> dict:
    if not SERPER_API_KEY:
        return {"url": "", "existe": False, "status": "no_key"}
        
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    domain = "instagram.com" if red == "instagram" else "facebook.com"
    payload = {
        "q": f"{nombre_negocio} site:{domain}",
        "gl": "mx",
        "hl": "es",
        "num": 1
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            resultados = data.get("organic", [])
            if resultados:
                link = resultados[0].get("link", "")
                if domain in link:
                    return {"url": link, "existe": True, "status": 200, "fuente": "serper"}
        return {"url": f"https://www.{domain}/", "existe": False, "status": 404, "fuente": "serper"}
    except Exception as e:
        log_error(f"Error Serper web search para {red}: {e}")
        return {"url": f"https://www.{domain}/", "existe": False, "status": "error"}

def _buscar_red_con_searxng(red: str, nombre_negocio: str) -> dict:
    """Verifica red social vía SearXNG propio. Mismo shape que serpapi/serper.
    Lanza excepción si no hay instancia (el llamador cae al siguiente provider)."""
    import urllib.parse
    domain = "instagram.com" if red == "instagram" else "facebook.com"
    url = (f"{SEARXNG_URL}/search?q="
           f"{urllib.parse.quote(f'{nombre_negocio} site:{domain}')}"
           f"&format=json&language=es-MX")
    res = requests.get(url, timeout=15)
    res.raise_for_status()
    for r in (res.json().get("results", []) or [])[:5]:
        link = r.get("url", "")
        if domain in link:
            return {"url": link, "existe": True, "status": 200, "fuente": "searxng"}
    return {"url": f"https://www.{domain}/", "existe": False, "status": 404, "fuente": "searxng"}

@mcp.tool()
def verificar_redes(nombre_negocio: str) -> str:
    """Verifica existencia de Instagram y Facebook"""
    try:
        resultados = {}
        redes = ["instagram", "facebook"]

        # 0. SearXNG primero (gratis, propio): por red, con caída al provider.
        if SEARXNG_URL:
            pendientes = []
            for red in redes:
                try:
                    resultados[red] = _buscar_red_con_searxng(red, nombre_negocio)
                except Exception as e:
                    log_error(f"SearXNG no disponible para {red} ({str(e)[:50]}), sigo con {PROVIDER}")
                    pendientes.append(red)
            if not pendientes:
                return json.dumps(resultados, ensure_ascii=False)
            redes = pendientes

        # 1. Intentar con SerpAPI / Serper si están configurados
        if PROVIDER == "serpapi" and SERPAPI_KEY:
            for red in redes:
                resultados[red] = _buscar_red_con_serpapi(red, nombre_negocio)
            return json.dumps(resultados, ensure_ascii=False)
        elif PROVIDER == "serper" and SERPER_API_KEY:
            for red in redes:
                resultados[red] = _buscar_red_con_serper(red, nombre_negocio)
            return json.dumps(resultados, ensure_ascii=False)
            
        # 2. Modo Mock (por defecto en local si no hay API keys)
        if PROVIDER == "mock":
            import time, random
            time.sleep(0.5)
            nombre_limpio = nombre_negocio.replace(" ", "").lower()
            return json.dumps({
                "instagram": {"url": f"https://instagram.com/{nombre_limpio}", "existe": random.choice([True, False]), "status": 200, "fuente": "mock"},
                "facebook": {"url": f"https://facebook.com/{nombre_limpio}", "existe": random.choice([True, False]), "status": 200, "fuente": "mock"}
            }, ensure_ascii=False)
            
        # 3. Fallback a HTTP ingenuo (si es google pero no tenemos SerpAPI para web)
        nombre_limpio = nombre_negocio.replace(" ", "").lower()
        urls = {
            "instagram": f"https://www.instagram.com/{nombre_limpio}/",
            "facebook": f"https://www.facebook.com/{nombre_limpio}/"
        }
        
        for red, url in urls.items():
            try:
                # Usar GET y User-Agent de Bot para evitar redirecciones agresivas
                headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
                r = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
                content = r.text.lower()
                
                # Heurística simple
                if r.status_code == 200 and "page not found" not in content and "página no encontrada" not in content:
                    resultados[red] = {"url": url, "existe": True, "status": 200, "fuente": "http"}
                else:
                    resultados[red] = {"url": url, "existe": False, "status": r.status_code, "fuente": "http"}
            except Exception as e:
                log_error(f"Error HTTP fallback verificando {red}: {str(e)[:50]}")
                resultados[red] = {"url": url, "existe": False, "status": "error", "fuente": "http"}
        
        return json.dumps(resultados, ensure_ascii=False)
    
    except Exception as e:
        # ⚠️ ÚLTIMA LÍNEA DE DEFENSA
        log_error(f"EXCEPCIÓN EN verificar_redes: {str(e)}\n{traceback.format_exc()}")
        return json.dumps({
            "error": f"Error crítico en verificar_redes: {str(e)[:80]}",
            "debug": str(e)[:100]
        }, ensure_ascii=False)

@mcp.tool()
def buscar_competidores(categoria: str, ciudad: str) -> str:
    """Busca 3 competidores directos en la misma ciudad y categoría usando SerpAPI (Google Maps)"""
    try:
        if PROVIDER == "serpapi" and SERPAPI_KEY:
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_maps",
                "q": f"mejores {categoria} en {ciudad}",
                "type": "search",
                "api_key": SERPAPI_KEY,
                "hl": "es",
                "gl": "mx"
            }
            res = requests.get(url, params=params, timeout=15)
            if res.status_code == 200:
                data = res.json()
                competidores = []
                for lugar in data.get("local_results", [])[:3]:
                    competidores.append({
                        "nombre": lugar.get("title", ""),
                        "rating": lugar.get("rating", "N/A"),
                        "resenas": lugar.get("reviews", 0)
                    })
                return json.dumps(competidores, ensure_ascii=False)
        elif PROVIDER == "serper" and SERPER_API_KEY:
            url = "https://google.serper.dev/maps"
            headers = {
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "q": f"mejores {categoria} en {ciudad}",
                "gl": "mx",
                "hl": "es"
            }
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                competidores = []
                for lugar in data.get("maps", [])[:3]:
                    competidores.append({
                        "nombre": lugar.get("title", ""),
                        "rating": lugar.get("rating", "N/A"),
                        "resenas": lugar.get("reviews", 0)
                    })
                return json.dumps(competidores, ensure_ascii=False)
                
        # Mock / Fallback
        import time
        time.sleep(0.5)
        return json.dumps([
            {"nombre": f"Competidor 1 de {categoria}", "rating": 4.5, "resenas": 120},
            {"nombre": f"Competidor 2 de {categoria}", "rating": 4.0, "resenas": 80},
            {"nombre": f"Competidor 3 de {categoria}", "rating": 4.8, "resenas": 200}
        ], ensure_ascii=False)
    except Exception as e:
        log_error(f"Error en buscar_competidores: {e}")
        return json.dumps([{"error": str(e)}], ensure_ascii=False)

def _buscar_presencia_con_searxng(query: str) -> list:
    """Presencia web vía SearXNG propio (`/search?format=json`).
    Devuelve lista [{titulo, link, snippet}] o lanza excepción (el llamador
    cae a serper/serpapi → mock con la cadena existente)."""
    import urllib.parse
    url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json&language=es-MX"
    res = requests.get(url, timeout=15)
    res.raise_for_status()
    data = res.json()
    resultados = []
    for r in (data.get("results", []) or [])[:5]:
        if r.get("title") and r.get("url"):
            resultados.append({
                "titulo": r.get("title", ""),
                "link": r.get("url", ""),
                "snippet": r.get("content", ""),
                "fuente": "searxng",
            })
    if not resultados:
        raise ValueError("SearXNG sin resultados útiles")
    return resultados

@mcp.tool()
def buscar_presencia_web(query: str) -> str:
    """Busca menciones generales, noticias o presencia web de una marca"""
    try:
        # 0. SearXNG primero (gratis, propio, sin key): fail-fast si no hay instancia.
        if SEARXNG_URL:
            try:
                return json.dumps(_buscar_presencia_con_searxng(query), ensure_ascii=False)
            except Exception as e:
                log_error(f"SearXNG no disponible ({str(e)[:60]}), sigo con {PROVIDER}")
        if PROVIDER == "serpapi" and SERPAPI_KEY:
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 3,
                "hl": "es"
            }
            res = requests.get(url, params=params, timeout=15)
            if res.status_code == 200:
                data = res.json()
                resultados = []
                for res_org in data.get("organic_results", [])[:3]:
                    resultados.append({
                        "titulo": res_org.get("title", ""),
                        "link": res_org.get("link", ""),
                        "snippet": res_org.get("snippet", "")
                    })
                return json.dumps(resultados, ensure_ascii=False)
        elif PROVIDER == "serper" and SERPER_API_KEY:
            url = "https://google.serper.dev/search"
            headers = {
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "q": query,
                "gl": "mx",
                "hl": "es",
                "num": 3
            }
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                resultados = []
                for res_org in data.get("organic", [])[:3]:
                    resultados.append({
                        "titulo": res_org.get("title", ""),
                        "link": res_org.get("link", ""),
                        "snippet": res_org.get("snippet", "")
                    })
                return json.dumps(resultados, ensure_ascii=False)
                
        # Mock / Fallback
        import time
        time.sleep(0.5)
        return json.dumps([
            {"titulo": f"Mención de {query} en directorio local", "link": "https://directorio.mx", "snippet": "Excelente servicio en la ciudad."},
            {"titulo": f"{query} - Reseñas de clientes", "link": "https://reviews.com", "snippet": "Opiniones mixtas sobre la marca."}
        ], ensure_ascii=False)
    except Exception as e:
        log_error(f"Error en buscar_presencia_web: {e}")
        return json.dumps([{"error": str(e)}], ensure_ascii=False)

if __name__ == "__main__":
    # Asegurar encoding UTF-8 para Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
        except Exception:
            pass
    
    try:
        log_error(f"🚀 Servidor MCP iniciado | Proveedor: {PROVIDER.upper()} | Modo: stdio")
        mcp.run()
    except Exception as e:
        log_error(f"❌ CRASH FATAL en servidor MCP: {str(e)}\n{traceback.format_exc()}")
        sys.exit(1)
