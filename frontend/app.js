/**
 * Karyawan AI — Dashboard App
 * Main JavaScript: API calls, rendering, real-time polling
 */

// ============================================
// CONFIG
// ============================================
const API_BASE = window.location.origin + '/api';
const POLL_INTERVAL = 5000; // 5 detik

let pollTimer = null;
let dashboardData = null;

// Check auth token
const token = localStorage.getItem('karyawan_token');
if (!token) {
    window.location.href = '/login.html';
}

function getAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('karyawan_token')}`
    };
}

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initEventListeners();
    fetchDashboard();
    fetchServers();
    fetchHealthMetrics();
    startPolling();
});

// ============================================
// CLOCK
// ============================================
function initClock() {
    const clockEl = document.getElementById('clock');
    function updateClock() {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString('id-ID', {
            hour: '2-digit',
            minute: '2-digit',
        });
    }
    updateClock();
    setInterval(updateClock, 1000);
}

// ============================================
// EVENT LISTENERS
// ============================================
function initEventListeners() {
    // Send command
    const sendBtn = document.getElementById('send-btn');
    const commandInput = document.getElementById('command-input');

    sendBtn.addEventListener('click', sendCommand);
    commandInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendCommand();
        }
    });

    // Auto-resize textarea
    commandInput.addEventListener('input', () => {
        commandInput.style.height = 'auto';
        commandInput.style.height = Math.min(commandInput.scrollHeight, 120) + 'px';
    });

    // Modal close handlers
    document.getElementById('modal-close').addEventListener('click', closeTaskModal);
    document.getElementById('task-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeTaskModal();
    });

    document.getElementById('emp-modal-close').addEventListener('click', closeEmployeeModal);
    document.getElementById('employee-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeEmployeeModal();
    });
    
    // Server Panel
    const refreshServersBtn = document.getElementById('refresh-servers-btn');
    if (refreshServersBtn) {
        refreshServersBtn.addEventListener('click', fetchServers);
    }
}

// ============================================
// POLLING (Data, Servers & Health)
// ============================================
async function fetchDashboard() {
    try {
        const res = await fetch(`${API_BASE}/dashboard`, {
            headers: getAuthHeaders()
        });
        
        if (res.status === 401) {
            localStorage.removeItem('karyawan_token');
            window.location.href = '/login.html';
            return;
        }
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        dashboardData = await res.json();

        renderStats(dashboardData.stats);
        renderEmployees(dashboardData.employees);
        renderActivity(dashboardData.recent_activity);
        populateEmployeeSelect(dashboardData.employees);
        setConnectionStatus(true);
        
        // Fetch servers periodically but less often
        if (!window.lastServerFetch || Date.now() - window.lastServerFetch > 30000) {
            fetchServers();
            window.lastServerFetch = Date.now();
        }
    } catch (err) {
        console.error('Dashboard fetch error:', err);
        setConnectionStatus(false);
    }
}

async function fetchServers() {
    const grid = document.getElementById('server-grid');
    const btn = document.getElementById('refresh-servers-btn');
    
    if (btn) btn.classList.add('loading');
    if (!grid.innerHTML.includes('server-card')) {
        grid.innerHTML = '<div class="server-loading">Memeriksa koneksi SSH ke server...</div>';
    }
    
    try {
        const res = await fetch(`${API_BASE}/servers/status`, {
            headers: getAuthHeaders()
        });
        
        if (res.status === 401) {
            localStorage.removeItem('karyawan_token');
            window.location.href = '/login.html';
            return;
        }
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const servers = await res.json();
        
        renderServers(servers);
    } catch (err) {
        console.error('Servers fetch error:', err);
        grid.innerHTML = `<div class="server-loading" style="color:var(--status-error)">Gagal mengambil status server.</div>`;
    } finally {
        if (btn) btn.classList.remove('loading');
    }
}

async function fetchHealthMetrics() {
    try {
        const res = await fetch(`${API_BASE}/servers/health_metrics`, {
            headers: getAuthHeaders()
        });
        
        if (res.status === 401) {
            localStorage.removeItem('karyawan_token');
            window.location.href = '/login.html';
            return;
        }
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const metrics = await res.json();
        
        const grid = document.getElementById('health-grid');
        grid.innerHTML = '';
        
        ['server1', 'server2'].forEach((srv, idx) => {
            const data = metrics[srv];
            if (!data) return;
            
            const serverName = idx === 0 ? 'Server 1 (Produksi)' : 'Server 2 (Backup)';
            const isWarningRam = data.ram_percent > 85;
            const isWarningDisk = data.disk_percent > 85;
            
            grid.innerHTML += `
                <div class="health-card">
                    <div class="health-server-name">${serverName}</div>
                    
                    <div class="health-metric">
                        <div class="health-metric-header">
                            <span>RAM (${data.ram_used_mb}MB / ${data.ram_total_mb}MB)</span>
                            <span class="${isWarningRam ? 'warning-text' : ''}">${data.ram_percent}%</span>
                        </div>
                        <div class="health-bar-bg">
                            <div class="health-bar-fill ${isWarningRam ? 'warning-bg' : ''}" style="width: ${data.ram_percent}%"></div>
                        </div>
                    </div>
                    
                    <div class="health-metric">
                        <div class="health-metric-header">
                            <span>Disk Usage</span>
                            <span class="${isWarningDisk ? 'warning-text' : ''}">${data.disk_percent}%</span>
                        </div>
                        <div class="health-bar-bg">
                            <div class="health-bar-fill ${isWarningDisk ? 'warning-bg' : ''}" style="width: ${data.disk_percent}%"></div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        if (grid.innerHTML === '') {
            grid.innerHTML = '<div class="server-loading">Gagal memuat data metrik.</div>';
        }
    } catch (err) {
        console.error('Health metrics fetch error:', err);
        const grid = document.getElementById('health-grid');
        grid.innerHTML = '<div class="server-loading" style="color:var(--status-error)">Gagal mengambil metrik server.</div>';
    }
}

