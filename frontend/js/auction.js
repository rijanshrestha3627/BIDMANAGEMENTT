// Auction details page logic — redesigned UI, all original API calls preserved.
let currentAuctionId = null;

// ── Image mapping (mirrors app.js) ──────────────────────────────────────────
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
const FALLBACK_IMG = 'assets/product-laptop.jpg';

function getAuctionImage(title) {
    if (!title) return FALLBACK_IMG;
    const lower = title.toLowerCase();
    for (const entry of IMAGE_MAP) {
        if (entry.keywords.some(kw => lower.includes(kw))) return entry.img;
    }
    return FALLBACK_IMG;
}

// ── DOMContentLoaded ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentAuctionId = urlParams.get('id');

    if (currentAuctionId) {
        await loadAuctionDetails(currentAuctionId);
        await loadBidHistory(currentAuctionId);
    } else {
        document.getElementById('auction-details-container').innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="24" cy="24" r="18" stroke="currentColor" stroke-width="2"/>
                    <path d="M24 16v8M24 32v.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
                </svg>
                <h3>No auction selected</h3>
                <p><a href="index.html">Back to all listings</a></p>
            </div>
        `;
    }
});

// ── Load auction details ──────────────────────────────────────────────────────
async function loadAuctionDetails(id) {
    const container = document.getElementById('auction-details-container');
    const auction = await api.getAuction(id);

    if (!auction) {
        container.innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="24" cy="24" r="18" stroke="currentColor" stroke-width="2"/>
                    <path d="M24 16v8M24 32v.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
                </svg>
                <h3>Auction not found</h3>
                <p><a href="index.html">Back to all listings</a></p>
            </div>
        `;
        return;
    }

    // Update page title
    document.title = `${auction.title} — University Auctions`;

    const imgSrc = auction.image_path ? `http://localhost:5000/${auction.image_path}` : getAuctionImage(auction.title);
    const currentBid = auction.current_highest_bid > 0
        ? formatCurrency(auction.current_highest_bid)
        : 'No bids yet';
    const minNext = formatCurrency(auction.minimum_next_bid);
    const isActive = auction.status === 'ACTIVE';

    container.innerHTML = `
        <div class="detail-layout">

            <!-- LEFT column: image + info + bid history -->
            <div class="detail-main">

                <!-- Product image -->
                <div class="detail-image-wrap">
                    <img src="${imgSrc}" alt="${auction.title}">
                </div>

                <!-- Auction header -->
                <div class="detail-header" style="margin-top:1.75rem;">
                    <div class="detail-status-row">
                        <span class="badge ${statusBadgeClass(auction.status)}">${auction.status}</span>
                    </div>
                    <h2 class="detail-title">${auction.title}</h2>
                    <p class="detail-description">${auction.description}</p>
                </div>

                <!-- Meta info grid -->
                <div class="detail-info-block">
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Starting Price</span>
                            <span class="info-value">${formatCurrency(auction.starting_price)}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Minimum Increment</span>
                            <span class="info-value">${formatCurrency(auction.minimum_increment)}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Starts</span>
                            <span class="info-value">${formatDateTime(auction.start_time)}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Ends</span>
                            <span class="info-value">${formatDateTime(auction.end_time)}</span>
                        </div>
                    </div>
                </div>

                <!-- Bid history -->
                <div class="bid-history-section">
                    <h3>Bid History</h3>
                    <div id="bid-history">
                        <p class="text-muted" style="font-size:0.875rem;">Loading…</p>
                    </div>
                </div>
            </div>

            <!-- RIGHT column: bidding panel -->
            <div class="bidding-panel ${!isActive ? 'bidding-disabled' : ''}">

                <!-- Current bid display -->
                <div class="panel-bid-summary">
                    <span class="panel-label">Current Highest Bid</span>
                    <span class="panel-price" id="display-current-bid">${currentBid}</span>

                    ${isActive ? `
                    <div class="panel-min-bid">
                        <span class="min-label">Minimum next bid</span>
                        <span class="min-value">${minNext}</span>
                    </div>` : ''}
                </div>

                ${isActive ? `
                <div id="bid-message"></div>
                <div class="bid-form" id="bid-form-container">
                    <!-- Populated by JS based on auth state -->
                    <p class="text-muted" style="margin-bottom: 1rem;">Checking authentication...</p>
                </div>
                ` : `
                <div class="panel-disabled-msg">
                    <h4>${auction.status === 'UPCOMING' ? 'Bidding Not Yet Open' : 'Bidding Closed'}</h4>
                    <p>${auction.status === 'UPCOMING'
                        ? 'This auction has not started yet. Bidding opens at ' + formatDateTime(auction.start_time) + '.'
                        : 'This auction has ended. No more bids are accepted.'}</p>
                </div>
                `}
            </div>
        </div>
    `;

    // Render auth-dependent bid form
    if (isActive) {
        const authData = await api.getMe();
        const bidFormContainer = document.getElementById('bid-form-container');
        if (authData && authData.authenticated) {
            bidFormContainer.innerHTML = `
                <div class="form-group">
                    <label for="bid-amount">Your Bid Amount (₹)</label>
                    <input type="number" class="form-input" id="bid-amount"
                           min="${auction.minimum_next_bid}" step="1"
                           value="${Math.ceil(auction.minimum_next_bid)}">
                </div>
                <button class="btn btn-primary btn-full" id="bid-btn" onclick="submitBid()">
                    Place Bid
                </button>
                <p class="bid-hint">Minimum bid: ${minNext}</p>
            `;
        } else {
            bidFormContainer.innerHTML = `
                <div class="panel-disabled-msg" style="padding:1rem; text-align:center;">
                    <p style="margin-bottom:0.75rem;">You must be logged in to place a bid.</p>
                    <a href="login.html" class="btn btn-primary btn-sm">Login</a>
                    <a href="register.html" class="btn btn-secondary btn-sm" style="margin-left:0.5rem;">Register</a>
                </div>
            `;
        }
    }
}

