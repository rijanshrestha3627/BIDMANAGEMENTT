/**
 * profile.js — Phase 4
 *
 * Handles:
 *  - Profile header + quick stats
 *  - Auction Activity section (cards, filter tabs)
 *  - Bid History section (table, sort)
 *  - My Analytics section (stat cards, SVG bar chart, win/loss chart)
 *  - Account & Security section
 *  - All modals (username, email, password)
 *  - Section navigation
 *
 * All data comes from real API calls.
 * Preserves Phase 2 modal functionality exactly.
 */

'use strict';

// ── Global state ────────────────────────────────────────────────────────────
let _activityData = null;   // cached from /api/profile/activity
let _currentFilter = 'ALL';
let _currentSort = 'newest';

// ── Boot ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Auth guard
    const authData = await api.getMe();
    if (!authData || !authData.authenticated) {
        window.location.href = 'login.html';
        return;
    }

    // Load base profile (username, email, dates)
    loadProfileBase();

    // Load activity data (stats, auction cards, bid table, charts)
    loadActivity();

    // Bind section nav
    document.querySelectorAll('.profile-nav-item').forEach(btn => {
        btn.addEventListener('click', () => switchSection(btn.dataset.section));
    });

    // Bind activity filter tabs
    document.querySelectorAll('#activity-filters .pf-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('#activity-filters .pf-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            _currentFilter = tab.dataset.filter;
            renderActivityCards();
        });
    });

    // Bind bid sort
    document.getElementById('bid-sort').addEventListener('change', function () {
        _currentSort = this.value;
        renderBidTable();
    });
});

// ── Section Switching ────────────────────────────────────────────────────────
function switchSection(sectionId) {
    document.querySelectorAll('.profile-nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.section === sectionId);
    });
    document.querySelectorAll('.profile-section').forEach(sec => {
        sec.classList.toggle('active', sec.id === `section-${sectionId}`);
    });
}

// ── Load Base Profile ────────────────────────────────────────────────────────
async function loadProfileBase() {
    const res = await api.getProfile();
    if (!res.success || !res.user) return;

    const u = res.user;

    // Header card
    setText('profile-username-display', u.username);
    setText('profile-email-display', u.email);
    setText('profile-date-display', new Date(u.created_at).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }));

    const avatar = document.getElementById('profile-avatar');
    if (avatar) avatar.textContent = u.username.charAt(0).toUpperCase();

    // Role badge
    const roleBadge = document.getElementById('profile-role-badge');
    if (roleBadge) roleBadge.textContent = u.role || 'USER';

    // Email badge
    const emailBadge = document.getElementById('profile-email-badge');
    if (emailBadge) {
        if (u.email_verified) {
            emailBadge.textContent = 'Verified';
            emailBadge.classList.add('verified');
        } else {
            emailBadge.textContent = 'Unverified';
        }
    }

    // Account section fields
    setText('info-username', u.username);
    setText('info-email', u.email);
    const statusEl = document.getElementById('info-email-status');
    if (statusEl) {
        statusEl.innerHTML = u.email_verified
            ? '<span style="color:var(--color-active);">✓ Verified</span>'
            : '<span style="color:var(--color-danger);">✗ Not verified</span>';
    }
}

