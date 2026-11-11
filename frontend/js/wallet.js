/**
 * wallet.js — Phase 7 Wallet System
 *
 * Handles all wallet UI interactions:
 *  - Balance display
 *  - Add Money (2-step simulated deposit flow)
 *  - Withdraw Money
 *  - Transaction History (paginated, filtered)
 *  - Withdrawal Requests
 *
 * SECURITY NOTES:
 *  - No wallet amounts are sourced from localStorage, URL params, or client state.
 *  - All amounts are entered by user and sent to server; server validates everything.
 *  - The idempotency key from step 1 is required for step 2 confirmation.
 */

'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let _walletData = null;
let _txnPage = 1;
let _txnTotalPages = 1;
let _depositIdempotencyKey = null;
let _depositAmount = null;
let _depositMethod = null;

// ── Boot ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Auth guard — wallet requires login
    const authData = await api.getMe();
    if (!authData || !authData.authenticated) {
        window.location.href = 'login.html';
        return;
    }

    // Update auth header
    if (typeof updateAuthHeader === 'function') updateAuthHeader(authData.user);

    // Load wallet data
    await loadWalletData();

    // Bind tab switching
    document.querySelectorAll('.wallet-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Bind transaction filter
    document.getElementById('txn-type-filter').addEventListener('change', () => {
        _txnPage = 1;
        loadTransactions();
    });

    // Bind withdraw method toggle
    const wdMethod = document.getElementById('withdraw-method');
    if (wdMethod) {
        wdMethod.addEventListener('change', () => {
            const upiField = document.getElementById('upi-field');
            if (upiField) upiField.style.display = wdMethod.value === 'UPI' ? '' : 'none';
        });
    }
});

// ── Tab Switching ─────────────────────────────────────────────────────────────
function switchTab(tabId) {
    document.querySelectorAll('.wallet-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tabId);
    });
    document.querySelectorAll('.wallet-tab-content').forEach(c => {
        c.classList.toggle('active', c.id === `wtab-content-${tabId}`);
    });

    if (tabId === 'transactions') loadTransactions();
    if (tabId === 'withdrawals') loadWithdrawals();
}

// ── Load Wallet Data ──────────────────────────────────────────────────────────
async function loadWalletData() {
    try {
        const res = await api.getWallet();
        if (!res || !res.success) {
            console.error('Wallet load failed:', res);
            return;
        }
        _walletData = res.wallet;
        renderBalanceCards(_walletData);
        loadTransactions();

        // Update available balance in withdraw modal
        const avail = document.getElementById('withdraw-available-balance');
        if (avail) avail.textContent = formatCurrency(_walletData.available);
    } catch (e) {
        console.error('loadWalletData error:', e);
    }
}

// ── Balance Cards ─────────────────────────────────────────────────────────────
function renderBalanceCards(wallet) {
    setText('wallet-available',  formatCurrency(wallet.available));
    setText('wallet-total',      formatCurrency(wallet.balance));
    setText('wallet-reserved',   formatCurrency(wallet.reserved));
    setText('wallet-deposited',  formatCurrency(wallet.total_deposited));
    setText('wallet-spent',      formatCurrency(wallet.total_spent));
    setText('wallet-withdrawn',  formatCurrency(wallet.total_withdrawn));
}

