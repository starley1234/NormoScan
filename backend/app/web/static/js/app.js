// NormoScan Web UI - Minimal llamacpp-style

const API = {
    async request(method, path, data = null, isForm = false) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) {
            if (isForm) {
                opts.body = data;
                delete opts.headers['Content-Type'];
            } else {
                opts.body = JSON.stringify(data);
            }
        }
        const resp = await fetch(`/api${path}`, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        return resp.json();
    },
    get(path) { return this.request('GET', path); },
    post(path, data) { return this.request('POST', path, data); },
    postForm(path, formData) { return this.request('POST', path, formData, true); }
};

function toast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('ru-RU', { 
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

function statusBadge(status) {
    const map = {
        'done': 'badge-success',
        'queued': 'badge-warning',
        'processing': 'badge-info',
        'failed': 'badge-error',
        'dead_letter': 'badge-error',
        'dedupe': 'badge-info'
    };
    return `<span class="badge ${map[status] || ''}">${status}</span>`;
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

function logout() {
    localStorage.removeItem('normoscan_token');
    window.location.href = '/web/login';
}

async function checkHealth() {
    try {
        const resp = await fetch('/health');
        const data = await resp.json();
        const el = document.getElementById('health-status');
        if (el) el.className = 'status-indicator ' + (data.status === 'ok' ? 'ok' : '');
    } catch {
        const el = document.getElementById('health-status');
        if (el) el.className = 'status-indicator';
    }
}

// Auth
async function login(username, password) {
    const form = new FormData();
    form.append('username', username);
    form.append('password', password);
    
    const resp = await fetch('/api/auth/login', {
        method: 'POST',
        body: form
    });
    
    if (!resp.ok) {
        throw new Error('Неверный логин или пароль');
    }
    
    const data = await resp.json();
    localStorage.setItem('normoscan_token', data.access_token);
    localStorage.setItem('normoscan_role', data.role);
    localStorage.setItem('normoscan_username', data.username);
    return data;
}

function getToken() {
    return localStorage.getItem('normoscan_token');
}

function getAuthHeaders() {
    const token = getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

// API with auth
const authApi = {
    async request(method, path, data = null, isForm = false) {
        const opts = {
            method,
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' }
        };
        if (data) {
            if (isForm) {
                opts.body = data;
                delete opts.headers['Content-Type'];
            } else {
                opts.body = JSON.stringify(data);
            }
        }
        const resp = await fetch(`/api${path}`, opts);
        if (resp.status === 401) {
            logout();
            throw new Error('Сессия истекла');
        }
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        return resp.json();
    },
    get(path) { return this.request('GET', path); },
    post(path, data) { return this.request('POST', path, data); },
    postForm(path, formData) { return this.request('POST', path, formData, true); },
    delete(path) { return this.request('DELETE', path); }
};

// File upload with progress
async function uploadFile(file, priority = 5, onProgress = null) {
    const formData = new FormData();
    formData.append('file', file);
    
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `/api/checks/upload?priority=${priority}`);
        xhr.setRequestHeader('Authorization', `Bearer ${getToken()}`);
        
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable && onProgress) {
                onProgress(Math.round(e.loaded / e.total * 100));
            }
        };
        
        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve(JSON.parse(xhr.responseText));
            } else {
                reject(new Error(JSON.parse(xhr.responseText)?.detail || 'Upload failed'));
            }
        };
        
        xhr.onerror = () => reject(new Error('Network error'));
        xhr.send(formData);
    });
}

// Poll check status
async function pollUntilDone(checkId, interval = 1000) {
    return new Promise((resolve, reject) => {
        const check = async () => {
            try {
                const data = await authApi.get(`/checks/${checkId}`);
                if (data.status === 'done' || data.status === 'failed' || data.status === 'dead_letter') {
                    resolve(data);
                } else {
                    setTimeout(check, interval);
                }
            } catch (err) {
                reject(err);
            }
        };
        check();
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    setInterval(checkHealth, 30000);
});
