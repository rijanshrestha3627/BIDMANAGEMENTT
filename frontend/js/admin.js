/**
 * Admin Dashboard — admin.js  (Phase 3)
 *
 * Responsibilities:
 *  - Tab navigation
 *  - Dashboard stats & charts from real API
 *  - Activity feed & recent auctions
 *  - Top bidders table
 *  - Auction management (create / edit / delete — reuses existing admin endpoints)
 *  - User management (list, search, paginate, detail view)
 *  - Analytics tab (auction performance + bid stats)
 *
 * All write operations use api.js which sends credentials:include.
 */

'use strict';

// ─── Global state ──────────────────────────────────────────────────────────
let allAuctions = [];
let currentAuctionFilter = 'ALL';
let currentUserPage = 1;
let currentUserSearch = '';
let walletTransactions = [];
let walletSearchTerm = '';
let walletTypeFilter = 'ALL';
let walletStatusFilter = 'ALL';

// ─── DOMContentLoaded ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Guard: only admins may see this page
    const me = await api.getMe();
    if (!me.authenticated || me.user.role !== 'ADMIN') {
        document.querySelector('main').innerHTML = `
            <div class="container" style="padding:4rem 1.5rem; text-align:center;">
                <h1 style="font-size:1.5rem; margin-bottom:1rem;">Access Denied</h1>
                <p style="color:var(--color-text-2); margin-bottom:1.5rem;">
                    You must be logged in as an admin to view this page.
                </p>
                <a href="admin-login.html" class="btn btn-primary">Admin Login</a>
            </div>`;
        return;
    }

    // Update nav to show logged-in admin
    updateAuthNav(me.user);

    // ── Tab setup ────────────────────────────────────────────────────────────
    document.querySelectorAll('.admin-tab').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // ── Create auction form ──────────────────────────────────────────────────
    const createForm = document.getElementById('create-auction-form');
    createForm.addEventListener('submit', handleCreateAuction);

    // Image preview
    const imageInput = document.getElementById('item-image');
    const previewContainer = document.getElementById('image-preview-container');
    const previewImg = document.getElementById('image-preview');
    const removeBtn = document.getElementById('remove-image-btn');

    if (imageInput) {
        imageInput.addEventListener('change', function () {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = e => {
                    previewImg.src = e.target.result;
                    previewContainer.style.display = 'block';
                };
                reader.readAsDataURL(file);
            } else {
                previewContainer.style.display = 'none';
            }
        });
    }

    if (removeBtn) {
        removeBtn.addEventListener('click', () => {
            imageInput.value = '';
            previewContainer.style.display = 'none';
        });
    }

    // ── Edit modal ───────────────────────────────────────────────────────────
    const editForm = document.getElementById('edit-auction-form');
    editForm.addEventListener('submit', handleEditAuction);
    document.getElementById('close-modal-btn').addEventListener('click', closeEditModal);

    // Close modal on overlay click
    document.getElementById('edit-modal').addEventListener('click', e => {
        if (e.target === document.getElementById('edit-modal')) closeEditModal();
    });

    // ── User detail modal ────────────────────────────────────────────────────
    document.getElementById('close-user-modal-btn').addEventListener('click', closeUserModal);
    document.getElementById('user-detail-modal').addEventListener('click', e => {
        if (e.target === document.getElementById('user-detail-modal')) closeUserModal();
    });

    // ── Auction filter tabs ──────────────────────────────────────────────────
    document.querySelectorAll('#auction-filter-tabs .filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('#auction-filter-tabs .filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentAuctionFilter = tab.dataset.status;
            renderAuctionList();
        });
    });

    // ── User search ──────────────────────────────────────────────────────────
    document.getElementById('user-search-btn').addEventListener('click', () => {
        currentUserSearch = document.getElementById('user-search').value.trim();
        currentUserPage = 1;
        loadUsers();
    });
    document.getElementById('user-search').addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            currentUserSearch = document.getElementById('user-search').value.trim();
            currentUserPage = 1;
            loadUsers();
        }
    });

    // ── Wallet tab controls ─────────────────────────────────────────────────
    document.getElementById('wallet-search-btn').addEventListener('click', applyWalletFilters);
    document.getElementById('wallet-clear-btn').addEventListener('click', clearWalletFilters);
    document.getElementById('wallet-refresh-btn').addEventListener('click', loadWalletTab);
    document.getElementById('wallet-search').addEventListener('keydown', e => {
        if (e.key === 'Enter') applyWalletFilters();
    });
    document.getElementById('wallet-type-filter').addEventListener('change', applyWalletFilters);
    document.getElementById('wallet-status-filter').addEventListener('change', applyWalletFilters);
    document.getElementById('wallet-credit-btn').addEventListener('click', () => openWalletAdjustModal('CREDIT'));
    document.getElementById('wallet-debit-btn').addEventListener('click', () => openWalletAdjustModal('DEBIT'));
    document.getElementById('wallet-adjust-close').addEventListener('click', closeWalletAdjustModal);
    document.getElementById('wallet-adjust-cancel').addEventListener('click', closeWalletAdjustModal);
    document.getElementById('wallet-adjust-modal').addEventListener('click', event => {
        if (event.target.id === 'wallet-adjust-modal') closeWalletAdjustModal();
    });
    document.getElementById('wallet-user-search-btn').addEventListener('click', searchWalletUsers);
    document.getElementById('wallet-user-search').addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchWalletUsers();
        }
    });
    document.getElementById('wallet-adjust-form').addEventListener('submit', submitWalletAdjustment);

    // ── Initial data load ────────────────────────────────────────────────────
    await loadDashboard();
    loadAdminAuctionList();
    loadUsers();
    loadAnalyticsTab();
    loadWalletTab();
});

