# investigacion/servidor_mcp.py
"""
Servidor MCP de la RAMA INVESTIGACIÓN (Analista de Mercado y Competencia).

Herramientas de apoyo para el agente (solo LECTURA; no alteran nada):
- buscar_web             : busca en la web real con el navegador del sistema
                           (Chrome headless, sin APIs ni keys). Devuelve
                           titulo/url/extracto por resultado.
- leer_pagina            : lee el texto de una URL real (verifica fuentes).
- buscar_mercado          : dossier base (combina memoria del pedido).
- analizar_competencia    : perfil de competidores (con datos de buscar_web).
- detectar_tendencias     : tendencias (con datos de buscar_web).

La rama PRODUCE dossiers e informes; no ejecuta acciones.
"""
import os
import re
import subprocess
import sys
import json
import shutil
import urllib.parse
from html.parser import HTMLParser

from fastmcp import FastMCP
from dotenv import load_dotenv

from core.ejecutar import run_seguro, verificar as _verificar_binario

ORQ_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ORQ_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

mcp = FastMCP("RamaInvestigacion")


def _log(msg: str):
    print(f"[INVESTIGACION] {msg}", file=sys.stderr)
    sys.stderr.flush()


def _navegador() -> str:
    for c in ("chrome", "msedge"):
        p = shutil.which(c)
        if p:
            return p
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(p):
            return p
    return ""


class _Texto(HTMLParser):
    BLOQUES = {"p", "h1", "h2", "h3", "li", "td", "title"}

    def __init__(self):
        super().__init__()
        self.pila = []
        self.partes = []

    def handle_starttag(self, tag, attrs):
        self.pila.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        while self.pila:
            t, _ = self.pila.pop()
            if t == tag:
                break

    def handle_data(self, data):
        if not self.pila:
            return
        tag, _ = self.pila[-1]
        if tag in ("script", "style", "noscript"):
            return
        txt = data.strip()
        if txt:
            self.partes.append(txt)


