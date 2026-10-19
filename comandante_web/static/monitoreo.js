/* Monitoreo de ramas: estado del puente + Ãºltimo evento + gates. */
(function () {
  var NOMBRES = {
    planeacion: "Estratega", contenido: "Copywriter", redes: "Community Manager",
    analitica: "Analista KPI", investigacion: "Analista Mercado",
    atencion_cliente: "Soporte", auditoria: "Auditor Huella"
  };

  async function cargar() {
    var data;
    try {
      data = await Comandante.req("/api/monitoreo", {});
    } catch (e) {
      Comandante.toast("Puente/panel no disponible: " + e.message, true);
      return;
    }
    var pill = document.getElementById("puente-estado");
    var est = (data && data.estado) || {};
    var ok = est.ok !== false && !est.error;
    pill.textContent = "puente: " + (ok ? "arriba (" + (est.uptime_s || 0) + " s)" : "caÃ­do");
    pill.className = "pill " + (ok ? "ok" : "err");

    var ramas = (est.ramas) || Object.keys(NOMBRES);
    var runs = est.runs || {};
    var ult = est.ultimos || {};
    var trabajando = {};
    Object.keys(runs).forEach(function (id) {
      var r = runs[id];
      if (r && r.rama) trabajando[r.rama] = r;
    });
    var html = ramas.map(function (r) {
      var t = trabajando[r];
      var u = ult[r];
      var estado = t ? ("trabajando desde " + (t.inicio || "?")) :
        (u ? ("Ãºltimo: " + (u.evento || u.siguiente || "?")) : "idle");
      var cls = t ? "warn" : (u ? "ok" : "");
      var det = u && u.resumen ? "<p class='muted'>" + Comandante.esc(u.resumen) + "</p>" : "";
      var gate = (u && u.requiere_gate) ?
        "<button class='btn small' data-gate='" + r + "'>Pedir gate</button>" : "";
      return "<div class='card'><h4>" + Comandante.esc(NOMBRES[r] || r) +
        " <span class='badge " + cls + "'>" + Comandante.esc(r) + "</span></h4>" +
        "<p>" + Comandante.esc(estado) + "</p>" + det + gate + "</div>";
    }).join("");
    document.getElementById("ramas").innerHTML = html || "<p>Sin ramas.</p>";

    var gates = data.gates_pendientes || [];
    document.getElementById("gates-count").textContent = gates.length;
    document.getElementById("gates").innerHTML = gates.map(function (g) {
      return "<div class='card'><h4>#" + g.id + " " + Comandante.esc(g.tipo || "") + "</h4>" +
        "<p>" + Comandante.esc(g.detalle || "") + "</p>" +
        "<button class='btn small ok' data-aprobar='" + g.id + "'>Aprobar</button> " +
        "<button class='btn small danger' data-rechazar='" + g.id + "'>Rechazar</button></div>";
    }).join("") || "<p>Sin gates pendientes.</p>";
  }

  async function post(url, body) {
    return await Comandante.req(url, { method: "POST", body: JSON.stringify(body || {}) });
  }

  document.addEventListener("click", async function (ev) {
    var t = ev.target;
    if (t.dataset && t.dataset.gate) {
      try {
        await post("/api/aprobaciones", { tipo: "gate", detalle: "Gate rama " + t.dataset.gate, borrador: "" });
        Comandante.toast("Gate creado para " + t.dataset.gate);
        cargar();
      } catch (e) { Comandante.toast(e.message, true); }
    }
    if (t.dataset && (t.dataset.aprobar || t.dataset.rechazar)) {
      var id = t.dataset.aprobar || t.dataset.rechazar;
      var dec = t.dataset.aprobar ? "aprobada" : "rechazada";
      try {
        await post("/api/aprobaciones/" + id + "/resolver", { decision: dec });
        Comandante.toast("Gate #" + id + " " + dec);
        cargar();
      } catch (e) { Comandante.toast(e.message, true); }
    }
  });

  document.getElementById("btn-actualizar").addEventListener("click", cargar);
  cargar();
  setInterval(cargar, 10000);
})();