// ─── Auth nav helper ───────────────────────────────────────────────────────
function updateAuthNav(user) {
    const actionsDiv = document.getElementById('auth-actions');
    if (!actionsDiv) return;
    actionsDiv.innerHTML = `
        <span style="font-size:0.8125rem; color:var(--color-text-2); font-weight:500;">${user.username}</span>
        <button class="btn btn-secondary btn-sm" id="logout-btn">Logout</button>
    `;
    document.getElementById('logout-btn').addEventListener('click', async () => {
        await api.logout();
        window.location.href = 'admin-login.html';
    });
}

// ─── Tab Switching ─────────────────────────────────────────────────────────
function switchTab(tabId) {
    document.querySelectorAll('.admin-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
        btn.setAttribute('aria-selected', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(sec => {
        sec.classList.toggle('active', sec.id === `tab-content-${tabId}`);
    });

    if (tabId === 'wallet') {
        loadWalletTab();
    }
}

async function loadWalletTab() {
    const tbody = document.getElementById('wallet-transactions-tbody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="table-empty">Loading wallet transactions...</td></tr>';

    const [overviewRes, txRes] = await Promise.all([
        api.getAdminWalletOverview(),
        api.getAdminWalletTransactions(1, {})
    ]);

    walletTransactions = txRes && txRes.success && Array.isArray(txRes.transactions) ? txRes.transactions : [];
    const summaryNode = document.getElementById('admin-wallet-summary');
    if (summaryNode) {
        if (overviewRes && overviewRes.success && overviewRes.stats) {
            const stats = {
                total_balance: Number(overviewRes.stats.total_balance || 0),
                total_deposited: Number(overviewRes.stats.total_deposited || 0),
                total_withdrawals: Number(overviewRes.stats.total_withdrawn || 0),
                pending_transactions_count: Number(overviewRes.stats.pending_transactions_count || 0)
            };
            renderWalletSummary(stats, walletTransactions);
        } else {
            summaryNode.querySelectorAll('.stat-value').forEach(value => { value.textContent = 'Unavailable'; });
        }
    }

    if (!txRes || !txRes.success) {
        tbody.innerHTML = `<tr><td colspan="7" class="table-empty">${escHtml(txRes?.error || 'Unable to load wallet transactions.')}</td></tr>`;
    } else {
        applyWalletFilters();
    }
    updateWalletPendingBadge();
}

function updateWalletPendingBadge() {
    const badge = document.getElementById('wallet-pending-badge');
    if (!badge) return;
    const pendingCount = walletTransactions.filter(tx => String(tx.status || '').toUpperCase() === 'PENDING').length;
    badge.textContent = pendingCount;
    badge.style.display = pendingCount > 0 ? 'inline-flex' : 'none';
}

function renderWalletSummary(stats, transactions) {
    const summaryNode = document.getElementById('admin-wallet-summary');
    if (!summaryNode) return;

    const summaryCards = [
        { label: 'Total Wallet Balance', value: formatCurrency(Number(stats.total_balance || 0)), sub: 'Across all active users' },
        { label: 'Total Deposits', value: formatCurrency(Number(stats.total_deposited || 0)), sub: 'Completed deposits' },
        { label: 'Total Withdrawals', value: formatCurrency(Number(stats.total_withdrawals || 0)), sub: 'Withdrawal payouts' },
        { label: 'Pending Transactions', value: String(Number(stats.pending_transactions_count ?? (transactions || []).filter(tx => String(tx.status || '').toUpperCase() === 'PENDING').length)), sub: 'Awaiting review' }
    ];

    summaryNode.innerHTML = summaryCards.map((card, idx) => `
        <div class="stat-card ${idx === 0 ? 'stat-card--primary' : ''}">
            <span class="stat-label">${card.label}</span>
            <span class="stat-value">${card.value}</span>
            <span class="stat-sub">${card.sub}</span>
        </div>
    `).join('');
}

function applyWalletFilters() {
    const search = (document.getElementById('wallet-search')?.value || '').trim().toLowerCase();
    const type = (document.getElementById('wallet-type-filter')?.value || 'ALL').toUpperCase();
    const status = (document.getElementById('wallet-status-filter')?.value || 'ALL').toUpperCase();

    const filtered = walletTransactions.filter(tx => {
        const text = `${tx.username || ''} ${tx.id || ''}`.toLowerCase();
        const matchesSearch = !search || text.includes(search);
        const matchesType = type === 'ALL' || String(tx.type || '').toUpperCase() === type;
        const matchesStatus = status === 'ALL' || String(tx.status || '').toUpperCase() === status;
        return matchesSearch && matchesType && matchesStatus;
    });

    renderWalletTable(filtered);
}

function clearWalletFilters() {
    const search = document.getElementById('wallet-search');
    const type = document.getElementById('wallet-type-filter');
    const status = document.getElementById('wallet-status-filter');
    if (search) search.value = '';
    if (type) type.value = 'ALL';
    if (status) status.value = 'ALL';
    walletSearchTerm = '';
    walletTypeFilter = 'ALL';
    walletStatusFilter = 'ALL';
    renderWalletTable(walletTransactions);
}

function renderWalletTable(rows) {
    const tbody = document.getElementById('wallet-transactions-tbody');
    if (!tbody) return;

    if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty">No matching wallet transactions found.</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map(tx => {
        const status = String(tx.status || 'PENDING').toUpperCase();
        const type = String(tx.type || 'DEPOSIT').replace(/_/g, ' ');
        const statusClass = status === 'COMPLETED' ? 'badge-success' : status === 'PENDING' ? 'badge-warning' : 'badge-danger';
        const safeType = type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
        const amount = formatCurrency(Number(tx.amount || 0));
        const createdDate = tx.created_at ? new Date(tx.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
        const actionButtons = `<button class="btn btn-secondary btn-sm" data-action="view" data-id="${tx.id}">View</button>`;

        return `
            <tr>
                <td>#${Number(tx.id || 0)}</td>
                <td>${escHtml(tx.username || 'Unknown')}</td>
                <td>${escHtml(safeType)}</td>
                <td>${amount}</td>
                <td>${createdDate}</td>
                <td><span class="badge ${statusClass}">${status}</span></td>
                <td>${actionButtons}</td>
            </tr>
        `;
    }).join('');

    tbody.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', () => handleWalletAction(btn.dataset.action, Number(btn.dataset.id)));
    });
}

