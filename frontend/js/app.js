// Home page logic — loads auction listings from the backend
// Preserves all existing API calls and data structures.

// ── Image mapping ──────────────────────────────────────────────────────────
// Maps keywords found in auction titles to product asset images.
const IMAGE_MAP = [
    { keywords: ['smartphone', 'phone', 'iphone', 'android', 'mobile'],  img: 'assets/product-smartphone.jpg' },
    { keywords: ['laptop', 'macbook', 'notebook', 'chromebook'],          img: 'assets/product-laptop.jpg' },
    { keywords: ['keyboard', 'mechanical'],                               img: 'assets/product-keyboard.jpg' },
    { keywords: ['camera', 'dslr', 'mirrorless', 'lens', 'gopro'],       img: 'assets/product-camera.jpg' },
    { keywords: ['headphone', 'earphone', 'airpod', 'earbuds', 'audio'], img: 'assets/product-headphones.jpg' },
    { keywords: ['book', 'textbook', 'novel', 'study'],                   img: 'assets/product-books.jpg' },
    { keywords: ['watch', 'smartwatch', 'fitbit'],                        img: 'assets/product-watch.jpg' },
    { keywords: ['tablet', 'ipad', 'kindle'],                             img: 'assets/product-tablet.jpg' },
    { keywords: ['backpack', 'bag', 'luggage'],                           img: 'assets/category-backpack.jpg' },
    { keywords: ['hoodie', 'jacket', 'cloth', 'shirt', 'apparel'],       img: 'assets/category-hoodie.jpg' },
    { keywords: ['desk', 'setup', 'monitor', 'gaming'],                   img: 'assets/category-desk-setup.jpg' },
    { keywords: ['console', 'playstation', 'xbox', 'nintendo', 'ps5'],   img: 'assets/category-gaming-console.jpg' },
    { keywords: ['lamp', 'light', 'led'],                                 img: 'assets/category-lamp.jpg' },
];

// Fallback cycling list so every card always has a distinct image
const FALLBACK_IMAGES = [
    'assets/product-laptop.jpg',
    'assets/product-camera.jpg',
    'assets/product-watch.jpg',
    'assets/product-keyboard.jpg',
    'assets/product-headphones.jpg',
    'assets/product-tablet.jpg',
];

let fallbackIndex = 0;

function getAuctionImage(title) {
    if (!title) return FALLBACK_IMAGES[0];
    const lower = title.toLowerCase();
    for (const entry of IMAGE_MAP) {
        if (entry.keywords.some(kw => lower.includes(kw))) return entry.img;
    }
    // Cycle through fallbacks so repeated "unknown" items vary
    const img = FALLBACK_IMAGES[fallbackIndex % FALLBACK_IMAGES.length];
    fallbackIndex++;
    return img;
}

// ── Time display ───────────────────────────────────────────────────────────
function formatCountdown(endTimeStr) {
    if (!endTimeStr) return '';
    try {
        const end = new Date(endTimeStr);
        const now = new Date();
        const diff = end - now;
        if (diff <= 0) return 'Ended';
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        if (h > 24) return Math.floor(h / 24) + 'd left';
        if (h > 0) return `${h}h ${m}m left`;
        return `${m}m left`;
    } catch { return ''; }
}

// ── Filter & sort state ────────────────────────────────────────────────────
let allAuctions = [];
let activeFilter = 'ALL';
let activeSort = 'newest';

// ── DOMContentLoaded ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    checkSystemStatus();
    await loadAuctions();

    // Filter tabs
    document.querySelectorAll('.filter-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            activeFilter = btn.dataset.filter;
            renderAuctions();
        });
    });

    // Sort select
    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', () => {
            activeSort = sortSelect.value;
            renderAuctions();
        });
    }
});