async function executeServerAction(appId, actionName) {
    if (!confirm(`Apakah Anda yakin ingin menjalankan aksi '${actionName}' untuk aplikasi ini?`)) return;
    
    const btnId = `btn-${appId}`;
    const btn = document.getElementById(btnId);
    const originalText = btn.textContent;
    
    btn.disabled = true;
    btn.textContent = 'Mengeksekusi...';
    
    try {
        const res = await fetch(`${API_BASE}/servers/action`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ app_id: appId, action: actionName }),
        });
        
        if (res.status === 401) {
            localStorage.removeItem('karyawan_token');
            window.location.href = '/login.html';
            return;
        }
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Gagal mengeksekusi');
        
        showFeedback(data.message, 'success');
        setTimeout(fetchServers, 2000); // refresh status
    } catch (err) {
        showFeedback(err.message, 'error');
        alert("Error:\n" + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function sendCommand() {
    const select = document.getElementById('employee-select');
    const input = document.getElementById('command-input');
    const sendBtn = document.getElementById('send-btn');
    const feedback = document.getElementById('command-feedback');

    const employeeName = select.value;
    const prompt = input.value.trim();

    if (!employeeName) {
        showFeedback('Pilih karyawan terlebih dahulu', 'error');
        return;
    }
    if (!prompt) {
        showFeedback('Tulis perintah terlebih dahulu', 'error');
        return;
    }

    // Disable UI
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<div class="spinner"></div>';

    try {
        const res = await fetch(`${API_BASE}/command`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                employee_name: employeeName,
                prompt: prompt,
            }),
        });
        
        if (res.status === 401) {
            localStorage.removeItem('karyawan_token');
            window.location.href = '/login.html';
            return;
        }

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || 'Gagal mengirim perintah');
        }

        showFeedback(data.message, 'success');
        input.value = '';
        input.style.height = 'auto';

        // Refresh dashboard segera
        setTimeout(fetchDashboard, 1000);
    } catch (err) {
        showFeedback(err.message, 'error');
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>`;
    }
}

async function fetchEmployeeTasks(employeeName) {
    try {
        const res = await fetch(`${API_BASE}/tasks?employee=${employeeName}&limit=20`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error('Fetch tasks error:', err);
        return [];
    }
}

async function fetchTaskDetail(taskId) {
    try {
        const res = await fetch(`${API_BASE}/tasks/${taskId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error('Fetch task detail error:', err);
        return null;
    }
}