function handleWalletAction(action, id) {
    const tx = walletTransactions.find(item => Number(item.id) === Number(id));
    if (!tx) return;

    if (action === 'view') {
        const details = [
            `Transaction ID: #${tx.id}`,
            `Username: ${tx.username || 'Unknown'}`,
            `Type: ${String(tx.type || 'DEPOSIT').replace(/_/g, ' ')}`,
            `Amount: ${formatCurrency(Number(tx.amount || 0))}`,
            `Status: ${tx.status || 'PENDING'}`,
            `Date: ${tx.created_at ? new Date(tx.created_at).toLocaleString('en-IN') : 'N/A'}`
        ].join('\n');
        window.alert(details);
        return;
    }

}

function openWalletAdjustModal(direction) {
    const modal = document.getElementById('wallet-adjust-modal');
    const directionSelect = document.getElementById('wallet-adjust-direction');
    const title = document.getElementById('wallet-adjust-title');
    const submit = document.getElementById('wallet-adjust-submit');
    const userSelect = document.getElementById('wallet-user-select');

    directionSelect.value = direction;
    title.textContent = direction === 'CREDIT' ? 'Add Money to User Wallet' : 'Withdraw Money from User Wallet';
    submit.textContent = direction === 'CREDIT' ? 'Confirm credit' : 'Confirm withdrawal';
    userSelect.innerHTML = '<option value="">Search for a user first</option>';
    userSelect.disabled = true;
    document.getElementById('wallet-adjust-message').textContent = '';
    document.getElementById('wallet-adjust-message').className = 'wallet-adjust-message';
    modal.style.display = 'flex';
    document.getElementById('wallet-user-search').focus();
}

function closeWalletAdjustModal() {
    document.getElementById('wallet-adjust-modal').style.display = 'none';
    document.getElementById('wallet-adjust-form').reset();
    const userSelect = document.getElementById('wallet-user-select');
    userSelect.innerHTML = '<option value="">Search for a user first</option>';
    userSelect.disabled = true;
}

async function searchWalletUsers() {
    const searchInput = document.getElementById('wallet-user-search');
    const userSelect = document.getElementById('wallet-user-select');
    const message = document.getElementById('wallet-adjust-message');
    const search = searchInput.value.trim();
    if (!search) {
        message.textContent = 'Enter a username or email to find the account.';
        message.className = 'wallet-adjust-message is-error';
        return;
    }

    const searchButton = document.getElementById('wallet-user-search-btn');
    searchButton.disabled = true;
    searchButton.textContent = 'Searching...';
    message.textContent = '';
    userSelect.disabled = true;
    try {
        const result = await api.getAdminWalletUsers(search);
        if (!result || !result.success || !Array.isArray(result.users)) {
            message.textContent = result?.error || 'Could not search user wallets.';
            message.className = 'wallet-adjust-message is-error';
            return;
        }

        userSelect.innerHTML = '<option value="">Select a user account</option>';
        result.users.forEach(user => {
            const option = document.createElement('option');
            option.value = String(user.id);
            option.textContent = `${user.username} (${user.email}) — Available ${formatCurrency(Number(user.available || 0))}`;
            userSelect.appendChild(option);
        });
        userSelect.disabled = result.users.length === 0;
        if (result.users.length === 0) {
            message.textContent = 'No wallet accounts found for that search.';
            message.className = 'wallet-adjust-message is-error';
        }
    } finally {
        searchButton.disabled = false;
        searchButton.textContent = 'Search';
    }
}

