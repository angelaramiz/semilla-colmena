// app.js

document.addEventListener('DOMContentLoaded', () => {
    // --- ELEMENTOS DEL DOM ---
    const authContainer = document.getElementById('auth-container');
    const loginCard = document.getElementById('login-card');
    const registerCard = document.getElementById('register-card');
    const pendingContainer = document.getElementById('pending-container');
    const appContainer = document.getElementById('app-container');
    
    // Auth Forms & Indicators
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const loginError = document.getElementById('login-error');
    const registerError = document.getElementById('register-error');
    const linkToRegister = document.getElementById('link-to-register');
    const linkToLogin = document.getElementById('link-to-login');
    const btnLogout = document.getElementById('btn-logout');
    const userInfo = document.getElementById('user-info');
    const currentUsername = document.getElementById('current-username');
    const userBadge = document.getElementById('user-badge');
    const btnCheckStatus = document.getElementById('btn-check-status');

    // Audit Form
    const auditForm = document.getElementById('audit-form');
    const btnSubmit = document.getElementById('btn-submit');
    const btnText = btnSubmit.querySelector('.btn-text');
    const btnLoader = btnSubmit.querySelector('.btn-loader');
    const consoleLog = document.getElementById('console-log');
    const btnClearLog = document.getElementById('btn-clear-log');
    
    // Tabs Navigation
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const tabReportBtn = document.getElementById('tab-report-btn');
    const tabAdminBtn = document.getElementById('tab-admin-btn');
    const reportView = document.getElementById('report-view');
    
    // Admin Dashboard
    const adminUsersList = document.getElementById('admin-users-list');

    // --- ESTADO GLOBAL ---
    let token = localStorage.getItem('jwt_token');
    let currentUser = null;
    let eventSource = null;

    // --- INICIALIZACIÓN DE LA APLICACIÓN (SPA ROUTER) ---
    async function initApp() {
        // Panel abierto (obrero = consola de operaciones sin cuentas):
        // sin token válido se entra como invitado en vez del muro de login.
        if (!token) {
            try {
                const info = await fetch('/api/arbol/info').then(r => r.json());
                if (info && info.auth_requerida === false) {
                    entrarComoInvitado();
                    return;
                }
            } catch (e) { /* si /api/arbol/info falla, se sigue al login normal */ }
            showView('auth');
            return;
        }

        try {
            const res = await fetch('/api/auth/me', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!res.ok) {
                throw new Error("Token inválido");
            }

            currentUser = await res.json();
            
            // Actualizar datos de usuario en la barra superior
            currentUsername.textContent = currentUser.username;
            userBadge.textContent = currentUser.role;
            userBadge.className = `badge ${currentUser.role}`;
            userInfo.classList.remove('hidden');
            btnLogout.classList.remove('hidden');

            // Enrutar según estado del usuario
            if (currentUser.role === 'admin' || currentUser.status === 'approved') {
                showView('app');
                if (currentUser.role === 'admin') {
                    tabAdminBtn.classList.remove('hidden');
                } else {
                    tabAdminBtn.classList.add('hidden');
                }
            } else {
                showView('pending');
                updatePendingView(currentUser.status);
            }
        } catch (err) {
            console.error("Error de sesión:", err);
            try {
                const info = await fetch('/api/arbol/info').then(r => r.json());
                if (info && info.auth_requerida === false) { entrarComoInvitado(); return; }
            } catch (e2) {}
            logout();
        }
    }

    function entrarComoInvitado() {
        // Panel abierto (obrero): consola de operaciones sin cuentas.
        // Admin/gates siguen exigiendo login real en sus endpoints.
        currentUser = { username: 'operador', role: 'invitado', status: 'approved' };
        token = '';
        try { localStorage.removeItem('jwt_token'); } catch (e) {}
        currentUsername.textContent = 'operador local';
        userBadge.textContent = 'invitado';
        userInfo.classList.remove('hidden');
        btnLogout.classList.add('hidden');
        tabAdminBtn.classList.add('hidden');
        showView('app');
    }

    function showView(view) {
        authContainer.classList.add('hidden');
        pendingContainer.classList.add('hidden');
        appContainer.classList.add('hidden');

        if (view === 'auth') {
            authContainer.classList.remove('hidden');
            loginCard.classList.remove('hidden');
            registerCard.classList.add('hidden');
            userInfo.classList.add('hidden');
            btnLogout.classList.add('hidden');
        } else if (view === 'pending') {
            pendingContainer.classList.remove('hidden');
        } else if (view === 'app') {
            appContainer.classList.remove('hidden');
            tabBtns[0].click(); // Activar pestaña de consola por defecto
        }
    }

    function updatePendingView(status) {
        const title = pendingContainer.querySelector('h2');
        const icon = pendingContainer.querySelector('.pending-icon');
        const desc = pendingContainer.querySelector('p');
        
        if (status === 'rejected') {
            icon.textContent = "❌";
            title.textContent = "Acceso Rechazado";
            title.style.color = "var(--error)";
            desc.textContent = "Tu solicitud de acceso ha sido denegada por el administrador.";
        } else {
            icon.textContent = "⏳";
            title.textContent = "Acceso en Espera";
            title.style.color = "var(--warning)";
            desc.textContent = "Tu cuenta se encuentra pendiente de aprobación.";
        }
    }

    function logout() {
        localStorage.removeItem('jwt_token');
        token = null;
        currentUser = null;
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        showView('auth');
    }

    btnLogout.addEventListener('click', logout);
    btnCheckStatus.addEventListener('click', initApp);

    // --- MANEJO DE REGISTRO E INICIO DE SESIÓN ---

    // Alternar tarjetas
    linkToRegister.addEventListener('click', (e) => {
        e.preventDefault();
        loginCard.classList.add('hidden');
        registerCard.classList.remove('hidden');
        registerError.classList.add('hidden');
    });

    linkToLogin.addEventListener('click', (e) => {
        e.preventDefault();
        registerCard.classList.add('hidden');
        loginCard.classList.remove('hidden');
        loginError.classList.add('hidden');
    });

    // Enviar Login
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(data.detail || "Error al iniciar sesión");
            }

            token = data.access_token;
            localStorage.setItem('jwt_token', token);
            loginError.classList.add('hidden');
            loginForm.reset();
            await initApp();
        } catch (err) {
            loginError.textContent = err.message;
            loginError.classList.remove('hidden');
        }
    });

    // Enviar Registro
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('register-username').value.trim();
        const email = document.getElementById('register-email').value.trim();
        const password = document.getElementById('register-password').value;

        try {
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || "Error en el registro");
            }

            registerError.classList.add('hidden');
            registerForm.reset();
            // Mostrar login y avisar que fue exitoso
            registerCard.classList.add('hidden');
            loginCard.classList.remove('hidden');
            loginError.className = "alert alert-success";
            loginError.textContent = "Cuenta creada. Espera a que el administrador apruebe tu acceso.";
            loginError.classList.remove('hidden');
        } catch (err) {
            registerError.textContent = err.message;
            registerError.classList.remove('hidden');
        }
    });

    // --- NAVEGACIÓN Y TABS ---
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.disabled) return;
            
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const targetTab = document.getElementById(btn.dataset.tab);
            if (targetTab) targetTab.classList.add('active');

            // Cargar usuarios si entra a la pestaña de administración
            if (btn.id === 'tab-admin-btn') {
                loadAdminUsers();
            }
        });
    });

    btnClearLog.addEventListener('click', () => {
        consoleLog.innerHTML = '<div class="log-line system">Log de consola limpiado. Listo para iniciar.</div>';
    });

    function appendLogLine(message, type = 'info') {
        const line = document.createElement('div');
        line.className = `log-line ${type}`;
        line.textContent = message;
        consoleLog.appendChild(line);
        consoleLog.scrollTop = consoleLog.scrollHeight;
    }

    // --- FORMULARIO DE AUDITORÍA CON STREAMING SSE ---
    auditForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const negocio = document.getElementById('negocio').value.trim();
        const ciudad = document.getElementById('ciudad').value.trim();
        const sitio = document.getElementById('sitio').value.trim();
        const ig = document.getElementById('ig').value.trim();
        const fb = document.getElementById('fb').value.trim();
        const modelo_negocio = document.getElementById('modelo-negocio').value;
        const contexto = document.getElementById('contexto').value.trim();
        const modo = document.getElementById('modo').value;

        if (!negocio || !ciudad) return;

        // Cambiar estado de interfaz
        btnSubmit.disabled = true;
        btnText.textContent = "⏳ Ejecutando...";
        btnLoader.classList.remove('hidden');
        tabReportBtn.disabled = true;
        
        // Pestaña de logs activa
        tabBtns[0].click();
        appendLogLine(`\n--- 🔄 INICIANDO AUDITORÍA DIGITAL: ${negocio} ---`, 'system');

        if (eventSource) {
            eventSource.close();
        }

        // Construir parámetros agregando el token JWT necesario
        const params = new URLSearchParams({
            negocio,
            ciudad,
            modo,
            sitio,
            ig,
            fb,
            modelo_negocio,
            contexto,
            token // Inyectamos el JWT de la sesión
        });

        eventSource = new EventSource(`/api/audit-stream?${params.toString()}`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'status') {
                    appendLogLine(data.message, 'system');
                } else if (data.type === 'log') {
                    let logType = 'info';
                    const msg = data.message.toLowerCase();
                    if (msg.includes('error') || msg.includes('falló') || msg.includes('critico') || msg.includes('crasheo')) {
                        logType = 'error';
                    } else if (msg.includes('ok') || msg.includes('exitosamente') || msg.includes('correcto') || msg.includes('conectado')) {
                        logType = 'success';
                    } else if (msg.includes('advertencia') || msg.includes('warning') || msg.includes('atención')) {
                        logType = 'warning';
                    }
                    appendLogLine(data.message, logType);
                } else if (data.type === 'fase') {
                    renderFase(data);
                    appendLogLine(`➡️ ${data.detalle}`, 'system');
                } else if (data.type === 'result') {
                    appendLogLine("🎉 Auditoría completada con éxito. Procesando reporte...", "success");
                    renderReport(data.report);
                    
                    tabReportBtn.disabled = false;
                    tabReportBtn.click();
                    
                    cleanupConnection();
                } else if (data.type === 'error') {
                    appendLogLine(`❌ Error: ${data.message}`, 'error');
                    cleanupConnection();
                }
            } catch (err) {
                console.error("Error parsing message event:", err);
            }
        };

        eventSource.onerror = (err) => {
            appendLogLine("⚠️ La conexión con el servidor se interrumpió de forma inesperada.", "error");
            cleanupConnection();
        };
    });

    function cleanupConnection() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        btnSubmit.disabled = false;
        btnText.textContent = "🚀 Iniciar Auditoría";
        btnLoader.classList.add('hidden');
        cargarProcesos();
    }

    // --- PESTAÑA GLOBAL: PROCESOS EN EJECUCIÓN (fases, no % a ciegas) ---
    function fmtTranscurrido(s) {
        s = s || 0;
        const m = Math.floor(s / 60), ss = s % 60;
        return m > 0 ? `${m}m ${ss}s` : `${ss}s`;
    }
    function escProc(t) {
        return String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;');
    }
    function renderProcesosTab(procs) {
        const c = document.getElementById('procesos-view');
        if (!c) return;
        if (!procs || !procs.length) {
            c.innerHTML = '<div class="no-report-placeholder"><span class="placeholder-icon">⚙️</span><h3>Sin procesos en ejecución</h3><p>Inicia una auditoría para ver aquí sus fases en vivo.</p></div>';
            return;
        }
        c.innerHTML = procs.map(p => {
            const fases = p.fases || [];
            const idx = p.idx || 0;
            const vivo = p.estado === 'en_curso';
            const pasos = fases.map((f, i) => {
                const cls = i < idx ? 'done' : (i === idx && vivo ? 'now' : (i === idx && !vivo ? (p.estado === 'completada' ? 'done' : 'bad') : 'todo'));
                const mark = i < idx || (!vivo && p.estado === 'completada') ? '✓' : (i === idx && vivo ? '▶' : '○');
                return `<div class="fase ${cls}"><span class="fase-mark">${mark}</span><span>${escProc(f)}</span></div>`;
            }).join('');
            const badge = vivo ? '<span class="proc-badge run">EN CURSO</span>'
                : (p.estado === 'completada' ? '<span class="proc-badge ok">COMPLETADA</span>' : `<span class="proc-badge bad">${escProc(p.estado || '').toUpperCase()}</span>`);
            return `<div class="proc-card"><div class="proc-head"><strong>${escProc(p.titulo)}</strong>${badge}</div><div class="proc-time">⏱ ${fmtTranscurrido(p.transcurrido_s)}</div><div class="proc-fases">${pasos}</div><div class="proc-detalle">${escProc(p.detalle || '')}</div></div>`;
        }).join('');
    }
    function renderFase(data) {
        // Evento en vivo: reconstruye vista mínima (1 proceso) y refresca lista.
        if (data && data.fases) {
            renderProcesosTab([{ id: data.report_id || 'x', tipo: 'auditoria', titulo: data.detalle || 'Auditoría', estado: 'en_curso', fases: data.fases, idx: data.fase_idx || 0, detalle: data.detalle || '', transcurrido_s: 0 }]);
        }
        cargarProcesos();
    }
    async function cargarProcesos() {
        try {
            const res = await fetch('/api/procesos');
            if (!res.ok) return;
            const j = await res.json();
            renderProcesosTab(j.procesos || []);
        } catch (e) { /* silencioso: no tapar la consola */ }
    }
    setInterval(() => { if (!document.hidden) cargarProcesos(); }, 8000);
    cargarProcesos();

    // --- PANEL DE ADMINISTRACIÓN ---
    async function loadAdminUsers() {
        try {
            const res = await fetch('/api/admin/users', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!res.ok) {
                throw new Error("No se pudo obtener la lista de usuarios");
            }

            const users = await res.json();
            renderAdminUsers(users);
        } catch (err) {
            console.error("Error de administración:", err);
        }
    }

    function renderAdminUsers(users) {
        adminUsersList.innerHTML = '';

        if (users.length === 0) {
            adminUsersList.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay usuarios registrados.</td></tr>';
            return;
        }

        users.forEach(user => {
            const tr = document.createElement('tr');
            
            // Badge del estado
            let badgeClass = 'pending';
            if (user.status === 'approved') badgeClass = 'approved';
            else if (user.status === 'rejected') badgeClass = 'rejected';

            // Deshabilitar botones si el usuario es el mismo admin conectado
            const isSelf = user.username === currentUser.username;
            const disabledAttr = isSelf ? 'disabled' : '';

            tr.innerHTML = `
                <td><strong>${user.username}</strong></td>
                <td>${user.email}</td>
                <td><span class="badge ${user.role}">${user.role}</span></td>
                <td><span class="badge ${badgeClass}">${user.status}</span></td>
                <td>
                    <div class="admin-actions">
                        <button class="btn-small btn-approve" data-id="${user.id}" ${disabledAttr} ${user.status === 'approved' ? 'style="opacity: 0.5;"' : ''}>Aprobar</button>
                        <button class="btn-small btn-reject" data-id="${user.id}" ${disabledAttr} ${user.status === 'rejected' ? 'style="opacity: 0.5;"' : ''}>Rechazar</button>
                        <button class="btn-small btn-delete" data-id="${user.id}" ${disabledAttr}>Eliminar</button>
                    </div>
                </td>
            `;

            // Asignar listeners a los botones de acción
            if (!isSelf) {
                tr.querySelector('.btn-approve').addEventListener('click', () => updateUserStatus(user.id, 'approve'));
                tr.querySelector('.btn-reject').addEventListener('click', () => updateUserStatus(user.id, 'reject'));
                tr.querySelector('.btn-delete').addEventListener('click', () => deleteUser(user.id));
            }

            adminUsersList.appendChild(tr);
        });
    }

    async function updateUserStatus(userId, action) {
        try {
            const res = await fetch(`/api/admin/users/${userId}/${action}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Error al actualizar estado del usuario");
            }

            // Recargar lista
            await loadAdminUsers();
        } catch (err) {
            alert(err.message);
        }
    }

    async function deleteUser(userId) {
        if (!confirm("¿Estás seguro de que deseas eliminar este usuario permanentemente?")) return;

        try {
            const res = await fetch(`/api/admin/users/${userId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Error al eliminar usuario");
            }

            await loadAdminUsers();
        } catch (err) {
            alert(err.message);
        }
    }

    // --- RENDERIZADO DEL REPORTE ESTRATÉGICO ---
    function renderReport(report) {
        const cliente = report.cliente_gancho || {};
        const mercadologa = report.interno_mercadologa || {};
        const ingeniero = report.interno_ingeniero || {};

        const score = cliente.score || 0;
        const resumen = cliente.resumen_ejecutivo || "Sin resumen ejecutivo provisto.";
        const plataformas = cliente.plataformas_encontradas || {};
        const dolores = cliente.puntos_dolor_urgentes || [];

        const estrategia = mercadologa.estrategia_recomendada || "Sin recomendaciones estratégicas.";
        const servicios = mercadologa.servicios_a_ofrecer || [];

        const viabilidad = ingeniero.viabilidad_automatizacion || "Sin análisis de ingeniería.";
        const flujos = ingeniero.flujos_n8n_sugeridos || [];

        let scoreClass = 'low';
        if (score >= 70) scoreClass = 'high';
        else if (score >= 40) scoreClass = 'medium';

        reportView.innerHTML = `
            <div class="score-card">
                <div class="score-circle ${scoreClass}">
                    <span class="score-value">${score}</span>
                    <span class="score-label">Score</span>
                </div>
                <div class="score-meta">
                    <h3>Resumen del Diagnóstico</h3>
                    <p>${resumen}</p>
                </div>
            </div>

            <div class="results-grid">
                <div class="card">
                    <h4>🗺️ Canales Digitales</h4>
                    <ul class="checklist">
                        <li class="checklist-item">
                            <span class="chk-icon">${plataformas.google_maps ? '✅' : '❌'}</span>
                            <span style="color: ${plataformas.google_maps ? 'var(--success)' : 'var(--error)'}">Google Maps (Perfil público)</span>
                        </li>
                        <li class="checklist-item">
                            <span class="chk-icon">${plataformas.sitio_web ? '✅' : '❌'}</span>
                            <span style="color: ${plataformas.sitio_web ? 'var(--success)' : 'var(--error)'}">Sitio Web</span>
                        </li>
                        <li class="checklist-item">
                            <span class="chk-icon">${plataformas.instagram ? '✅' : '❌'}</span>
                            <span style="color: ${plataformas.instagram ? 'var(--success)' : 'var(--error)'}">Instagram</span>
                        </li>
                        <li class="checklist-item">
                            <span class="chk-icon">${plataformas.facebook ? '✅' : '❌'}</span>
                            <span style="color: ${plataformas.facebook ? 'var(--success)' : 'var(--error)'}">Facebook</span>
                        </li>
                    </ul>
                </div>

                <div class="card">
                    <h4>🚨 Puntos de Dolor Urgentes</h4>
                    <ul class="bullet-list">
                        ${dolores.map(dolor => `<li>${dolor}</li>`).join('') || '<li>Ninguno detectado.</li>'}
                    </ul>
                </div>

                <div class="card" style="grid-column: span 2;">
                    <h4 style="color: var(--warning)">🎯 Propuesta Estratégica de Venta</h4>
                    <p style="font-size: 0.9rem; margin-bottom: 1rem; color: #d1d5db;">${estrategia}</p>
                    <h5 style="font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-main);">Servicios a Cotizar:</h5>
                    <ul class="bullet-list" style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                        ${servicios.map(serv => `<li>${serv}</li>`).join('') || '<li>No especificados.</li>'}
                    </ul>
                </div>

                <div class="card" style="grid-column: span 2; border-color: rgba(139, 92, 246, 0.3);">
                    <h4 style="color: var(--purple)">⚙️ Viabilidad de Automatización (Sistemas)</h4>
                    <p style="font-size: 0.9rem; margin-bottom: 1rem; color: #d1d5db;">${viabilidad}</p>
                    <h5 style="font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-main);">Flujos n8n Sugeridos:</h5>
                    <ul class="bullet-list">
                        ${flujos.map(flujo => `<li>${flujo}</li>`).join('') || '<li>Ninguno propuesto.</li>'}
                    </ul>
                </div>
            </div>
        `;
    }

    // Arrancar la verificación al cargar la página
    initApp();
});