// ── Load Activity (big data load) ────────────────────────────────────────────
async function loadActivity() {
    const [activityRes, bidsOverTime] = await Promise.all([
        api.getActivity(),
        api.getUserBidsOverTime()
    ]);

    if (!activityRes.success) {
        // Show graceful errors
        const list = document.getElementById('activity-list');
        if (list) list.innerHTML = emptyState('🔨', "No auction activity yet.", "Browse Auctions", "index.html");
        document.getElementById('bid-history-tbody').innerHTML =
            '<tr><td colspan="6" class="table-empty">No bids placed yet.</td></tr>';
        return;
    }

    _activityData = activityRes;
    const { stats, auctions, bids } = activityRes;

    // Quick stats strip
    setText('pqs-bids', stats.total_bids.toLocaleString());
    setText('pqs-auctions', stats.auctions_participated.toLocaleString());
    setText('pqs-won', stats.won.toLocaleString());
    setText('pqs-active', stats.active_bids.toLocaleString());

    // Analytics stats
    setText('a-total-bids', stats.total_bids.toLocaleString());
    setText('a-total-amount', formatCurrency(stats.total_amount_bid));
    setText('a-highest', formatCurrency(stats.highest_bid));
    setText('a-won', stats.won.toLocaleString());

    // Render sections
    renderActivityCards();
    renderBidTable();
    renderUserBidChart(bidsOverTime);
    renderWinLossChart(stats);
}

// ── Activity Cards ───────────────────────────────────────────────────────────
function renderActivityCards() {
    const list = document.getElementById('activity-list');
    if (!_activityData || !_activityData.auctions) {
        list.innerHTML = emptyState('🔨', "No auction activity yet.", "Browse Auctions", "index.html");
        return;
    }

    let filtered = _activityData.auctions;
    if (_currentFilter !== 'ALL') {
        filtered = filtered.filter(a => a.result === _currentFilter);
    }

    if (filtered.length === 0) {
        list.innerHTML = emptyState('📂', `No auctions with status "${_currentFilter}".`, '', '');
        return;
    }

    list.innerHTML = filtered.map(a => {
        const imgUrl = a.image_path ? `http://localhost:5000/${a.image_path}` : 'assets/placeholder-item.jpg';
        const resultCls = resultBadgeClass(a.result);
        const userBidLabel = a.user_bid_count > 1 ? `${a.user_bid_count} bids placed` : '1 bid placed';
        return `
            <a href="auction.html?id=${a.auction_id}" class="activity-card" target="_blank" rel="noopener">
                <img src="${imgUrl}" alt="${escHtml(a.title)}" class="activity-card-img">
                <div class="activity-card-info">
                    <div class="activity-card-title">${escHtml(a.title)}</div>
                    <div class="activity-card-meta">
                        <span class="badge ${statusBadgeClass(a.status)}">${a.status}</span>
                        <span>${userBidLabel}</span>
                        <span>Last bid ${formatDateTime(a.last_bid_at)}</span>
                    </div>
                    <div style="margin-top:0.375rem;">
                        <span class="result-badge result-badge--${a.result.toLowerCase()}">${a.result}</span>
                    </div>
                </div>
                <div class="activity-card-stats">
                    <div class="activity-card-bid-label">My Highest</div>
                    <div class="activity-card-my-bid">${formatCurrency(a.user_highest_bid)}</div>
                    <div style="font-size:0.6875rem; color:var(--color-text-3); margin-top:0.25rem;">
                        Current: ${formatCurrency(a.current_highest_bid)}
                    </div>
                </div>
            </a>`;
    }).join('');
}

// ── Bid History Table ────────────────────────────────────────────────────────
function renderBidTable() {
    const tbody = document.getElementById('bid-history-tbody');
    if (!_activityData || !_activityData.bids || _activityData.bids.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No bids placed yet. <a href="index.html" style="color:var(--color-text); font-weight:600;">Browse Auctions</a></td></tr>';
        return;
    }

    let bids = [..._activityData.bids];

    // Sort
    if (_currentSort === 'oldest') {
        bids.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    } else if (_currentSort === 'highest') {
        bids.sort((a, b) => b.amount - a.amount);
    } else {
        bids.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }

    tbody.innerHTML = bids.map(b => {
        const imgUrl = b.auction_image ? `http://localhost:5000/${b.auction_image}` : 'assets/placeholder-item.jpg';
        const resultCls = resultBadgeClass(b.result);
        return `<tr>
            <td>
                <div class="bht-auction-cell">
                    <img src="${imgUrl}" alt="" class="bht-img">
                    <a href="auction.html?id=${b.auction_id}" class="bht-title" title="${escHtml(b.auction_title)}" target="_blank">${escHtml(b.auction_title)}</a>
                </div>
            </td>
            <td style="font-weight:700; color:var(--color-text);">${formatCurrency(b.amount)}</td>
            <td style="color:var(--color-text-3); font-size:0.75rem; white-space:nowrap;">${formatDateTime(b.created_at)}</td>
            <td>${formatCurrency(b.current_highest_bid)}</td>
            <td><span class="badge ${statusBadgeClass(b.auction_status)}">${b.auction_status}</span></td>
            <td><span class="result-badge result-badge--${b.result.toLowerCase()}">${b.result}</span></td>
        </tr>`;
    }).join('');
}