async function submitWalletAdjustment(event) {
    event.preventDefault();
    const userId = Number(document.getElementById('wallet-user-select').value);
    const direction = document.getElementById('wallet-adjust-direction').value;
    const amount = Number(document.getElementById('wallet-adjust-amount').value);
    const reason = document.getElementById('wallet-adjust-reason').value.trim();
    const message = document.getElementById('wallet-adjust-message');
    const submit = document.getElementById('wallet-adjust-submit');

    if (!userId || !Number.isFinite(amount) || amount <= 0 || !reason) {
        message.textContent = 'Select a user, enter a valid amount, and provide a reason.';
        message.className = 'wallet-adjust-message is-error';
        return;
    }

    const action = direction === 'CREDIT' ? 'add' : 'withdraw';
    if (!window.confirm(`Confirm ${action} of ${formatCurrency(amount)}? This action will be recorded in the audit log.`)) return;

    submit.disabled = true;
    message.textContent = 'Processing wallet adjustment...';
    message.className = 'wallet-adjust-message';
    try {
        const result = await api.adminAdjustBalance(userId, amount, direction, reason);
        if (!result || !result.success) {
            message.textContent = result?.error || 'Wallet adjustment failed.';
            message.className = 'wallet-adjust-message is-error';
            return;
        }
        message.textContent = result.message || 'Wallet adjustment completed.';
        message.className = 'wallet-adjust-message is-success';
        await loadWalletTab();
    } finally {
        submit.disabled = false;
    }
}

function escHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[ch]));
}

// ─── Dashboard Load ────────────────────────────────────────────────────────
async function loadDashboard() {
    const [analytics, bidsOverTime, topBidders, recentActivity, recentAuctions] = await Promise.all([
        api.getAnalytics(),
        api.getBidsOverTime(),
        api.getTopBidders(),
        api.getRecentActivity(),
        api.getRecentAuctions()
    ]);

    if (!analytics.error) {
        renderStats(analytics);
    }

    renderBidChart(bidsOverTime);
    renderTopBidders(topBidders);
    renderRecentActivity(recentActivity);
    renderRecentAuctions(recentAuctions);

    // Render status chart from analytics data
    if (!analytics.error) {
        renderStatusChart(analytics.auctions);
    }
}

