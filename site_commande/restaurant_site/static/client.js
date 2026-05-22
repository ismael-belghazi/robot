// =========================
// TABLE NUM & TOKEN
// =========================
const urlParams = new URLSearchParams(window.location.search);
const tableNum = parseInt(urlParams.get('table')) || parseInt(window.TABLE_NUMBER) || 1;
const tableToken = urlParams.get('token') || window.TABLE_TOKEN || '';

sessionStorage.setItem('table_number', tableNum);
sessionStorage.setItem('table_token', tableToken);

// =========================
// SOCKET.IO
// =========================
const socket = io();
let orderSubmitting = false;

socket.on('connect', () => {
    console.log('WebSocket connecté');
    socket.emit('join_table', { table: tableNum, token: tableToken });
});

socket.on('joined_table', () => {
    socket.emit('request_summary', { table: tableNum, token: tableToken });
});

socket.on('join_error', data => {
    showStatus(data.message || 'Erreur de connexion');
});

socket.on('disconnect', () => console.warn('WebSocket déconnecté'));

// Mise à jour du résumé global pour la table
socket.on('update_summary', data => {
    renderTableSummary(data);
    syncQuantities(data.summary);
});

// Mise à jour du nombre de clients connectés
socket.on('update_clients_count', count => {
    let clientsElem = document.getElementById('clients-count');
    if(!clientsElem){
        clientsElem = document.createElement('p');
        clientsElem.id = 'clients-count';
        document.querySelector('.container').prepend(clientsElem);
    }
    clientsElem.textContent = `Clients connectés : ${count}`;
});

// =========================
// MENU DATA GLOBAL
// =========================
let menuData = {};

// =========================
// APPLY THEME
// =========================
function applyTheme(tableNum) {
    const tableThemes = {
        1: { name: "Rubis", story: "Une flamme passionnée illumine votre repas", color: "#ffdddd", subcolor: "#ff9999", bg: "#6b0000", menu: "#a00000" },
        2: { name: "Emeraude", story: "La forêt et ses secrets vous entourent", color: "#ddffdd", subcolor: "#a0f0a0", bg: "#004d00", menu: "#007f00" },
        3: { name: "Soleil", story: "La chaleur et la lumière caressent vos plats", color: "#fff5dd", subcolor: "#ffdd99", bg: "#996600", menu: "#cc9900" },
        4: { name: "Saphir", story: "La profondeur de l'océan enveloppe votre table", color: "#ddeeff", subcolor: "#99ccff", bg: "#00194d", menu: "#0033a0" }
    };
    const theme = tableThemes[tableNum] || tableThemes[1];
    const root = document.documentElement.style;

    root.setProperty('--theme-color', theme.color);
    root.setProperty('--theme-subcolor', theme.subcolor);
    root.setProperty('--menu-bg', theme.menu);
    root.setProperty('--button-bg', theme.subcolor);
    root.setProperty('--button-text', theme.bg);
    root.setProperty('--button-border', theme.color);
    root.setProperty('--input-bg', theme.menu);
    root.setProperty('--input-text', theme.subcolor);

    const tableNameElem = document.getElementById('table-name');
    const tableStoryElem = document.getElementById('table-story');
    if(tableNameElem) tableNameElem.textContent = theme.name;
    if(tableStoryElem) tableStoryElem.textContent = theme.story;
    document.body.style.background = `linear-gradient(135deg, ${theme.bg}, ${theme.menu})`;
}

// =========================
// TAB NAVIGATION
// =========================
function setupTabNavigation() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            tabs.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.menu-section').forEach(sec => {
                sec.style.display = sec.dataset.category === btn.dataset.tab ? 'flex' : 'none';
            });
        });
    });

    const activeTab = document.querySelector('.tab-btn.active');
    const activeCategory = activeTab ? activeTab.dataset.tab : 'entrees';
    document.querySelectorAll('.menu-section').forEach(sec => {
        sec.style.display = sec.dataset.category === activeCategory ? 'flex' : 'none';
    });
}

// =========================
// LOAD MENU
// =========================
async function loadMenu() {
    try {
        const response = await fetch('/api/menu');
        menuData = await response.json();

        const menuDiv = document.getElementById('menu');
        menuDiv.innerHTML = '';

        ['entrees','plats','desserts','boissons'].forEach(cat => {
            const section = document.createElement('div');
            section.className = 'menu-section';
            section.dataset.category = cat;

            const title = document.createElement('h3');
            title.textContent = cat.charAt(0).toUpperCase() + cat.slice(1);
            section.appendChild(title);

            (menuData[cat] || []).forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'menu-item';
                itemDiv.innerHTML = `
                    <div class="item-info">
                        <img src="${item.image}" alt="${item.name}" class="item-img"
                             onerror="this.onerror=null;this.src='/static/images/placeholder.jpg';">
                        <span>${item.name} - ${item.price}€</span>
                    </div>
                    <div class="quantity-controls">
                        <button type="button" class="qty-btn" data-action="decrease">-</button>
                        <span class="qty">0</span>
                        <button type="button" class="qty-btn" data-action="increase">+</button>
                    </div>
                `;
                section.appendChild(itemDiv);
            });

            menuDiv.appendChild(section);
        });

        setupQuantityControls();
        setupTabNavigation();
        setupOrderForm();
    } catch(err) {
        console.error("Erreur loadMenu", err);
    }
}

