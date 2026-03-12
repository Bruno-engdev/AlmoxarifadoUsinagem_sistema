/* ============================================================
   Tool Crib – Custom JavaScript (Dark Theme)
   ============================================================ */

// Chart.js dark theme defaults
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#cdd6f4';
    Chart.defaults.borderColor = '#3b3b53';
    Chart.defaults.plugins.legend.labels.color = '#cdd6f4';
    Chart.defaults.scale = Chart.defaults.scale || {};
}

// Auto-dismiss Bootstrap alerts after 8 seconds
document.addEventListener('DOMContentLoaded', function () {
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 8000);
    });
});
