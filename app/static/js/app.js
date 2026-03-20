/* ============================================================
   Tool Crib – Custom JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    // ------------------------------------------------------------------
    // Auto-dismiss Bootstrap alerts after 8 seconds
    // ------------------------------------------------------------------
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 8000);
    });

    // ------------------------------------------------------------------
    // Sidebar – mobile toggle (< lg)
    // ------------------------------------------------------------------
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggleBtn = document.getElementById('sidebarToggleMobile');

    function closeSidebar() {
        if (sidebar) sidebar.classList.remove('expanded');
        if (overlay) overlay.classList.remove('show');
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('expanded');
            overlay.classList.toggle('show');
        });
    }
    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    // ------------------------------------------------------------------
    // Notifications – badge count + modal content
    // ------------------------------------------------------------------
    const notifBadge = document.getElementById('notifBadge');
    const notifBell = document.getElementById('notificationBell');
    const notifModalBody = document.getElementById('notifModalBody');
    const markAllBtn = document.getElementById('markAllReadBtn');
    const notifModal = document.getElementById('notificationModal');

    function fetchUnreadCount() {
        fetch('/api/notifications/unread-count')
            .then(r => r.json())
            .then(data => {
                if (data.count > 0) {
                    notifBadge.textContent = data.count > 99 ? '99+' : data.count;
                    notifBadge.classList.remove('d-none');
                } else {
                    notifBadge.classList.add('d-none');
                }
            })
            .catch(() => {});
    }

    function fetchNotifications() {
        notifModalBody.innerHTML = '<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm" role="status"></div> Carregando...</div>';
        fetch('/api/notifications')
            .then(r => r.json())
            .then(data => {
                if (!data.length) {
                    notifModalBody.innerHTML = '<div class="text-center text-muted py-4"><i class="bi bi-check-circle fs-3 d-block mb-2"></i>Nenhuma notificação</div>';
                    return;
                }
                // Sort: unread+critical first, then unread, then read
                data.sort((a, b) => {
                    const scoreA = (!a.is_read ? 2 : 0) + (a.is_critical ? 1 : 0);
                    const scoreB = (!b.is_read ? 2 : 0) + (b.is_critical ? 1 : 0);
                    return scoreB - scoreA;
                });
                let html = '';
                data.forEach(n => {
                    const cls = n.is_read ? '' : ' unread';
                    const iconCls = n.is_critical ? 'bi-exclamation-triangle-fill text-danger' : 'bi-exclamation-circle text-warning';
                    const criticalTag = n.is_critical ? ' <span class="badge bg-danger" style="font-size:0.65rem;">Crítica</span>' : '';
                    const cleared = n.cleared_at ? ' <span class="badge bg-success" style="font-size:0.65rem;">Resolvido</span>' : '';
                    const toolLink = n.tool_id ? '/tools/' + n.tool_id : '#';
                    html += `<a href="${toolLink}" class="notif-item-link" data-bs-dismiss="modal">
                        <div class="notif-item${cls}" data-id="${n.id}">
                            <i class="bi ${iconCls} notif-icon"></i>
                            <div class="notif-body">
                                <div class="notif-title">${n.tool_name}${criticalTag}${cleared}</div>
                                <div class="notif-detail">Estoque: <strong>${n.current_stock}</strong> / Mín: <strong>${n.min_stock}</strong></div>
                            </div>
                            <span class="notif-time">${n.created_at}</span>
                        </div>
                    </a>`;
                });
                notifModalBody.innerHTML = html;
            })
            .catch(() => {
                notifModalBody.innerHTML = '<div class="text-center text-danger py-4">Erro ao carregar notificações.</div>';
            });
    }

    function markAllRead() {
        fetch('/api/notifications/mark-all-read', { method: 'POST' })
            .then(() => {
                fetchNotifications();
                fetchUnreadCount();
            })
            .catch(() => {});
    }

    function refreshAlerts() {
        const btn = document.getElementById('refreshAlertsBtn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Verificando...';
        }
        fetch('/api/notifications/refresh', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                fetchNotifications();
                fetchUnreadCount();
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Atualizar';
                }
            })
            .catch(() => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Atualizar';
                }
            });
    }

    // Wire events
    if (notifModal) {
        notifModal.addEventListener('show.bs.modal', fetchNotifications);
    }
    if (markAllBtn) {
        markAllBtn.addEventListener('click', markAllRead);
    }
    const refreshBtn = document.getElementById('refreshAlertsBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshAlerts);
    }

    // Initial badge fetch + poll every 30s
    if (notifBadge) {
        fetchUnreadCount();
        setInterval(fetchUnreadCount, 30000);
    }
});