// ─── Render Stats ──────────────────────────────────────────────────────────
function renderStats(data) {
    const { users, auctions, bids } = data;

    setText('stat-total-users', users.total);
    if (users.new_last_7_days > 0) {
        setText('stat-new-users', `+${users.new_last_7_days} this week`);
    }

    setText('stat-total-auctions', auctions.total);
    setText('stat-total-bids', bids.total.toLocaleString());
    setText('stat-active', auctions.active);
    setText('stat-upcoming', auctions.upcoming);
    setText('stat-ended', auctions.ended);
    setText('stat-total-value', formatCurrency(bids.total_value));
    setText('stat-highest', formatCurrency(bids.highest));
    setText('stat-average', formatCurrency(bids.average));

    // Also update analytics tab bid stats
    setText('a-total-bids', bids.total.toLocaleString());
    setText('a-total-value', formatCurrency(bids.total_value));
    setText('a-highest', formatCurrency(bids.highest));
    setText('a-average', formatCurrency(bids.average));
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

// ─── Bid Activity Chart (fixed-pixel SVG, no label overlap) ────────────────
function renderBidChart(data) {
    const container = document.getElementById('bid-chart-container');
    if (!data || data.length === 0 || data.error) {
        container.innerHTML = '<p class="chart-loading">No bid data available yet.</p>';
        return;
    }

    const maxCount = Math.max(...data.map(d => d.count), 1);
    const n = data.length; // 14 days

    // Fixed-pixel coordinate system inside viewBox
    const vW = 540, vH = 200;
    const padL = 28, padR = 12, padTop = 20, padBot = 36;
    const chartW = vW - padL - padR;
    const chartH = vH - padTop - padBot;
    const slotW = chartW / n;
    const barW = Math.max(slotW * 0.55, 6);

    let barsHtml = '', valuesHtml = '', labelsHtml = '';

    data.forEach((d, i) => {
        const cx = padL + i * slotW + slotW / 2;
        const x = cx - barW / 2;
        const barH = d.count > 0 ? Math.max((d.count / maxCount) * chartH, 3) : 0;
        const y = padTop + chartH - barH;

        barsHtml += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barH.toFixed(1)}"
            rx="2" fill="var(--color-text)" opacity="${d.count > 0 ? '0.82' : '0.1'}">
            <title>${d.label}: ${d.count} bid${d.count !== 1 ? 's' : ''}</title>
        </rect>`;

        if (d.count > 0) {
            valuesHtml += `<text x="${cx.toFixed(1)}" y="${(y - 4).toFixed(1)}"
                text-anchor="middle" font-size="8" fill="var(--color-text-2)"
                font-family="Inter,system-ui,sans-serif">${d.count}</text>`;
        }

        // Show every other label to guarantee no overlap on 14-day range
        // Always show index 0, last index, and even indices
        const showLabel = n <= 8 || i === 0 || i === n - 1 || i % 2 === 0;
        if (showLabel) {
            labelsHtml += `<text x="${cx.toFixed(1)}" y="${(padTop + chartH + 22).toFixed(1)}"
                text-anchor="middle" font-size="8.5" fill="var(--color-text-3)"
                font-family="Inter,system-ui,sans-serif">${d.label}</text>`;
        }
    });

    container.innerHTML = `
        <svg class="admin-bar-chart-svg" viewBox="0 0 ${vW} ${vH}"
             role="img" aria-label="Admin bid activity bar chart">
            <!-- axis line -->
            <line x1="${padL}" y1="${padTop + chartH}" x2="${vW - padR}" y2="${padTop + chartH}"
                  stroke="var(--color-border)" stroke-width="1"/>
            ${barsHtml}
            ${valuesHtml}
            ${labelsHtml}
        </svg>`;
}

// ─── Auction Status Chart ──────────────────────────────────────────────────
function renderStatusChart(auctionData) {
    const container = document.getElementById('auction-status-chart');
    if (!auctionData) {
        container.innerHTML = '<p class="chart-loading">No data.</p>';
        return;
    }

    const { active, upcoming, ended, total } = auctionData;
    const denom = total || 1;

    const rows = [
        { label: 'Active', count: active, cls: 'active', pct: Math.round((active / denom) * 100) },
        { label: 'Upcoming', count: upcoming, cls: 'upcoming', pct: Math.round((upcoming / denom) * 100) },
        { label: 'Ended', count: ended, cls: 'ended', pct: Math.round((ended / denom) * 100) }
    ];

    container.innerHTML = rows.map(r => `
        <div class="status-bar-row">
            <span class="status-bar-label">${r.label}</span>
            <div class="status-bar-track">
                <div class="status-bar-fill status-bar-fill--${r.cls}" style="width:${r.pct}%"></div>
            </div>
            <span class="status-bar-count">${r.count}</span>
        </div>
    `).join('');
}

// ─── Top Bidders ───────────────────────────────────────────────────────────
function renderTopBidders(data) {
    const tbody = document.getElementById('top-bidders-tbody');
    if (!data || data.length === 0 || data.error) {
        tbody.innerHTML = '<tr><td colspan="5" class="table-empty">No bidding activity yet.</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(row => {
        const rankCls = row.rank === 1 ? 'rank-badge--gold' : row.rank === 2 ? 'rank-badge--silver' : row.rank === 3 ? 'rank-badge--bronze' : '';
        return `<tr>
            <td><span class="rank-badge ${rankCls}">${row.rank}</span></td>
            <td style="font-weight:600; color:var(--color-text);">${escHtml(row.username)}</td>
            <td>${row.total_bids.toLocaleString()}</td>
            <td>${formatCurrency(row.highest_bid)}</td>
            <td>${formatCurrency(row.total_amount)}</td>
        </tr>`;
    }).join('');
}

// ─── Recent Activity ───────────────────────────────────────────────────────
function renderRecentActivity(events) {
    const list = document.getElementById('recent-activity-list');
    if (!events || events.length === 0 || events.error) {
        list.innerHTML = '<p class="text-muted" style="font-size:0.875rem;">No recent activity.</p>';
        return;
    }

    const iconMap = {
        person: '👤',
        gavel: '🔨',
        add_circle: '📋'
    };

    list.innerHTML = events.map(ev => `
        <div class="activity-item">
            <div class="activity-icon">${iconMap[ev.icon] || '●'}</div>
            <div class="activity-text">
                <div class="activity-msg">${escHtml(ev.message)}</div>
                <div class="activity-time">${formatDateTime(ev.time)}</div>
            </div>
        </div>
    `).join('');
}

// ─── Recent Auctions ───────────────────────────────────────────────────────
function renderRecentAuctions(auctions) {
    const container = document.getElementById('recent-auctions-list');
    if (!auctions || auctions.length === 0 || auctions.error) {
        container.innerHTML = '<p class="text-muted" style="font-size:0.875rem;">No auctions yet.</p>';
        return;
    }

    container.innerHTML = auctions.map(a => {
        const imgUrl = a.image_path ? `http://localhost:5000/${a.image_path}` : 'assets/placeholder-item.jpg';
        const bid = a.current_highest_bid > 0 ? formatCurrency(a.current_highest_bid) : formatCurrency(a.starting_price);
        return `
            <a href="auction.html?id=${a.id}" class="recent-auction-row" target="_blank" rel="noopener">
                <img class="recent-auction-img" src="${imgUrl}" alt="${escHtml(a.title)}">
                <div class="recent-auction-info">
                    <div class="recent-auction-title">${escHtml(a.title)}</div>
                    <div class="recent-auction-meta">
                        <span class="badge ${statusBadgeClass(a.status)}">${a.status}</span>
                        <span>${bid}</span>
                        <span>${a.bid_count} bid${a.bid_count !== 1 ? 's' : ''}</span>
                    </div>
                </div>
            </a>`;
    }).join('');
}

