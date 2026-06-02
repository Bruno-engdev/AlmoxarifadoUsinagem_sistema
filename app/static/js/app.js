/* ============================================================
   Tool Crib – Custom JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    // ------------------------------------------------------------------
    // Hamburger nav drawer
    // ------------------------------------------------------------------
    const navToggleBtn     = document.getElementById('navToggleBtn');
    const navDrawer        = document.getElementById('navDrawer');
    const navDrawerOverlay = document.getElementById('navDrawerOverlay');
    const appFeedbackRegion = document.getElementById('appFeedbackRegion');
    const navDrawerGroups = navDrawer ? Array.from(navDrawer.querySelectorAll('[data-drawer-group]')) : [];
    let drawerReturnFocusTo = null;
    let unreadCountErrorVisible = false;

    function showAppFeedback(message, variant = 'danger') {
        if (!appFeedbackRegion || !message) return;

        const alert = document.createElement('div');
        alert.className = `alert alert-${variant} alert-dismissible fade show app-feedback-toast`;
        alert.setAttribute('role', 'alert');
        alert.innerHTML = `
            <div class="d-flex align-items-start gap-2">
                <i class="bi ${variant === 'danger' ? 'bi-exclamation-triangle' : 'bi-info-circle'} mt-1"></i>
                <div class="flex-grow-1">${message}</div>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Fechar"></button>
            </div>
        `;

        appFeedbackRegion.appendChild(alert);
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 6000);
    }

    function getDrawerFocusableElements() {
        if (!navDrawer) return [];
        return Array.from(
            navDrawer.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')
        ).filter(function (element) {
            if (element.hasAttribute('disabled') || element.getAttribute('aria-hidden') === 'true') {
                return false;
            }

            const style = window.getComputedStyle(element);
            return style.visibility !== 'hidden' && style.display !== 'none';
        });
    }

    function closeOtherDrawerGroups(currentGroup) {
        navDrawerGroups.forEach(function (group) {
            if (group !== currentGroup) {
                setDrawerGroupOpen(group, false);
            }
        });
    }

    function setDrawerGroupOpen(group, isOpen) {
        if (!group) return;
        group.classList.toggle('is-open', isOpen);
        const toggle = group.querySelector('[data-drawer-toggle]');
        if (toggle) {
            toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }
    }

    function initializeDrawerState() {
        navDrawerGroups.forEach(function (group) {
            setDrawerGroupOpen(group, false);
        });
    }


    function openDrawer() {
        drawerReturnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : navToggleBtn;
        navDrawer.classList.add('open');
        navDrawerOverlay.classList.add('open');
        navToggleBtn.classList.add('open');
        navToggleBtn.setAttribute('aria-expanded', 'true');
        navDrawer.setAttribute('aria-hidden', 'false');
        window.setTimeout(function () {
            const focusable = getDrawerFocusableElements();
            if (focusable.length) {
                focusable[0].focus();
            } else {
                navDrawer.focus();
            }
        }, 0);
    }

    function closeDrawer(options) {
        const shouldRestoreFocus = !options || options.restoreFocus !== false;
        initializeDrawerState();
        navDrawer.classList.remove('open');
        navDrawerOverlay.classList.remove('open');
        navToggleBtn.classList.remove('open');
        navToggleBtn.setAttribute('aria-expanded', 'false');
        navDrawer.setAttribute('aria-hidden', 'true');
        if (shouldRestoreFocus && drawerReturnFocusTo && typeof drawerReturnFocusTo.focus === 'function') {
            drawerReturnFocusTo.focus();
        }
    }

    if (navToggleBtn && navDrawer) {
        initializeDrawerState();

        navToggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            navDrawer.classList.contains('open') ? closeDrawer() : openDrawer();
        });
        navDrawerOverlay.addEventListener('click', closeDrawer);

        navDrawer.querySelectorAll('[data-drawer-toggle]').forEach(function (toggle) {
            toggle.addEventListener('click', function () {
                const group = toggle.closest('[data-drawer-group]');
                const nextState = !group.classList.contains('is-open');
                closeOtherDrawerGroups(group);
                setDrawerGroupOpen(group, nextState);
            });
        });

        navDrawerGroups.forEach(function (group) {
            group.addEventListener('mouseenter', function () {
                closeOtherDrawerGroups(group);
                setDrawerGroupOpen(group, true);
            });

            group.addEventListener('mouseleave', function () {
                setDrawerGroupOpen(group, false);
            });

            group.addEventListener('focusin', function () {
                closeOtherDrawerGroups(group);
                setDrawerGroupOpen(group, true);
            });

            group.addEventListener('focusout', function (event) {
                if (!group.contains(event.relatedTarget)) {
                    setDrawerGroupOpen(group, false);
                }
            });
        });

        navDrawer.querySelectorAll('.nav-drawer-link').forEach(function (link) {
            link.addEventListener('click', function () {
                closeDrawer({ restoreFocus: false });
            });
        });
        document.addEventListener('keydown', function (e) {
            if (!navDrawer.classList.contains('open')) return;

            if (e.key === 'Escape') {
                closeDrawer();
                return;
            }

            if (e.key !== 'Tab') return;

            const focusable = getDrawerFocusableElements();
            if (!focusable.length) {
                e.preventDefault();
                navDrawer.focus();
                return;
            }

            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            const activeElement = document.activeElement;

            if (e.shiftKey && activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });
    }

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
    // Notifications – badge count + modal content
    // ------------------------------------------------------------------
    const notifBadge = document.getElementById('notifBadge');
    const notifBell = document.getElementById('notificationBell');
    const notifModalBody = document.getElementById('notifModalBody');
    const markAllBtn = document.getElementById('markAllReadBtn');
    const notifModal = document.getElementById('notificationModal');

    function assertOk(response) {
        if (!response.ok) {
            throw new Error('request-failed');
        }
        return response;
    }

    function setNotificationBellLabel(count) {
        if (!notifBell) return;
        const suffix = count > 0 ? ` (${count} não lidas)` : '';
        notifBell.setAttribute('aria-label', `Abrir notificações${suffix}`);
    }

    function fetchUnreadCount() {
        fetch('/api/notifications/unread-count')
            .then(assertOk)
            .then(r => r.json())
            .then(data => {
                unreadCountErrorVisible = false;
                if (data.count > 0) {
                    notifBadge.textContent = data.count > 99 ? '99+' : data.count;
                    notifBadge.classList.remove('d-none');
                } else {
                    notifBadge.classList.add('d-none');
                }
                setNotificationBellLabel(data.count || 0);
            })
            .catch(() => {
                if (!unreadCountErrorVisible) {
                    showAppFeedback('Não foi possível atualizar o contador de notificações.', 'warning');
                    unreadCountErrorVisible = true;
                }
            });
    }

    function fetchNotifications() {
        notifModalBody.innerHTML = '<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm" role="status"></div> Carregando...</div>';
        fetch('/api/notifications')
            .then(assertOk)
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
                showAppFeedback('Não foi possível carregar as notificações agora.', 'danger');
            });
    }

    function markAllRead() {
        if (!markAllBtn) return;
        markAllBtn.disabled = true;
        fetch('/api/notifications/mark-all-read', { method: 'POST' })
            .then(assertOk)
            .then(r => r.json())
            .then(() => {
                fetchNotifications();
                fetchUnreadCount();
                showAppFeedback('Notificações marcadas como lidas.', 'success');
            })
            .catch(() => {
                showAppFeedback('Não foi possível marcar as notificações como lidas.', 'danger');
            })
            .finally(() => {
                markAllBtn.disabled = false;
            });
    }

    function refreshAlerts() {
        const btn = document.getElementById('refreshAlertsBtn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Verificando...';
        }
        fetch('/api/notifications/refresh', { method: 'POST' })
            .then(assertOk)
            .then(r => r.json())
            .then(data => {
                fetchNotifications();
                fetchUnreadCount();
                if (data.new_alerts > 0) {
                    showAppFeedback(`${data.new_alerts} novo(s) alerta(s) de estoque foram encontrados.`, 'success');
                } else {
                    showAppFeedback('Nenhum novo alerta de estoque foi encontrado.', 'success');
                }
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Atualizar';
                }
            })
            .catch(() => {
                showAppFeedback('Não foi possível atualizar os alertas de estoque.', 'danger');
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

    // ------------------------------------------------------------------
    // Tools – column selector for search bar
    // ------------------------------------------------------------------
    const searchColBtn   = document.getElementById('searchColBtn');
    const searchColInput = document.getElementById('searchColInput');
    const searchColLabel = document.getElementById('searchColLabel');
    const searchInput    = document.getElementById('searchInput');

    const colPlaceholders = {
        'all':       'Buscar por nome ou tipo...',
        'name':      'Buscar por nome...',
        'origin_id': 'Buscar por ID origem...',
        'tool_type': 'Buscar por tipo...',
        'location':  'Buscar por localização (ex: G1D5)...',
        'status':    'Crítico, Baixo ou OK...',
    };

    if (searchColBtn && searchColInput) {
        document.querySelectorAll('#searchColMenu .dropdown-item').forEach(function (item) {
            item.addEventListener('click', function (e) {
                e.preventDefault();
                const col = this.dataset.col;
                searchColInput.value = col;
                if (searchColLabel) searchColLabel.textContent = this.textContent.trim();
                if (searchInput) searchInput.placeholder = colPlaceholders[col] || 'Buscar...';
                // Mark active item
                document.querySelectorAll('#searchColMenu .dropdown-item').forEach(i => i.classList.remove('active'));
                this.classList.add('active');
            });
        });

        // Highlight the currently active option on page load
        const currentCol = searchColInput.value || 'all';
        const activeItem = document.querySelector(`#searchColMenu .dropdown-item[data-col="${currentCol}"]`);
        if (activeItem) activeItem.classList.add('active');
        if (searchInput && colPlaceholders[currentCol]) {
            searchInput.placeholder = colPlaceholders[currentCol];
        }
    }
});
