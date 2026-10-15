/* Utilidades compartidas del panel del Comandante. Sin dependencias. */
(function () {
  "use strict";

  var TOKEN_KEY = "comandante_token";

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY) || ""; }
    catch (e) { return ""; }
  }
  function setToken(v) {
    try { localStorage.setItem(TOKEN_KEY, v || ""); } catch (e) {}
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  async function req(url, opts) {
    opts = opts || {};
    var headers = {};
    var t = getToken();
    if (t) headers["X-Comandante-Token"] = t;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    var r = await fetch(url, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body !== undefined ? opts.body : undefined
    });
    var text = await r.text();
    var data = null;
    try { data = text ? JSON.parse(text) : null; }
    catch (e) { data = { raw: text }; }
    if (!r.ok) {
      var msg = (data && (data.detail || data.error)) || ("HTTP " + r.status);
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
  }

  var toastTimer = null;
  function toast(msg, isErr) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "show" + (isErr ? " err" : "");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.className = ""; }, 3600);
  }

  function badgeFor(estado) {
    var e = String(estado || "").toLowerCase();
    if (["online", "en_linea", "ok", "terminada", "completada", "listo"].indexOf(e) >= 0)
      return '<span class="badge ok">' + esc(estado) + "</span>";
    if (["en_curso", "en_cola", "desconocido", "unknown", "pendiente"].indexOf(e) >= 0)
      return '<span class="badge warn">' + esc(estado) + "</span>";
    if (["offline", "error", "fallo", "no"].indexOf(e) >= 0)
      return '<span class="badge err">' + esc(estado) + "</span>";
    if (estado) return '<span class="badge info">' + esc(estado) + "</span>";
    return '<span class="badge neutral">sin dato</span>';
  }

  function shortTime(v) {
    if (!v) return "—";
    return String(v).replace("T", " ").slice(0, 19);
  }

  function bindTokenBox() {
    var input = document.getElementById("token");
    if (!input) return;
    input.value = getToken();
    input.addEventListener("change", function () {
      setToken(input.value.trim());
      toast("Token guardado en este navegador.");
    });
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); input.blur(); setToken(input.value.trim()); toast("Token guardado en este navegador."); }
    });
  }

  function markNav() {
    var path = window.location.pathname || "/";
    var links = document.querySelectorAll(".nav a[data-route]");
    links.forEach(function (a) {
      var r = a.getAttribute("data-route");
      var on = (r === "/" && (path === "/" || path.endsWith("index.html"))) ||
               (r !== "/" && path.indexOf(r) === 0);
      if (on) a.classList.add("active");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindTokenBox();
    markNav();
  });

  window.Comandante = {
    req: req, esc: esc, toast: toast,
    getToken: getToken, setToken: setToken,
    badgeFor: badgeFor, shortTime: shortTime
  };
})();