// ── System status ─────────────────────────────────────────────────────────
async function checkSystemStatus() {
    const badge = document.getElementById('api-status');
    const health = await api.checkHealth();

    if (health && health.status === 'ok') {
        const javaOk = health.java_engine === 'connected';
        badge.textContent = javaOk ? 'System Online' : 'Java Engine Offline';
        badge.style.color = javaOk ? 'var(--color-active)' : 'var(--color-upcoming)';
        badge.style.borderColor = javaOk ? 'var(--color-active-bd)' : 'var(--color-upcoming-bd)';
        badge.style.background = javaOk ? 'var(--color-active-bg)' : 'var(--color-upcoming-bg)';
    } else {
        badge.textContent = 'Backend Offline';
        badge.style.color = 'var(--color-danger)';
        badge.style.borderColor = 'var(--color-danger-bd)';
        badge.style.background = 'var(--color-danger-bg)';
    }
}

// ── Load auctions from API ─────────────────────────────────────────────────
async function loadAuctions() {
    allAuctions = await api.getAuctions();
    fallbackIndex = 0;
    renderAuctions();
}

// ── Render filtered + sorted auctions ─────────────────────────────────────
function renderAuctions() {
    const container = document.getElementById('auction-list');
    if (!container) return;

    // Filter
    let list = allAuctions;
    if (activeFilter !== 'ALL') {
        list = allAuctions.filter(a => a.status === activeFilter);
    }

    // Sort
    list = [...list];
    if (activeSort === 'price-high') {
        list.sort((a, b) => (b.current_highest_bid || b.starting_price) - (a.current_highest_bid || a.starting_price));
    } else if (activeSort === 'price-low') {
        list.sort((a, b) => (a.current_highest_bid || a.starting_price) - (b.current_highest_bid || b.starting_price));
    }
    // 'newest' = original order from API

    if (!list || list.length === 0) {
        const filterLabel = activeFilter === 'ALL' ? '' : activeFilter.toLowerCase() + ' ';
        container.innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="6" y="10" width="36" height="28" rx="3" stroke="currentColor" stroke-width="2"/>
                    <path d="M22 20l4 4-4 4M26 20l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <h3>No ${filterLabel}auctions found</h3>
                <p>${activeFilter === 'ALL'
                    ? 'No auctions exist yet. <a href="admin.html">Create one in Admin.</a>'
                    : 'Try a different filter or check back soon.'}</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    // Reset fallback index for stable image assignments
    fallbackIndex = 0;

    list.forEach(auction => {
        const imgSrc = auction.image_path ? `http://localhost:5000/${auction.image_path}` : getAuctionImage(auction.title);
        const currentBid = auction.current_highest_bid > 0
            ? formatCurrency(auction.current_highest_bid)
            : null;
        const minNext = formatCurrency(auction.minimum_next_bid);
        const countdown = auction.status === 'ACTIVE' ? formatCountdown(auction.end_time) : '';
        const bidsLabel = auction.bid_count != null
            ? `${auction.bid_count} bid${auction.bid_count !== 1 ? 's' : ''}`
            : '';

        const card = document.createElement('article');
        card.className = 'auction-card';
        card.innerHTML = `
            <div class="card-image">
                <img src="${imgSrc}" alt="${auction.title}" loading="lazy">
                <div class="card-status">
                    <span class="badge ${statusBadgeClass(auction.status)}">${auction.status}</span>
                </div>
            </div>
            <div class="card-body">
                <h3 class="card-title">${auction.title}</h3>
                <p class="card-desc">${auction.description}</p>

                <div class="card-pricing">
                    <div class="pricing-item">
                        <div class="pricing-label">Current Bid</div>
                        <div class="pricing-value ${currentBid ? '' : 'no-bids'}">${currentBid || 'No bids yet'}</div>
                    </div>
                    <div class="pricing-item">
                        <div class="pricing-label">Min Next</div>
                        <div class="pricing-value">${minNext}</div>
                    </div>
                </div>

                <div class="card-footer-row">
                    ${countdown ? `<span class="card-meta-item">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        ${countdown}
                    </span>` : `<span class="card-meta-item">${auction.status === 'UPCOMING' ? 'Starts ' + formatDateTime(auction.start_time) : 'Ended'}</span>`}
                    ${bidsLabel ? `<span class="card-meta-item">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                        ${bidsLabel}
                    </span>` : ''}
                </div>

                <a href="auction.html?id=${auction.id}" class="btn btn-primary btn-full">
                    View Auction →
                </a>
            </div>
        `;
        container.appendChild(card);
    });
}