// ─── Auction Management ────────────────────────────────────────────────────
async function loadAdminAuctionList() {
    const container = document.getElementById('admin-auction-list');
    container.innerHTML = '<p class="text-muted" style="font-size:0.875rem;">Loading auctions…</p>';
    const auctions = await api.getAuctions();
    allAuctions = Array.isArray(auctions) ? auctions : [];
    renderAuctionList();
}

function renderAuctionList() {
    const container = document.getElementById('admin-auction-list');
    const filtered = currentAuctionFilter === 'ALL'
        ? allAuctions
        : allAuctions.filter(a => a.status === currentAuctionFilter);

    if (filtered.length === 0) {
        container.innerHTML = '<p class="text-muted" style="font-size:0.875rem;">No auctions found.</p>';
        return;
    }

    container.innerHTML = filtered.map(auction => {
        const imgUrl = auction.image_path ? `http://localhost:5000/${auction.image_path}` : 'assets/placeholder-item.jpg';
        return `
            <div class="admin-auction-row">
                <img src="${imgUrl}" alt="Product" style="width:60px; height:60px; object-fit:cover; border-radius:var(--r-sm);">
                <div class="admin-auction-info">
                    <span class="admin-auction-title">${escHtml(auction.title)}</span>
                    <div class="admin-auction-details">
                        <span class="badge ${statusBadgeClass(auction.status)}">${auction.status}</span>
                        <span>Starting: ${formatCurrency(auction.starting_price)}</span>
                        <span>Current: ${auction.current_highest_bid > 0 ? formatCurrency(auction.current_highest_bid) : 'No bids'}</span>
                        <span>${auction.bid_count != null ? auction.bid_count + ' bid' + (auction.bid_count !== 1 ? 's' : '') : ''}</span>
                        <span>${formatDateTime(auction.start_time)} → ${formatDateTime(auction.end_time)}</span>
                    </div>
                </div>
                <div class="admin-auction-actions">
                    <button class="btn btn-secondary btn-sm" onclick="openEditModal(${auction.id})">Edit</button>
                    ${auction.status === 'UPCOMING' ? `<button class="btn btn-primary btn-sm" onclick="forceStart(${auction.id})">Start</button>` : ''}
                    ${auction.status === 'ACTIVE' ? `<button class="btn btn-danger btn-sm" onclick="forceEnd(${auction.id})">End</button>` : ''}
                    ${auction.status === 'ENDED' ? `<button class="btn btn-danger btn-sm" onclick="deleteAuction(${auction.id})">Delete</button>` : ''}
                    <a href="auction.html?id=${auction.id}" class="btn btn-secondary btn-sm" target="_blank">View</a>
                </div>
            </div>`;
    }).join('');
}

// ── Create Auction ──────────────────────────────────────────────────────────
async function handleCreateAuction(e) {
    e.preventDefault();
    const msgDiv = document.getElementById('form-message');
    const submitBtn = document.getElementById('submit-btn');

    const title = document.getElementById('item-title').value.trim();
    const description = document.getElementById('item-desc').value.trim();
    const startingPrice = parseFloat(document.getElementById('starting-price').value);
    const minimumIncrement = parseFloat(document.getElementById('min-increment').value);
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;
    const imageInput = document.getElementById('item-image');

    if (!title || !description) { showMsg(msgDiv, 'Please fill in all fields.', 'error'); return; }
    if (isNaN(startingPrice) || startingPrice <= 0) { showMsg(msgDiv, 'Starting price must be a positive number.', 'error'); return; }
    if (isNaN(minimumIncrement) || minimumIncrement <= 0) { showMsg(msgDiv, 'Minimum increment must be a positive number.', 'error'); return; }
    if (!startTime || !endTime) { showMsg(msgDiv, 'Please set both start and end times.', 'error'); return; }
    if (new Date(endTime) <= new Date(startTime)) { showMsg(msgDiv, 'End time must be after start time.', 'error'); return; }

    const formData = new FormData();
    formData.append('title', title);
    formData.append('description', description);
    formData.append('starting_price', startingPrice);
    formData.append('minimum_increment', minimumIncrement);
    formData.append('start_time', startTime);
    formData.append('end_time', endTime);

    if (imageInput && imageInput.files.length > 0) {
        const file = imageInput.files[0];
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
            showMsg(msgDiv, 'Invalid image type. Only JPG, PNG, WEBP allowed.', 'error'); return;
        }
        if (file.size > 5 * 1024 * 1024) { showMsg(msgDiv, 'Image too large. Max 5MB.', 'error'); return; }
        formData.append('image', file);
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating…';

    const result = await api.createAuction(formData);

    if (result.id) {
        showMsg(msgDiv, `Auction "${title}" created successfully! (ID: ${result.id})`, 'success');
        document.getElementById('create-auction-form').reset();
        const pc = document.getElementById('image-preview-container');
        if (pc) pc.style.display = 'none';
        await loadAdminAuctionList();
        // Refresh dashboard stats
        loadDashboard();
    } else {
        showMsg(msgDiv, result.error || 'Failed to create auction.', 'error');
    }

    submitBtn.disabled = false;
    submitBtn.textContent = 'Create Auction';
}