// ============================================
// RENDERING
// ============================================
function renderStats(stats) {
    animateNumber('stat-working', stats.working);
    animateNumber('stat-done', stats.done_24h);
    animateNumber('stat-decision', stats.needs_decision);
    animateNumber('stat-error', stats.error);
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    const current = parseInt(el.textContent) || 0;
    if (current === target) return;

    const duration = 400;
    const steps = 20;
    const increment = (target - current) / steps;
    let step = 0;

    const timer = setInterval(() => {
        step++;
        el.textContent = Math.round(current + increment * step);
        if (step >= steps) {
            el.textContent = target;
            clearInterval(timer);
        }
    }, duration / steps);
}

function renderEmployees(employees) {
    const grid = document.getElementById('employee-grid');
    grid.innerHTML = employees.map(emp => `
        <div class="emp-card ${emp.status}" onclick="openEmployeeModal('${emp.name}')" title="${emp.description}">
            <div class="emp-tasks-count">${emp.total_tasks} task</div>
            <div class="emp-emoji">${emp.emoji}</div>
            <div class="emp-name">${emp.display_name}</div>
            <div class="emp-role">${emp.role}</div>
            <span class="emp-status-badge ${emp.status}">
                ${emp.status === 'working' ? '⚡ Kerja' : '💤 Idle'}
            </span>
        </div>
    `).join('');
}

function renderServers(servers) {
    const grid = document.getElementById('server-grid');
    
    if (!servers || servers.length === 0) {
        grid.innerHTML = '<div class="server-loading">Tidak ada data server</div>';
        return;
    }
    
    grid.innerHTML = servers.map(srv => {
        const isUp = srv.status === 'up';
        const actionLabel = isUp ? 'Restart' : 'Start';
        const actionName = isUp ? 'restart' : 'start';
        
        // Custom actions based on app id
        let btnHtml = `<button id="btn-${srv.id}" class="server-action-btn ${!isUp ? 'primary' : ''}" onclick="executeServerAction('${srv.id}', '${actionName}')">${actionLabel}</button>`;
        
        if (srv.id === 'timesheet_dev' || srv.id === 'ir_app') {
            btnHtml = `<button id="btn-${srv.id}" class="server-action-btn ${!isUp ? 'primary' : ''}" onclick="executeServerAction('${srv.id}', 'recreate')">Recreate tmux</button>`;
        }
        
        return `
            <div class="server-card ${srv.status}">
                <div class="server-card-header">
                    <div class="server-name">${escapeHtml(srv.name)}</div>
                    <div class="server-type">${escapeHtml(srv.type)}</div>
                </div>
                <div class="server-meta">${escapeHtml(srv.server)} • ${escapeHtml(srv.status.toUpperCase())}</div>
                ${btnHtml}
            </div>
        `;
    }).join('');
}

function renderActivity(activities) {
    const feed = document.getElementById('activity-feed');

    if (!activities || activities.length === 0) {
        feed.innerHTML = '<div class="activity-empty">Belum ada aktivitas</div>';
        return;
    }

    feed.innerHTML = activities.map(act => {
        const actionLabels = {
            task_created: 'membuat task baru',
            started: 'mulai bekerja',
            completed: 'selesai bekerja',
            error: 'mengalami error',
        };

        const label = actionLabels[act.action] || act.action;
        const time = act.timestamp ? formatTime(act.timestamp) : '';

        return `
            <div class="activity-item">
                <div class="activity-dot ${act.action}"></div>
                <div class="activity-content">
                    <div class="activity-title">
                        <strong>${capitalize(act.employee_name)}</strong> ${label}
                    </div>
                    ${act.detail ? `<div class="activity-detail">${escapeHtml(act.detail)}</div>` : ''}
                </div>
                <div class="activity-time">${time}</div>
            </div>
        `;
    }).join('');
}

