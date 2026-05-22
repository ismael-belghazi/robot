// =========================
// DASHBOARD TEMPS RÉEL (WEBSOCKET)
// =========================
const socket = io.connect(location.origin);

socket.on('connect', () => {
    console.log('Dashboard connecté au serveur WebSocket.');
    socket.emit('join_dashboard');
});

socket.on('join_error', data => {
    console.error('Erreur dashboard:', data.message);
});

// =========================
// TABLE THEMES (Couleurs contrastées pour la lisibilité)
// =========================
const tableThemes = {
    1: { bg: '#6b0000', menu: '#ffffff' }, // Fond bordeaux, texte blanc
    2: { bg: '#004d00', menu: '#ffffff' }, // Fond vert sapin, texte blanc
    3: { bg: '#996600', menu: '#ffffff' }, // Fond marron/or, texte blanc
    4: { bg: '#00194d', menu: '#ffffff' }  // Fond bleu nuit, texte blanc
};

// =========================
// RENDER ORDERS
// =========================
function renderOrders(orders) {
    const ordersBody = document.getElementById('orders-body');
    const summaryBody = document.getElementById('summary-body');
    if (!ordersBody || !summaryBody) return;

    ordersBody.innerHTML = '';
    summaryBody.innerHTML = '';

    const summary = {};

    orders.forEach(order => {
        if (!order || !order.table || !order.plats) return;

        // Nettoyage du statut (minuscules)
        let status = (order.status || 'en_attente').toLowerCase();
        if (status === 'prêt') status = 'pret'; 

        if (status === 'cancelled' || status === 'annule' || status === 'payee' || status === 'payé') return;

        if (status === 'en_attente' || status === 'preparation') {
            const theme = tableThemes[order.table] || { bg: '#ffffff', menu: '#000000' };
            const tr = document.createElement('tr');
            tr.classList.add('order-row');
            tr.style.backgroundColor = theme.bg;
            tr.style.color = theme.menu;

            const platsCount = {};
            order.plats.forEach(p => platsCount[p] = (platsCount[p] || 0) + 1);
            const platsDisplay = Object.entries(platsCount)
                .map(([plat, qty]) => `${qty}x ${plat}`).join(', ');

            const statusColors = { 
                'en_attente': '#ffcc00', 
                'preparation': '#ffaa00'
            };
            const statusColor = statusColors[status] || theme.menu;

            tr.innerHTML = `
                <td>${order.table}</td>
                <td>${platsDisplay}</td>
                <td style="color:${statusColor}; font-weight:bold;">${status.toUpperCase()}</td>
                <td>
                    <button class="confirm-btn" data-table="${order.table}">Confirmer</button>
                    <button class="cancel-btn" data-table="${order.table}">Annuler</button>
                </td>
            `;
            ordersBody.appendChild(tr);
        }

        if (!summary[order.table]) {
            summary[order.table] = { plats: [], total: 0, ready: true };
        }
        
        summary[order.table].plats.push(...order.plats);
        summary[order.table].total += float(order.total_price) || 0; 

        if (status === 'en_attente' || status === 'preparation') {
            summary[order.table].ready = false;
        }
    });

    Object.keys(summary).forEach(table => {
        const theme = tableThemes[table] || { bg: '#ffffff', menu: '#000000' };
        const tr = document.createElement('tr');
        tr.classList.add('summary-row');
        tr.style.backgroundColor = theme.bg;
        tr.style.color = theme.menu;

        const platsCount = {};
        summary[table].plats.forEach(p => platsCount[p] = (platsCount[p] || 0) + 1);
        const platsDisplay = Object.entries(platsCount)
            .map(([plat, qty]) => `${qty}x ${plat}`).join(', ');

        tr.innerHTML = `
            <td>${table}</td>
            <td>${platsDisplay}</td>
            <td>${summary[table].total.toFixed(2)} €</td>
            <td>
                <button class="pay-btn" data-table="${table}" ${!summary[table].ready ? 'disabled' : ''}>Payer</button>
            </td>
        `;
        summaryBody.appendChild(tr);
    });

    bindButtonEvents();
}

function float(val) {
    const parsed = parseFloat(val);
    return isNaN(parsed) ? 0 : parsed;
}
// =========================
// BIND BUTTON EVENTS
// =========================
function bindButtonEvents() {
    document.querySelectorAll('.confirm-btn').forEach(btn => {
        btn.onclick = () => {
            btn.disabled = true;
            socket.emit('confirm_order', { table: parseInt(btn.dataset.table) });
        };
    });

    document.querySelectorAll('.cancel-btn').forEach(btn => {
        btn.onclick = () => {
            btn.disabled = true;
            socket.emit('cancel_order', { table: parseInt(btn.dataset.table) });
        };
    });

    document.querySelectorAll('.pay-btn').forEach(btn => {
        btn.onclick = () => {
            btn.disabled = true;
            socket.emit('pay_order', { table: parseInt(btn.dataset.table) });
        };
    });
}

// =========================
// SOCKET EVENTS
// =========================
socket.on('update_orders', data => {
    renderOrders(data);
});

socket.on('disconnect', () => {
    console.warn('Déconnecté du serveur WebSocket. Tentative de reconnexion...');
});

// =========================
// INITIALIZE DASHBOARD
// =========================
document.addEventListener('DOMContentLoaded', () => {
    console.log("Dashboard prêt, WebSocket actif !");
});