// ── Transaction History ───────────────────────────────────────────────────────
async function loadTransactions() {
    const loadingEl = document.getElementById('txn-loading');
    const tableWrap = document.getElementById('txn-table-wrap');
    const emptyEl   = document.getElementById('txn-empty');
    const tbody     = document.getElementById('txn-tbody');

    loadingEl.style.display = '';
    tableWrap.style.display  = 'none';
    emptyEl.style.display    = 'none';

    const typeFilter = document.getElementById('txn-type-filter').value;
    const res = await api.getWalletTransactions(_txnPage, 20, typeFilter);

    loadingEl.style.display = 'none';

    if (!res || !res.success) {
        tbody.innerHTML = `<tr><td colspan="5" class="table-empty">Failed to load transactions.</td></tr>`;
        tableWrap.style.display = '';
        return;
    }

    _txnTotalPages = res.total_pages || 1;
    const txns = res.transactions || [];

    if (txns.length === 0) {
        emptyEl.style.display = '';
        renderPagination('txn-pagination', _txnPage, _txnTotalPages, (p) => {
            _txnPage = p; loadTransactions();
        });
        return;
    }

    tbody.innerHTML = txns.map(t => {
        const typeLower = t.type.toLowerCase().replace(/_/g, '_');
        const dirClass = `txn-${t.direction}`;
        const sign = t.direction === 'credit' ? '+' : t.direction === 'debit' ? '-' : '';
        const statusLower = t.status.toLowerCase();
        return `<tr>
            <td style="color:var(--color-text-3); font-size:0.75rem; white-space:nowrap;">
                ${formatDateTime(t.created_at)}
            </td>
            <td>
                <span class="txn-type-badge txn-type-badge--${typeLower}">
                    ${txnIcon(t.type)} ${escHtml(t.type_label)}
                </span>
            </td>
            <td style="font-size:0.8125rem; color:var(--color-text-2); max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escHtml(t.description || '')}">
                ${escHtml(t.description || '—')}
            </td>
            <td class="${dirClass}" style="white-space:nowrap; font-weight:700;">
                ${sign}${formatCurrency(t.amount)}
            </td>
            <td>
                <span class="wallet-status-badge wallet-status-badge--${statusLower}">
                    ${escHtml(t.status)}
                </span>
            </td>
        </tr>`;
    }).join('');

    tableWrap.style.display = '';
    renderPagination('txn-pagination', _txnPage, _txnTotalPages, (p) => {
        _txnPage = p; loadTransactions();
    });
}