// =========================
// QUANTITY CONTROLS
// =========================
function setupQuantityControls() {
    document.querySelectorAll('.qty-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            const itemDiv = e.target.closest('.menu-item');
            const qtySpan = itemDiv.querySelector('.qty');
            const name = itemDiv.querySelector('.item-info span').textContent.split(' - ')[0];
            let delta = 0;

            if(e.target.dataset.action === 'increase') delta = 1;
            if(e.target.dataset.action === 'decrease' && parseInt(qtySpan.textContent) > 0) delta = -1;

            if(delta === 0) return;

            qtySpan.textContent = parseInt(qtySpan.textContent) + delta;

            socket.emit('update_item', {
                table: tableNum,
                token: tableToken,
                item: name,
                quantityDelta: delta
            });
        });
    });
}

// =========================
// SYNCHRONISATION DES QUANTITÉS
// =========================
function syncQuantities(summary) {
    document.querySelectorAll('.menu-item').forEach(itemDiv => {
        const name = itemDiv.querySelector('.item-info span').textContent.split(' - ')[0];
        itemDiv.querySelector('.qty').textContent = summary[name] || 0;
    });
}

// =========================
// ORDER FORM
// =========================
function setupOrderForm() {
    const form = document.getElementById('order-form');
    if (!form) return;

    form.addEventListener('submit', e => {
        e.preventDefault();
        if (orderSubmitting) return;

        const order = {};
        document.querySelectorAll('.menu-item').forEach(itemDiv => {
            const qty = parseInt(itemDiv.querySelector('.qty').textContent);
            if (qty > 0) {
                const name = itemDiv.querySelector('.item-info span').textContent.split(' - ')[0];
                order[name] = qty;
            }
        });

        if (Object.keys(order).length === 0) {
            alert("Aucun plat sélectionné !");
            return;
        }

        orderSubmitting = true;
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) submitButton.disabled = true;

        socket.emit('send_order', { table: tableNum, token: tableToken, order });
        showStatus("Commande envoyée à la cuisine...");

        document.querySelectorAll('.qty-btn').forEach(btn => btn.disabled = true);
        document.querySelectorAll('.menu-item .qty').forEach(span => span.textContent = '0');
    });

    socket.on('order_delivered', data => {
        if (data.table === tableNum) {
            enableOrdering("Votre commande a été livrée ! Bon appétit !");
            alert("Votre commande est arrivée ! Bon appétit !");
        }
    });

    socket.on('order_completed', data => {
        if (data.table === tableNum && data.token === tableToken) {
            enableOrdering("Commande terminée. Vous pouvez recommander !");
            alert("Commande terminée. Vous pouvez recommander !");
        }
    });

    socket.on('order_ready', data => {
        if (data.table === tableNum) {
            showStatus("Votre commande est prête. Le robot est en route !");
        }
    });

    socket.on('order_submitted', data => {
        if (data.table === tableNum) {
            disableOrdering("Commande envoyée. En attente de validation.");
        }
    });

    socket.on('order_already_submitted', data => {
        if (data.table === tableNum) {
            disableOrdering("Commande déjà envoyée depuis cette table.");
        }
    });

    socket.on('order_cleared', data => {
        if (data.table === tableNum) {
            enableOrdering("Vous pouvez recommander à nouveau.");
        }
    });

    socket.on('session_ended', data => {
        if (data.table === tableNum) {
            disableOrdering("Session terminée.");
            alert("La table est fermée par le serveur.");
        }
    });
}

function disableOrdering(message) {
    document.querySelectorAll('.qty-btn').forEach(btn => btn.disabled = true);
    document.querySelectorAll('button[type="submit"]').forEach(btn => btn.disabled = true);
    const payButton = document.getElementById('pay-button');
    if (payButton) payButton.disabled = true;
    showStatus(message || "Session expirée.");
}

function enableOrdering(message) {
    orderSubmitting = false;
    document.querySelectorAll('.qty-btn').forEach(btn => btn.disabled = false);
    document.querySelectorAll('button[type="submit"]').forEach(btn => btn.disabled = false);
    const payButton = document.getElementById('pay-button');
    if (payButton) payButton.disabled = false;
    showStatus(message || "Vous pouvez commander.");
}

function showStatus(message) {
    const status = document.getElementById('status');
    if (status) status.textContent = message;
}

// =========================
// RENDER SERVER SUMMARY
// =========================
function renderTableSummary(data){
    const summaryList = document.getElementById('summary-list');
    if(!summaryList) return;
    summaryList.innerHTML = '';

    const { summary, total } = data;

    for(const [name, qty] of Object.entries(summary)){
        let price = 0;
        for(let cat of ['entrees','plats','desserts','boissons']){
            const item = menuData[cat]?.find(i => i.name === name);
            if(item){ price = item.price; break; }
        }
        summaryList.innerHTML += `<li>${name} x${qty} <span>${(price*qty).toFixed(2)}€</span></li>`;
    }

    const totalElem = document.getElementById('total');
    if(totalElem) totalElem.textContent = `Total : ${total.toFixed(2)}€`;
}

// =========================
// INITIALIZE
// =========================
document.addEventListener('DOMContentLoaded', () => {
    applyTheme(tableNum);
    loadMenu();
});