function populateEmployeeSelect(employees) {
    const select = document.getElementById('employee-select');
    const currentValue = select.value;

    // Only repopulate if empty
    if (select.options.length <= 1) {
        employees.forEach(emp => {
            const option = document.createElement('option');
            option.value = emp.name;
            option.textContent = `${emp.emoji} ${emp.display_name} (${emp.role})`;
            select.appendChild(option);
        });
    }

    if (currentValue) {
        select.value = currentValue;
    }
}

// ============================================
// MODALS
// ============================================
async function openEmployeeModal(name) {
    const modal = document.getElementById('employee-modal');
    const title = document.getElementById('emp-modal-title');
    const taskList = document.getElementById('emp-modal-tasks');

    // Find employee info
    const emp = dashboardData?.employees?.find(e => e.name === name);
    title.textContent = emp ? `${emp.emoji} ${emp.display_name} — ${emp.role}` : name;

    // Show loading
    taskList.innerHTML = '<div class="activity-empty">Memuat riwayat...</div>';
    modal.classList.remove('hidden');

    // Fetch tasks
    const tasks = await fetchEmployeeTasks(name);

    if (tasks.length === 0) {
        taskList.innerHTML = '<div class="activity-empty">Belum ada riwayat task</div>';
        return;
    }

    taskList.innerHTML = tasks.map(task => `
        <div class="emp-task-item" onclick="openTaskModal('${task.id}')">
            <div class="emp-task-prompt">${escapeHtml(task.prompt)}</div>
            <div class="emp-task-meta">
                <span class="task-status-badge ${task.status}">${task.status}</span>
                <span class="emp-task-time">${task.created_at ? formatTime(task.created_at) : ''}</span>
            </div>
        </div>
    `).join('');
}

function closeEmployeeModal() {
    document.getElementById('employee-modal').classList.add('hidden');
}

async function openTaskModal(taskId) {
    const modal = document.getElementById('task-modal');
    const title = document.getElementById('modal-title');
    const meta = document.getElementById('modal-meta');
    const promptText = document.getElementById('modal-prompt-text');
    const resultText = document.getElementById('modal-result-text');

    // Show loading
    title.textContent = 'Memuat...';
    meta.innerHTML = '';
    promptText.textContent = '';
    resultText.textContent = '';
    modal.classList.remove('hidden');

    const task = await fetchTaskDetail(taskId);
    if (!task) {
        title.textContent = 'Error';
        resultText.textContent = 'Gagal memuat detail task';
        return;
    }

    title.textContent = `${capitalize(task.employee_name)} — Task Detail`;
    meta.innerHTML = `
        <span class="meta-tag">
            <span class="task-status-badge ${task.status}">${task.status}</span>
        </span>
        ${task.created_at ? `<span class="meta-tag">📅 ${formatDateTime(task.created_at)}</span>` : ''}
        ${task.completed_at ? `<span class="meta-tag">⏱️ ${formatDuration(task.created_at, task.completed_at)}</span>` : ''}
    `;
    promptText.textContent = task.prompt;
    resultText.textContent = task.result || task.error_message || 'Belum ada hasil (masih diproses...)';

    // Handle Confirmation Area
    const confirmArea = document.getElementById('modal-confirmation-area');
    const affectedData = document.getElementById('modal-affected-data');
    const btnConfirm = document.getElementById('btn-confirm-task');
    const btnCancel = document.getElementById('btn-cancel-task');

    // Remove old listeners
    const newBtnConfirm = btnConfirm.cloneNode(true);
    const newBtnCancel = btnCancel.cloneNode(true);
    btnConfirm.replaceWith(newBtnConfirm);
    btnCancel.replaceWith(newBtnCancel);

    if (task.status === 'needs_decision') {
        confirmArea.classList.remove('hidden');
        
        // Render affected rows if available
        if (task.affected_rows_json) {
            try {
                const rows = JSON.parse(task.affected_rows_json);
                if (rows.length === 0) {
                    affectedData.innerHTML = "<p>Tidak ada data yang terpengaruh (0 baris).</p>";
                } else {
                    const headers = Object.keys(rows[0]);
                    let tableHTML = '<table class="data-table"><thead><tr>';
                    headers.forEach(h => tableHTML += `<th>${escapeHtml(h)}</th>`);
                    tableHTML += '</tr></thead><tbody>';
                    
                    rows.forEach(row => {
                        tableHTML += '<tr>';
                        headers.forEach(h => tableHTML += `<td>${escapeHtml(String(row[h]))}</td>`);
                        tableHTML += '</tr>';
                    });
                    tableHTML += '</tbody></table>';
                    affectedData.innerHTML = tableHTML;
                }
            } catch (e) {
                affectedData.innerHTML = "<p>Gagal mem-parsing data pratinjau.</p>";
            }
        } else {
            affectedData.innerHTML = "<p>Preview data tidak tersedia.</p>";
        }

        newBtnConfirm.onclick = async () => {
            newBtnConfirm.disabled = true;
            newBtnConfirm.textContent = 'Mengeksekusi...';
            try {
                const res = await fetch(`${API_BASE}/command/${taskId}/confirm`, {
                    method: 'POST',
                    headers: getAuthHeaders()
                });
                const data = await res.json();
                if(!res.ok) throw new Error(data.detail || data.message);
                showFeedback(data.message, 'success');
                openTaskModal(taskId); // Refresh
            } catch (e) {
                alert("Error: " + e.message);
                newBtnConfirm.disabled = false;
                newBtnConfirm.textContent = 'Setujui & Eksekusi';
            }
        };

        newBtnCancel.onclick = async () => {
            newBtnCancel.disabled = true;
            newBtnCancel.textContent = 'Membatalkan...';
            try {
                const res = await fetch(`${API_BASE}/command/${taskId}/cancel`, {
                    method: 'POST',
                    headers: getAuthHeaders()
                });
                const data = await res.json();
                if(!res.ok) throw new Error(data.detail || data.message);
                showFeedback(data.message, 'success');
                openTaskModal(taskId); // Refresh
            } catch (e) {
                alert("Error: " + e.message);
                newBtnCancel.disabled = false;
                newBtnCancel.textContent = 'Batalkan';
            }
        };

    } else {
        confirmArea.classList.add('hidden');
    }
}