// ── Withdrawal Requests ───────────────────────────────────────────────────────
async function loadWithdrawals() {
    const loadingEl = document.getElementById('wd-loading');
    const tableWrap = document.getElementById('wd-table-wrap');
    const emptyEl   = document.getElementById('wd-empty');
    const tbody     = document.getElementById('wd-tbody');

    loadingEl.style.display = '';
    tableWrap.style.display  = 'none';
    emptyEl.style.display    = 'none';

    const res = await api.getWithdrawals();
    loadingEl.style.display = 'none';

    if (!res || !res.success) {
        tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Failed to load withdrawals.</td></tr>`;
        tableWrap.style.display = '';
        return;
    }

    const wds = res.withdrawals || [];
    if (wds.length === 0) {
        emptyEl.style.display = '';
        return;
    }

    tbody.innerHTML = wds.map(w => {
        const canCancel = w.status === 'PENDING';
        const statusLower = w.status.toLowerCase();
        return `<tr>
            <td style="font-size:0.75rem; color:var(--color-text-3); white-space:nowrap;">
                ${formatDateTime(w.created_at)}
            </td>
            <td style="font-weight:700; color:var(--color-text);">${formatCurrency(w.amount)}</td>
            <td style="font-size:0.8125rem;">${escHtml(w.method)}</td>
            <td>
                <span class="wallet-status-badge wallet-status-badge--${statusLower}">
                    ${escHtml(w.status)}
                </span>
            </td>
            <td style="font-size:0.8125rem; color:var(--color-text-3); max-width:180px; overflow:hidden; text-overflow:ellipsis;">
                ${escHtml(w.admin_note || '—')}
            </td>
            <td>
                ${canCancel
                    ? `<button class="btn btn-secondary btn-sm" onclick="cancelWithdrawal(${w.id})">Cancel</button>`
                    : '—'
                }
            </td>
        </tr>`;
    }).join('');

    tableWrap.style.display = '';
}

// ── Cancel Withdrawal ─────────────────────────────────────────────────────────
async function cancelWithdrawal(wdId) {
    if (!confirm('Cancel this withdrawal request? The reserved funds will be released back to your wallet.')) return;
    const res = await api.cancelWithdrawal(wdId);
    if (res && res.success) {
        showToast('Withdrawal cancelled. Funds released.', 'success');
        await loadWalletData();
        await loadWithdrawals();
    } else {
        showToast((res && res.error) || 'Failed to cancel withdrawal', 'error');
    }
}

// ── Deposit Flow ──────────────────────────────────────────────────────────────

/** Step 1: Initiate deposit */
async function initiateDeposit() {
    const amountInput = document.getElementById('deposit-amount');
    const methodInput = document.getElementById('deposit-method');
    const btn         = document.getElementById('btn-initiate-deposit');
    const msgEl       = document.getElementById('deposit-msg');

    showMsg(msgEl, '', '');

    const amount = parseFloat(amountInput.value);
    if (!amount || amount <= 0) {
        return showMsg(msgEl, 'Please enter a valid amount.', 'error');
    }
    if (amount > 100000) {
        return showMsg(msgEl, 'Maximum deposit is ₹1,00,000.', 'error');
    }

    btn.disabled = true;
    btn.textContent = 'Processing…';

    const method = methodInput.value;
    const res = await api.initiateDeposit(amount, method);

    btn.disabled = false;
    btn.textContent = 'Proceed →';

    if (!res || !res.success) {
        return showMsg(msgEl, res?.error || 'Failed to initiate deposit', 'error');
    }

    // Store for step 2
    _depositIdempotencyKey = res.idempotency_key;
    _depositAmount = res.amount;
    _depositMethod = method;

    // Show step 2
    document.getElementById('deposit-step-1').classList.add('hidden');
    document.getElementById('deposit-step-2').classList.remove('hidden');
    setText('deposit-confirm-amount', formatCurrency(_depositAmount));
    setText('deposit-confirm-method', method);
}

/** Step 2: Confirm deposit */
async function confirmDeposit() {
    const btn   = document.getElementById('btn-confirm-deposit');
    const msgEl = document.getElementById('deposit-step2-msg');
    showMsg(msgEl, '', '');

    if (!_depositIdempotencyKey) {
        return showMsg(msgEl, 'Session error. Please start over.', 'error');
    }

    btn.disabled = true;
    btn.textContent = 'Confirming…';

    const res = await api.confirmDeposit(_depositIdempotencyKey);

    btn.disabled = false;
    btn.textContent = 'Confirm Payment ✓';

    if (!res || !res.success) {
        return showMsg(msgEl, res?.error || 'Confirmation failed', 'error');
    }

    // Show success
    document.getElementById('deposit-step-2').classList.add('hidden');
    document.getElementById('deposit-step-3').classList.remove('hidden');
    setText('deposit-success-msg', res.message || `${formatCurrency(_depositAmount)} credited to your wallet.`);

    // Reload wallet data in background
    loadWalletData();
}

/** Reset deposit modal to step 1 */
function resetDepositModal() {
    _depositIdempotencyKey = null;
    _depositAmount = null;
    _depositMethod = null;

    document.getElementById('deposit-step-1').classList.remove('hidden');
    document.getElementById('deposit-step-2').classList.add('hidden');
    document.getElementById('deposit-step-3').classList.add('hidden');
    document.getElementById('deposit-amount').value = '';
    showMsg(document.getElementById('deposit-msg'), '', '');
    showMsg(document.getElementById('deposit-step2-msg'), '', '');
}

// ── Withdrawal Submit ─────────────────────────────────────────────────────────
async function submitWithdrawal() {
    const amountInput = document.getElementById('withdraw-amount');
    const methodInput = document.getElementById('withdraw-method');
    const upiInput    = document.getElementById('withdraw-upi');
    const btn         = document.getElementById('btn-submit-withdraw');
    const msgEl       = document.getElementById('withdraw-msg');

    showMsg(msgEl, '', '');

    const amount = parseFloat(amountInput.value);
    if (!amount || amount <= 0) {
        return showMsg(msgEl, 'Please enter a valid amount.', 'error');
    }

    const available = _walletData ? _walletData.available : 0;
    if (amount > available) {
        return showMsg(msgEl, `Insufficient available balance. Available: ${formatCurrency(available)}`, 'error');
    }

    const method     = methodInput.value;
    const upi_id     = (upiInput && method === 'UPI') ? upiInput.value.trim() : null;

    btn.disabled = true;
    btn.textContent = 'Submitting…';

    const res = await api.createWithdrawal(amount, method, upi_id);

    btn.disabled = false;
    btn.textContent = 'Submit Request';

    if (!res || !res.success) {
        return showMsg(msgEl, res?.error || 'Failed to submit withdrawal', 'error');
    }

    showMsg(msgEl, res.message || 'Withdrawal request submitted!', 'success');
    amountInput.value = '';
    if (upiInput) upiInput.value = '';

    // Reload data
    await loadWalletData();
    await loadWithdrawals();

    setTimeout(() => closeModal('withdraw-modal'), 2000);
}

// ── Modal Helpers ─────────────────────────────────────────────────────────────
function openModal(id) {
    document.getElementById(id).classList.add('active');
    if (id === 'deposit-modal') {
        resetDepositModal();
        // Update available balance
        if (_walletData) {
            setText('withdraw-available-balance', formatCurrency(_walletData.available));
        }
    }
    if (id === 'withdraw-modal') {
        showMsg(document.getElementById('withdraw-msg'), '', '');
        // Update available balance display
        if (_walletData) {
            const avail = document.getElementById('withdraw-available-balance');
            if (avail) avail.textContent = formatCurrency(_walletData.available);
        }
    }
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
    if (id === 'deposit-modal') resetDepositModal();
}

// ── Pagination ────────────────────────────────────────────────────────────────
function renderPagination(containerId, currentPage, totalPages, onPageClick) {
    const container = document.getElementById(containerId);
    if (!container || totalPages <= 1) {
        if (container) container.innerHTML = '';
        return;
    }

    let html = '';
    html += `<button class="wpag-btn" ${currentPage <= 1 ? 'disabled' : ''}
        onclick="(${onPageClick.toString()})(${currentPage - 1})">← Prev</button>`;

    const start = Math.max(1, currentPage - 2);
    const end   = Math.min(totalPages, currentPage + 2);
    for (let p = start; p <= end; p++) {
        html += `<button class="wpag-btn ${p === currentPage ? 'active' : ''}"
            onclick="(${onPageClick.toString()})(${p})">${p}</button>`;
    }

    html += `<button class="wpag-btn" ${currentPage >= totalPages ? 'disabled' : ''}
        onclick="(${onPageClick.toString()})(${currentPage + 1})">Next →</button>`;

    container.innerHTML = html;
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val ?? '—';
}

function escHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function showMsg(el, text, type) {
    if (!el) return;
    el.textContent = text;
    el.className = 'alert ' + (type === 'success' ? 'alert-success' : type === 'error' ? 'alert-error' : '');
    if (!text) el.className = '';
    el.style.marginBottom = text ? '1rem' : '0';
}

function showToast(message, type) {
    // Simple toast using alert-style element
    const toast = document.createElement('div');
    toast.className = `alert ${type === 'success' ? 'alert-success' : 'alert-error'}`;
    toast.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;max-width:320px;animation:fadeIn 0.2s;';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

function txnIcon(type) {
    const icons = {
        DEPOSIT: '💰', WITHDRAWAL: '🏧', BID_RESERVE: '🔒',
        BID_RELEASE: '🔓', WIN_DEBIT: '🏆', ADMIN_CREDIT: '⚙️',
        ADMIN_DEBIT: '⚙️', REFUND: '↩️'
    };
    return icons[type] || '💳';
}

function handleLogout() {
    api.logout().then(() => { window.location.href = 'login.html'; });
}