// ── Edit Modal ──────────────────────────────────────────────────────────────
function openEditModal(id) {
    const auction = allAuctions.find(a => a.id === id);
    if (!auction) return;

    document.getElementById('edit-id').value = auction.id;
    document.getElementById('edit-title').value = auction.title;
    document.getElementById('edit-desc').value = auction.description;
    document.getElementById('edit-starting-price').value = auction.starting_price;
    document.getElementById('edit-min-increment').value = auction.minimum_increment;
    document.getElementById('edit-start-time').value = auction.start_time;
    document.getElementById('edit-end-time').value = auction.end_time;
    document.getElementById('edit-image').value = '';

    const currentImg = document.getElementById('edit-current-image');
    if (auction.image_path) {
        currentImg.src = `http://localhost:5000/${auction.image_path}`;
        currentImg.style.display = 'block';
    } else {
        currentImg.style.display = 'none';
    }

    document.getElementById('edit-form-message').innerHTML = '';

    const priceInput = document.getElementById('edit-starting-price');
    if (auction.current_highest_bid > 0) {
        priceInput.disabled = true;
        priceInput.title = 'Cannot change starting price after bids have been placed';
    } else {
        priceInput.disabled = false;
        priceInput.title = '';
    }

    document.getElementById('edit-modal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

async function handleEditAuction(e) {
    e.preventDefault();
    const msgDiv = document.getElementById('edit-form-message');
    const submitBtn = document.getElementById('edit-submit-btn');
    const id = document.getElementById('edit-id').value;

    const formData = new FormData();
    formData.append('title', document.getElementById('edit-title').value.trim());
    formData.append('description', document.getElementById('edit-desc').value.trim());
    formData.append('starting_price', parseFloat(document.getElementById('edit-starting-price').value));
    formData.append('minimum_increment', parseFloat(document.getElementById('edit-min-increment').value));
    formData.append('start_time', document.getElementById('edit-start-time').value);
    formData.append('end_time', document.getElementById('edit-end-time').value);

    const imageInput = document.getElementById('edit-image');
    if (imageInput && imageInput.files.length > 0) {
        formData.append('image', imageInput.files[0]);
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving…';

    const result = await api.editAuction(id, formData);

    if (result.message) {
        showMsg(msgDiv, 'Auction updated successfully!', 'success');
        setTimeout(() => { closeEditModal(); loadAdminAuctionList(); }, 1000);
    } else {
        showMsg(msgDiv, result.error || 'Failed to update auction.', 'error');
    }

    submitBtn.disabled = false;
    submitBtn.textContent = 'Save Changes';
}

async function deleteAuction(id) {
    if (!confirm('Delete this ended auction and its bid history?\n\nThis cannot be undone.')) return;
    const result = await api.deleteAuction(id);
    if (result.success) {
        alert('Auction deleted successfully.');
        loadAdminAuctionList();
        loadDashboard();
    } else {
        alert(result.message || result.error || 'Failed to delete auction.');
    }
}

async function forceStart(id) {
    if (!confirm('Start this auction now?')) return;
    await api.startAuction(id);
    await loadAdminAuctionList();
    loadDashboard();
}

async function forceEnd(id) {
    if (!confirm('End this auction now? This cannot be undone.')) return;
    await api.endAuction(id);
    await loadAdminAuctionList();
    loadDashboard();
}

// ─── User Management ───────────────────────────────────────────────────────
async function loadUsers() {
    const tbody = document.getElementById('users-tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="table-empty">Loading…</td></tr>';

    const data = await api.getAdminUsers(currentUserSearch, currentUserPage);

    if (!data || data.error) {
        tbody.innerHTML = '<tr><td colspan="8" class="table-empty">Failed to load users.</td></tr>';
        return;
    }

    const { users, total, total_pages } = data;

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="table-empty">No users found.</td></tr>';
        renderPagination(0, 1);
        return;
    }

    tbody.innerHTML = users.map(u => `
        <tr>
            <td style="color:var(--color-text-3);">${u.id}</td>
            <td style="font-weight:600; color:var(--color-text);">${escHtml(u.username)}</td>
            <td>${escHtml(u.email)}</td>
            <td>
                <span class="badge ${u.role === 'ADMIN' ? 'badge-active' : 'badge-upcoming'}">${u.role}</span>
            </td>
            <td>${u.total_bids.toLocaleString()}</td>
            <td>
                <span style="font-size:0.75rem; color:${u.email_verified ? 'var(--color-active)' : 'var(--color-ended)'};">
                    ${u.email_verified ? '✓ Yes' : '✗ No'}
                </span>
            </td>
            <td style="color:var(--color-text-3); font-size:0.75rem;">${formatDateTime(u.created_at)}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="openUserDetail(${u.id})">View</button>
            </td>
        </tr>`
    ).join('');

    renderPagination(total_pages, currentUserPage);
}

function renderPagination(totalPages, currentPage) {
    const container = document.getElementById('user-pagination');
    if (totalPages <= 1) { container.innerHTML = ''; return; }

    let html = `<button class="page-btn" onclick="goToUserPage(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}>← Prev</button>`;

    for (let i = 1; i <= totalPages; i++) {
        if (i === currentPage || i === 1 || i === totalPages || Math.abs(i - currentPage) <= 1) {
            html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToUserPage(${i})">${i}</button>`;
        } else if (i === currentPage - 2 || i === currentPage + 2) {
            html += `<span style="padding:0.375rem;">…</span>`;
        }
    }

    html += `<button class="page-btn" onclick="goToUserPage(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}>Next →</button>`;
    container.innerHTML = html;
}

function goToUserPage(page) {
    currentUserPage = page;
    loadUsers();
}

async function openUserDetail(userId) {
    const modal = document.getElementById('user-detail-modal');
    const content = document.getElementById('user-detail-content');
    content.innerHTML = '<p class="text-muted">Loading…</p>';
    modal.style.display = 'flex';

    const data = await api.getAdminUser(userId);

    if (data.error) {
        content.innerHTML = `<p class="text-muted">${escHtml(data.error)}</p>`;
        return;
    }

    const { stats } = data;
    content.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:1rem;">
            <div class="user-detail-field">
                <span style="font-size:0.6875rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--color-text-3);">Username</span>
                <span style="font-size:1.125rem; font-weight:700; color:var(--color-text);">${escHtml(data.username)}</span>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.75rem;">
                <div>
                    <span style="font-size:0.6875rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--color-text-3); display:block;">Email</span>
                    <span style="font-size:0.875rem; color:var(--color-text-2);">${escHtml(data.email)}</span>
                </div>
                <div>
                    <span style="font-size:0.6875rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--color-text-3); display:block;">Role</span>
                    <span class="badge ${data.role === 'ADMIN' ? 'badge-active' : 'badge-upcoming'}">${data.role}</span>
                </div>
                <div>
                    <span style="font-size:0.6875rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--color-text-3); display:block;">Registered</span>
                    <span style="font-size:0.875rem; color:var(--color-text-2);">${formatDateTime(data.created_at)}</span>
                </div>
                <div>
                    <span style="font-size:0.6875rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--color-text-3); display:block;">Email Verified</span>
                    <span style="font-size:0.875rem; color:${data.email_verified ? 'var(--color-active)' : 'var(--color-ended)'};">${data.email_verified ? 'Yes' : 'No'}</span>
                </div>
            </div>
            <hr style="border:none; border-top:1px solid var(--color-border);">
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.75rem;">
                <div class="analytics-stat">
                    <span class="analytics-stat-label">Total Bids</span>
                    <span class="analytics-stat-value">${stats.total_bids.toLocaleString()}</span>
                </div>
                <div class="analytics-stat">
                    <span class="analytics-stat-label">Highest Bid</span>
                    <span class="analytics-stat-value">${formatCurrency(stats.highest_bid)}</span>
                </div>
                <div class="analytics-stat">
                    <span class="analytics-stat-label">Total Amount</span>
                    <span class="analytics-stat-value">${formatCurrency(stats.total_amount)}</span>
                </div>
                <div class="analytics-stat">
                    <span class="analytics-stat-label">Auctions</span>
                    <span class="analytics-stat-value">${stats.auctions_participated}</span>
                </div>
            </div>
        </div>`;
}

function closeUserModal() {
    document.getElementById('user-detail-modal').style.display = 'none';
}

// ─── Analytics Tab ─────────────────────────────────────────────────────────
async function loadAnalyticsTab() {
    const data = await api.getAuctionPerformance();
    const tbody = document.getElementById('auction-perf-tbody');

    if (!data || data.length === 0 || data.error) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No auction data yet.</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(row => `
        <tr>
            <td style="font-weight:600; color:var(--color-text);">${escHtml(row.title)}</td>
            <td><span class="badge ${statusBadgeClass(row.status)}">${row.status}</span></td>
            <td>${formatCurrency(row.starting_price)}</td>
            <td>${row.highest_bid > 0 ? formatCurrency(row.highest_bid) : '—'}</td>
            <td>${row.bid_count.toLocaleString()}</td>
            <td>${row.total_bid_value > 0 ? formatCurrency(row.total_bid_value) : '—'}</td>
        </tr>`
    ).join('');
}

// ─── Utilities ─────────────────────────────────────────────────────────────
function showMsg(container, text, type) {
    container.innerHTML = `<div class="alert alert-${type}" style="margin-bottom:1rem;">${escHtml(text)}</div>`;
}

function escHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