function closeTaskModal() {
    document.getElementById('task-modal').classList.add('hidden');
}

// ============================================
// POLLING
// ============================================
function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    
    // Poll dashboard & servers every 5s
    pollTimer = setInterval(() => {
        fetchDashboard();
        fetchServers();
    }, POLL_INTERVAL);
    
    // Poll health metrics every 15s to avoid overwhelming SSH
    setInterval(() => {
        fetchHealthMetrics();
    }, 15000);
}

function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
}

// Pause polling when tab is hidden
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopPolling();
    } else {
        fetchDashboard();
        fetchServers();
        fetchHealthMetrics();
        startPolling();
    }
});

// ============================================
// UTILITIES
// ============================================
function setConnectionStatus(connected) {
    const dot = document.getElementById('connection-status');
    dot.classList.toggle('connected', connected);
    dot.title = connected ? 'Terhubung ke server' : 'Terputus dari server';
}

function showFeedback(message, type) {
    const feedback = document.getElementById('command-feedback');
    feedback.textContent = message;
    feedback.className = `command-feedback ${type}`;

    // Auto hide after 4 seconds
    setTimeout(() => {
        feedback.classList.add('hidden');
    }, 4000);
}

function capitalize(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function formatTime(isoString) {
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);

        if (diff < 60) return 'baru saja';
        if (diff < 3600) return `${Math.floor(diff / 60)}m lalu`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}j lalu`;
        return date.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
    } catch {
        return '';
    }
}

function formatDateTime(isoString) {
    try {
        return new Date(isoString).toLocaleString('id-ID', {
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return '';
    }
}

function formatDuration(startIso, endIso) {
    try {
        const start = new Date(startIso);
        const end = new Date(endIso);
        const diff = Math.floor((end - start) / 1000);

        if (diff < 60) return `${diff} detik`;
        if (diff < 3600) return `${Math.floor(diff / 60)} menit`;
        return `${Math.floor(diff / 3600)} jam ${Math.floor((diff % 3600) / 60)} menit`;
    } catch {
        return '';
    }
}