// ── Load bid history ──────────────────────────────────────────────────────────
async function loadBidHistory(auctionId) {
    const container = document.getElementById('bid-history');
    if (!container) return;

    const bids = await api.getBids(auctionId);

    if (!bids || bids.length === 0) {
        container.innerHTML = '<p class="no-bids">No bids have been placed yet. Be the first to bid!</p>';
        return;
    }

    let html = '<div class="bid-list">';
    bids.forEach((bid, index) => {
        const isTop = index === 0;
        html += `
            <div class="bid-item ${isTop ? 'bid-highest' : ''}">
                <span class="bid-rank">${isTop ? '<span class="bid-crown">★</span>' : index + 1}</span>
                <span class="bid-bidder">${escapeHtml(bid.bidder_name)}</span>
                <span class="bid-amount">${formatCurrency(bid.amount)}</span>
                <span class="bid-time">${formatDateTime(bid.created_at)}</span>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// ── Submit bid ────────────────────────────────────────────────────────────────
async function submitBid() {
    const bidBtn = document.getElementById('bid-btn');
    const messageDiv = document.getElementById('bid-message');
    const bidAmount = parseFloat(document.getElementById('bid-amount').value);

    // Client-side validation
    if (isNaN(bidAmount) || bidAmount <= 0) {
        showMessage(messageDiv, 'Please enter a valid bid amount.', 'error');
        return;
    }

    // Disable button to prevent double-click
    bidBtn.disabled = true;
    bidBtn.textContent = 'Placing bid…';

    const result = await api.placeBid(currentAuctionId, bidAmount);

    if (result.success) {
        showMessage(messageDiv, 'Bid accepted! You are now the highest bidder.', 'success');
        // Wait so user sees confirmation, then reload
        await new Promise(resolve => setTimeout(resolve, 1500));
        await loadAuctionDetails(currentAuctionId);
        await loadBidHistory(currentAuctionId);
    } else {
        showMessage(messageDiv, result.message || 'Bid was rejected.', 'error');
        bidBtn.disabled = false;
        bidBtn.textContent = 'Place Bid';
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function showMessage(container, text, type) {
    if (!container) return;
    container.innerHTML = `<div class="alert alert-${type}">${text}</div>`;
    if (type !== 'success') {
        setTimeout(() => {
            if (container && container.parentNode) container.innerHTML = '';
        }, 6000);
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