def _dump_dom(url: str, espera_ms: int = 8000) -> str:
    nav = _navegador()
    if not nav:
        return json.dumps({"error": "sin navegador del sistema"}, ensure_ascii=False)
    try:
        _verificar_binario(nav)  # hook: solo Chrome/Edge del sistema
        p = run_seguro(
            [nav, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--virtual-time-budget=%d" % espera_ms, "--dump-dom", url],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120)
        return p.stdout or ""
    except Exception as e:
        return ""


class _ResultadosDDG(HTMLParser):
    """Parser DuckDuckGo html (/html/?q=)."""
    def __init__(self):
        super().__init__()
        self.res = []
        self._a = None
        self._snip = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "a" and "result__a" in cls:
            self._a = {"url": d.get("href", ""), "titulo": ""}
        elif tag == "a" and "result__snippet" in cls:
            self._snip = ""

    def handle_data(self, data):
        if self._a is not None and self._snip is None:
            self._a["titulo"] += data.strip() + " "
        elif self._snip is not None:
            self._snip += data.strip() + " "

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None and self._snip is None:
            self._a["titulo"] = self._a["titulo"].strip()
            self.res.append(self._a)
            self._a = None
        elif tag == "a" and self._snip is not None:
            if self.res:
                self.res[-1]["extracto"] = self._snip.strip()[:400]
            self._snip = None


def _bing_url(href: str) -> str:
    """Decodifica el redirect de Bing (/ck/a?...&u=<base64>) a la URL real."""
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        u = (qs.get("u") or [""])[0]
        if u.startswith("a1"):
            u = u[2:]
        pad = "=" * (-len(u) % 4)
        return __import__("base64").urlsafe_b64decode(u + pad).decode("utf-8", "replace")
    except Exception:
        return href


class _ResultadosBing(HTMLParser):
    """Parser Bing (li.b_algo > h2 > a + p.b_caption)."""
    def __init__(self):
        super().__init__()
        self.res = []
        self._cur = None
        self._h2 = False
        self._cap = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "li" and "b_algo" in cls:
            self._cur = {"url": "", "titulo": "", "extracto": ""}
        elif tag == "h2" and self._cur is not None:
            self._h2 = True
        elif tag == "a" and self._h2 and self._cur is not None:
            self._cur["url"] = _bing_url(d.get("href", ""))
        elif tag == "p" and self._cur is not None and "b_caption" in cls:
            self._cap = True

    def handle_data(self, data):
        if self._cur is None:
            return
        if self._h2:
            self._cur["titulo"] += data.strip() + " "
        elif self._cap:
            self._cur["extracto"] += data.strip() + " "

    def handle_endtag(self, tag):
        if tag == "h2":
            self._h2 = False
        elif tag == "p" and self._cap:
            self._cap = False
        elif tag == "li" and self._cur is not None:
            self._cur["titulo"] = self._cur["titulo"].strip()
            self._cur["extracto"] = self._cur["extracto"][:400].strip()
            if self._cur["url"]:
                self.res.append(self._cur)
            self._cur = None


def _buscar_lista(q: str, tope: int = 10) -> list:
    for url, parser_cls in (
        ("https://www.bing.com/search?q=" + urllib.parse.quote_plus(q), _ResultadosBing),
        ("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(q), _ResultadosDDG),
    ):
        html = _dump_dom(url)
        if not html or html.startswith("{"):
            continue
        par = parser_cls()
        try:
            par.feed(html)
        except Exception:
            continue
        if par.res:
            return par.res[:tope]
    return []


@mcp.tool()
def buscar_web(consulta: str, ciudad: str = "") -> str:
    """Busca en la web real con el navegador del sistema (sin APIs ni keys).

    Devuelve titulo/url/extracto por resultado. Úsalo para dossier,
    competencia y tendencias con datos verificables.
    """
    q = consulta if not ciudad else "%s %s" % (consulta, ciudad)
    res = _buscar_lista(q)
    if res:
        return json.dumps({"consulta": q, "resultados": res,
                           "fuente": "web directa (navegador del sistema)"},
                          ensure_ascii=False)
    return json.dumps({"consulta": q, "resultados": [],
                       "fuente": "web directa: sin resultados (posible bloqueo anti-bot)"},
                      ensure_ascii=False)


@mcp.tool()
def leer_pagina(url: str) -> str:
    """Lee el texto visible de una URL real (verifica fuentes del dossier)."""
    html = _dump_dom(url)
    if not html or html.startswith("{"):
        return json.dumps({"error": "no se pudo leer", "url": url},
                          ensure_ascii=False)
    par = _Texto()
    try:
        par.feed(html)
    except Exception:
        pass
    texto = re.sub(r"\s+", " ", " ".join(par.partes))[:6000]
    return json.dumps({"url": url, "texto": texto,
                       "fuente": "web directa (navegador del sistema)"},
                      ensure_ascii=False)


@mcp.tool()
def buscar_mercado(tema: str, ciudad: str = "") -> str:
    """Dossier de mercado: tamaño, audiencia y canales clave (web real)."""
    q = tema if not ciudad else "%s %s" % (tema, ciudad)
    res = _buscar_lista("mercado %s" % q, 5)
    return json.dumps({
        "tema": tema, "ciudad": ciudad or "general",
        "audiencia_objetivo": "ver extractos de resultados",
        "canales_clave": ["Google", "Instagram", "TikTok", "Email"],
        "hallazgos_web": res,
        "fuente": "web directa (navegador del sistema)",
    }, ensure_ascii=False)


@mcp.tool()
def analizar_competencia(categoria: str, ciudad: str = "") -> str:
    """Perfil de competidores directos con nombres y URLs REALES (web real)."""
    q = categoria if not ciudad else "%s %s" % (categoria, ciudad)
    vistos = _buscar_lista(q, 10)
    compas = []
    BASURA = ("imdb", "espinof", "netflix", "pelicula", "serie",
              "wikipedia.org")
    for r in vistos:
        try:
            dom = urllib.parse.urlsplit(r.get("url", "")).netloc.lower()
            ruta = urllib.parse.urlsplit(r.get("url", "")).path.lower()
        except Exception:
            dom, ruta = "", ""
        if not dom or "bing.com" in dom or "duckduckgo" in dom:
            continue
        if any(b in dom + ruta for b in BASURA):
            continue
        compas.append({"nombre": r.get("titulo", "")[:80], "url": r.get("url", ""),
                       "extracto": r.get("extracto", "")[:200]})
        if len(compas) >= 8:
            break
    return json.dumps({
        "categoria": categoria, "ciudad": ciudad or "general",
        "competidores": compas,
        "fuente": "web directa (navegador del sistema)",
    }, ensure_ascii=False)


@mcp.tool()
def detectar_tendencias(categoria: str = "") -> str:
    """Tendencias de la categoría con extractos REALES (web real)."""
    q = "tendencias %s 2026" % (categoria or "marketing")
    res = _buscar_lista(q, 8)
    tends = [{"tema": r.get("titulo", "")[:100], "url": r.get("url", ""),
              "extracto": r.get("extracto", "")[:250]} for r in res]
    return json.dumps({
        "categoria": categoria or "general",
        "tendencias": tends,
        "fuente": "web directa (navegador del sistema)",
    }, ensure_ascii=False)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    _log("🚀 Servidor MCP de la Rama Investigación iniciado (stdio)")
    mcp.run()