// ── User Bid Activity Chart (SVG) ────────────────────────────────────────────
function renderUserBidChart(data) {
    const container = document.getElementById('user-bid-chart');
    if (!data || data.length === 0) {
        container.innerHTML = '<p class="chart-loading-msg">No bid activity in the last 14 days.</p>';
        return;
    }

    const hasActivity = data.some(d => d.count > 0);
    if (!hasActivity) {
        container.innerHTML = '<p class="chart-loading-msg">No bid activity yet. Place bids to see your chart!</p>';
        return;
    }

    const maxCount = Math.max(...data.map(d => d.count), 1);
    const n = data.length; // always 14
    // Use percentage viewBox. Avoid label overlap by only showing even-indexed labels.
    const svgW = 420;
    const svgH = 160;
    const padL = 24, padR = 8, padTop = 18, padBot = 28;
    const chartW = svgW - padL - padR;
    const chartH = svgH - padTop - padBot;
    const barW = chartW / n * 0.6;
    const barGap = chartW / n;

    let bars = '', labels = '', values = '';

    data.forEach((d, i) => {
        const x = padL + i * barGap + (barGap - barW) / 2;
        const barH = d.count > 0 ? Math.max((d.count / maxCount) * chartH, 3) : 0;
        const y = padTop + chartH - barH;
        const cx = x + barW / 2;

        bars += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barH.toFixed(1)}"
            rx="2" fill="var(--color-text)" opacity="${d.count > 0 ? '0.85' : '0.12'}">
            <title>${d.label}: ${d.count} bid${d.count !== 1 ? 's' : ''}</title>
        </rect>`;

        // Show labels every 2nd day to avoid overlap, always show first and last
        if (i === 0 || i === n - 1 || (i % 2 === 0)) {
            labels += `<text x="${cx.toFixed(1)}" y="${(padTop + chartH + 16).toFixed(1)}"
                text-anchor="middle" font-size="8" fill="var(--color-text-3)"
                font-family="Inter,system-ui,sans-serif">${d.label}</text>`;
        }

        if (d.count > 0) {
            values += `<text x="${cx.toFixed(1)}" y="${(y - 4).toFixed(1)}"
                text-anchor="middle" font-size="8.5" fill="var(--color-text-2)"
                font-family="Inter,system-ui,sans-serif">${d.count}</text>`;
        }
    });

    container.innerHTML = `
        <svg viewBox="0 0 ${svgW} ${svgH}" style="width:100%; height:100%; overflow:visible;"
             role="img" aria-label="Bid activity bar chart showing bids over the last 14 days">
            <!-- axis -->
            <line x1="${padL}" y1="${padTop + chartH}" x2="${svgW - padR}" y2="${padTop + chartH}"
                  stroke="var(--color-border)" stroke-width="1"/>
            ${bars}
            ${values}
            ${labels}
        </svg>`;
}

// ── Win/Loss Chart ───────────────────────────────────────────────────────────
function renderWinLossChart(stats) {
    const container = document.getElementById('win-loss-chart');
    const total = (stats.won + stats.lost + stats.active_bids) || 1;

    const rows = [
        { label: 'Won', count: stats.won, cls: 'won', pct: (stats.won / total * 100) },
        { label: 'Lost', count: stats.lost, cls: 'lost', pct: (stats.lost / total * 100) },
        { label: 'Active', count: stats.active_bids, cls: 'active', pct: (stats.active_bids / total * 100) }
    ];

    const hasData = rows.some(r => r.count > 0);
    if (!hasData) {
        container.innerHTML = '<p class="chart-loading-msg">Participate in auctions to see your results.</p>';
        return;
    }

    container.innerHTML = rows.map(r => `
        <div class="wl-row">
            <span class="wl-label">${r.label}</span>
            <div class="wl-track">
                <div class="wl-fill wl-fill--${r.cls}" style="width:${r.pct.toFixed(1)}%"></div>
            </div>
            <span class="wl-count">${r.count}</span>
        </div>
    `).join('');
}

// ── Modal Handling (Phase 2 preserved) ──────────────────────────────────────
function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
    if (id === 'username-modal') {
        document.getElementById('new-username-input').value = '';
        showMessage('username-msg', '', '');
    } else if (id === 'email-modal') {
        document.getElementById('new-email-input').value = '';
        document.getElementById('email-otp-input').value = '';
        document.getElementById('email-step-1').classList.remove('hidden');
        document.getElementById('email-step-2').classList.add('hidden');
        showMessage('email-msg', '', '');
    } else if (id === 'password-modal') {
        document.getElementById('current-password-input').value = '';
        document.getElementById('new-password-input').value = '';
        document.getElementById('confirm-password-input').value = '';
        showMessage('password-msg', '', '');
    }
}

function showMessage(elementId, text, type) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = text;
    el.className = 'alert ' + (type === 'success' ? 'alert-success' : type === 'error' ? 'alert-error' : '');
    if (!text) el.className = '';
    el.style.marginBottom = text ? '1rem' : '0';
}

// ── Profile Actions (Phase 2 preserved exactly) ──────────────────────────────
async function saveUsername() {
    const nu = document.getElementById('new-username-input').value;
    const btn = document.getElementById('btn-save-username');
    if (!nu.trim()) return showMessage('username-msg', 'Username cannot be empty', 'error');

    btn.disabled = true;
    btn.textContent = 'Saving…';

    const res = await api.changeUsername(nu);
    if (res.success) {
        showMessage('username-msg', 'Username updated!', 'success');
        setTimeout(() => { closeModal('username-modal'); window.location.reload(); }, 1500);
    } else {
        showMessage('username-msg', res.error || 'Failed to update', 'error');
        btn.disabled = false;
        btn.textContent = 'Save';
    }
}

let emailOtpInterval = null;

async function requestEmailChange() {
    const ne = document.getElementById('new-email-input').value;
    const btn = document.getElementById('btn-request-email');
    if (!ne.trim()) return showMessage('email-msg', 'Email cannot be empty', 'error');

    btn.disabled = true;
    btn.textContent = 'Sending…';

    const res = await api.requestEmailChange(ne);
    if (res.success) {
        showMessage('email-msg', 'Code sent to new email!', 'success');
        document.getElementById('otp-email-target').textContent = ne;
        setTimeout(() => {
            document.getElementById('email-step-1').classList.add('hidden');
            document.getElementById('email-step-2').classList.remove('hidden');
            document.getElementById('email-otp-input').value = '';
            document.getElementById('email-otp-input').focus();
            startEmailOtpTimer();
            showMessage('email-msg', '', '');
        }, 1000);
    } else {
        showMessage('email-msg', res.error || 'Failed to send', 'error');
        btn.disabled = false;
        btn.textContent = 'Send Code';
    }
}

function startEmailOtpTimer() {
    if (emailOtpInterval) clearInterval(emailOtpInterval);
    const btnResend = document.getElementById('btn-resend-email');
    const timerText = document.getElementById('otp-timer-text');
    let timeLeft = 600; // 10 minutes total expiry
    let resendCooldown = 60; // 60 seconds cooldown for resend

    btnResend.disabled = true;

    emailOtpInterval = setInterval(() => {
        timeLeft--;
        resendCooldown--;

        if (timeLeft <= 0) {
            clearInterval(emailOtpInterval);
            timerText.textContent = 'Code expired';
            btnResend.textContent = 'Resend code';
            btnResend.disabled = false;
            return;
        }

        const m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
        const s = (timeLeft % 60).toString().padStart(2, '0');
        timerText.textContent = `Code expires in ${m}:${s}`;

        if (resendCooldown > 0) {
            btnResend.textContent = `Resend code (${resendCooldown}s)`;
            btnResend.disabled = true;
        } else {
            btnResend.textContent = 'Resend code';
            btnResend.disabled = false;
        }
    }, 1000);
}

async function resendEmailOtp() {
    const btn = document.getElementById('btn-resend-email');
    btn.disabled = true;
    btn.textContent = 'Sending...';
    showMessage('email-msg', '', '');

    const ne = document.getElementById('new-email-input').value;
    const res = await api.requestEmailChange(ne);
    
    if (res.success) {
        showMessage('email-msg', 'New code sent!', 'success');
        document.getElementById('email-otp-input').value = '';
        document.getElementById('email-otp-input').focus();
        startEmailOtpTimer();
    } else {
        showMessage('email-msg', res.error || 'Failed to resend', 'error');
        btn.disabled = false;
        btn.textContent = 'Resend code';
    }
}

async function verifyEmailChange() {
    const otp = document.getElementById('email-otp-input').value;
    const btn = document.getElementById('btn-verify-email');
    if (!otp.trim()) return showMessage('email-msg', 'OTP is required', 'error');

    btn.disabled = true;
    btn.textContent = 'Verifying…';

    const res = await api.verifyEmailChange(otp);
    if (res.success) {
        showMessage('email-msg', 'Email updated!', 'success');
        setTimeout(() => { closeModal('email-modal'); loadProfileBase(); }, 1500);
    } else {
        showMessage('email-msg', res.error || 'Verification failed', 'error');
        btn.disabled = false;
        btn.textContent = 'Verify';
    }
}

async function savePassword() {
    const cp = document.getElementById('current-password-input').value;
    const np = document.getElementById('new-password-input').value;
    const confirm = document.getElementById('confirm-password-input').value;
    const btn = document.getElementById('btn-save-password');

    if (!cp || !np || !confirm) return showMessage('password-msg', 'All fields required', 'error');
    if (np !== confirm) return showMessage('password-msg', 'Passwords do not match', 'error');
    if (np.length < 6) return showMessage('password-msg', 'New password must be at least 6 characters', 'error');

    btn.disabled = true;
    btn.textContent = 'Changing…';

    const res = await api.changePassword({ current_password: cp, new_password: np, confirm_password: confirm });
    if (res.success) {
        showMessage('password-msg', 'Password updated!', 'success');
        setTimeout(() => closeModal('password-modal'), 1500);
    } else {
        showMessage('password-msg', res.error || 'Failed to update', 'error');
        btn.disabled = false;
        btn.textContent = 'Change Password';
    }
}

// ── Utilities ────────────────────────────────────────────────────────────────
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

function resultBadgeClass(result) {
    const map = { WINNING: 'winning', OUTBID: 'outbid', WON: 'won', LOST: 'lost', ACTIVE: 'active', UPCOMING: 'active' };
    return map[result] || 'active';
}

function emptyState(icon, msg, linkText, linkHref) {
    return `<div class="activity-empty-state">
        <div class="empty-icon-wrap">${icon}</div>
        <p>${escHtml(msg)}</p>
        ${linkText ? `<a href="${linkHref}">${escHtml(linkText)}</a>` : ''}
    </div>`;
}
