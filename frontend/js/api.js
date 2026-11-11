// API communication module
// All frontend-to-backend communication goes through this module.
const API_BASE_URL = 'http://localhost:5000/api';

const api = {
    async checkHealth() {
        try {
            const response = await fetch(`${API_BASE_URL}/health`);
            return await response.json();
        } catch (error) {
            console.error('Backend is unreachable', error);
            return null;
        }
    },

    // --- Authentication ---
    async register(data) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/register`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async login(email, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async adminLogin(email, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/admin-login`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async logout() {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getMe() {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { authenticated: false };
        }
    },

    // --- Profile ---
    async getProfile() {
        try {
            const response = await fetch(`${API_BASE_URL}/profile`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getActivity() {
        try {
            const response = await fetch(`${API_BASE_URL}/profile/activity`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getUserBidsOverTime() {
        try {
            const response = await fetch(`${API_BASE_URL}/profile/bids-over-time`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return [];
        }
    },

    async changeUsername(new_username) {
        try {
            const response = await fetch(`${API_BASE_URL}/profile/username`, {
                method: 'PUT',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_username })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async changePassword(data) {
        try {
            const response = await fetch(`${API_BASE_URL}/profile/password`, {
                method: 'PUT',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async requestEmailChange(new_email) {
        try {
            const response = await fetch(`${API_BASE_URL}/profile/email/request`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_email })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async verifyEmailChange(otp) {
        try {
            const response = await fetch(`${API_BASE_URL}/profile/email/verify`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ otp })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    // --- Password Reset ---
    async requestPasswordReset(email) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/password-reset/request`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async verifyPasswordReset(email, otp) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/password-reset/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, otp })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async completePasswordReset(email, otp, new_password) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/password-reset/complete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, otp, new_password })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getAuctions() {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching auctions', error);
            return [];
        }
    },

    async getAuction(id) {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions/${id}`);
            if (!response.ok) throw new Error('Auction not found');
            return await response.json();
        } catch (error) {
            console.error(`Error fetching auction ${id}`, error);
            return null;
        }
    },

    async createAuction(data) {
        try {
            const isFormData = data instanceof FormData;
            const options = {
                method: 'POST',
                credentials: 'include',
                body: isFormData ? data : JSON.stringify(data)
            };
            if (!isFormData) {
                options.headers = { 'Content-Type': 'application/json' };
            }
            // Use the correct admin endpoint
            const response = await fetch(`${API_BASE_URL}/admin/auctions`, options);
            return await response.json();
        } catch (error) {
            console.error('Error creating auction', error);
            return { error: 'Server unreachable' };
        }
    },

    async editAuction(id, data) {
        try {
            const isFormData = data instanceof FormData;
            const options = {
                method: 'PUT',
                credentials: 'include',
                body: isFormData ? data : JSON.stringify(data)
            };
            if (!isFormData) {
                options.headers = { 'Content-Type': 'application/json' };
            }
            const response = await fetch(`${API_BASE_URL}/admin/auctions/${id}`, options);
            return await response.json();
        } catch (error) {
            console.error('Error editing auction', error);
            return { error: 'Server unreachable' };
        }
    },

    async deleteAuction(id) {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/auctions/${id}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            return await response.json();
        } catch (error) {
            console.error('Error deleting auction', error);
            return { error: 'Server unreachable' };
        }
    },

    async placeBid(auctionId, amount) {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}/bids`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount: amount })
            });
            return await response.json();
        } catch (error) {
            console.error('Error placing bid', error);
            return { success: false, message: 'Server unreachable' };
        }
    },

    async getBids(auctionId) {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}/bids`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching bids', error);
            return [];
        }
    },

    async startAuction(auctionId) {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}/start`, {
                method: 'POST',
                credentials: 'include'
            });
            return await response.json();
        } catch (error) {
            console.error('Error starting auction', error);
            return { error: 'Server unreachable' };
        }
    },

    async endAuction(auctionId) {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}/end`, {
                method: 'POST',
                credentials: 'include'
            });
            return await response.json();
        } catch (error) {
            console.error('Error ending auction', error);
            return { error: 'Server unreachable' };
        }
    },

    async simulateConcurrentBids(auctionId, bidders) {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}/simulate-concurrent-bids`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bidders: bidders })
            });
            return await response.json();
        } catch (error) {
            console.error('Error running simulation', error);
            return { success: false, message: 'Server unreachable' };
        }
    },

    async getAuctionQueue(auctionId) {
        try {
            const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}/queue`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching priority queue', error);
            return null;
        }
    },

    async seedDemoData() {
        try {
            const response = await fetch(`${API_BASE_URL}/demo/seed`, {
                method: 'POST'
            });
            return await response.json();
        } catch (error) {
            console.error('Error seeding demo data', error);
            return { success: false, message: 'Server unreachable' };
        }
    },

    // ── Admin Analytics ──────────────────────────────────────────────────────
    async getAnalytics() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/analytics`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { error: 'Server unreachable' };
        }
    },

    async getBidsOverTime() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/analytics/bids-over-time`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return [];
        }
    },

    async getTopBidders() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/analytics/top-bidders`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return [];
        }
    },

    async getAuctionPerformance() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/analytics/auction-performance`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return [];
        }
    },

    async getAdminUsers(search = '', page = 1) {
        try {
            const params = new URLSearchParams({ search, page, per_page: 20 });
            const response = await fetch(`${API_BASE_URL}/admin/users?${params}`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { users: [], total: 0, total_pages: 1 };
        }
    },

    async getAdminUser(userId) {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/users/${userId}`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { error: 'Server unreachable' };
        }
    },

    async getRecentActivity() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/recent-activity`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return [];
        }
    },

    async getRecentAuctions() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/recent-auctions`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return [];
        }
    },

    // ── Wallet ───────────────────────────────────────────────────────────────
    async getWallet() {
        try {
            const response = await fetch(`${API_BASE_URL}/wallet/`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getWalletTransactions(page = 1, per_page = 20, type = '') {
        try {
            const params = new URLSearchParams({ page, per_page });
            if (type) params.set('type', type);
            const response = await fetch(`${API_BASE_URL}/wallet/transactions?${params}`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async initiateDeposit(amount, method = 'SIMULATED') {
        try {
            const response = await fetch(`${API_BASE_URL}/wallet/deposit/initiate`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount, method })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async confirmDeposit(idempotency_key) {
        try {
            const response = await fetch(`${API_BASE_URL}/wallet/deposit/confirm`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idempotency_key })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async createWithdrawal(amount, method = 'SIMULATED', upi_id = null) {
        try {
            const response = await fetch(`${API_BASE_URL}/wallet/withdraw`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount, method, upi_id })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getWithdrawals() {
        try {
            const response = await fetch(`${API_BASE_URL}/wallet/withdrawals`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async cancelWithdrawal(withdrawal_id) {
        try {
            const response = await fetch(`${API_BASE_URL}/wallet/withdrawals/${withdrawal_id}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    // ── Admin Wallet ─────────────────────────────────────────────────────────
    async getAdminWalletOverview() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/wallet/overview`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getAdminWalletUsers(search = '', page = 1) {
        try {
            const params = new URLSearchParams({ search, page, per_page: 20 });
            const response = await fetch(`${API_BASE_URL}/admin/wallet/users?${params}`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getAdminWalletTransactions(page = 1, filters = {}) {
        try {
            const params = new URLSearchParams({ page, per_page: 30, ...filters });
            const response = await fetch(`${API_BASE_URL}/admin/wallet/transactions?${params}`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getAdminWithdrawals(status = 'PENDING', page = 1) {
        try {
            const params = new URLSearchParams({ status, page, per_page: 20 });
            const response = await fetch(`${API_BASE_URL}/admin/wallet/withdrawals?${params}`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async approveWithdrawal(wd_id, note = '') {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/wallet/withdrawals/${wd_id}/approve`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ note })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async rejectWithdrawal(wd_id, note = '') {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/wallet/withdrawals/${wd_id}/reject`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ note })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async adminAdjustBalance(user_id, amount, direction, reason) {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/wallet/adjust`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id, amount, direction, reason })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    },

    async getAdminAuditLog(page = 1) {
        try {
            const params = new URLSearchParams({ page, per_page: 30 });
            const response = await fetch(`${API_BASE_URL}/admin/wallet/audit-log?${params}`, { credentials: 'include' });
            return await response.json();
        } catch (error) {
            return { success: false, error: 'Server unreachable' };
        }
    }
};

// Utility: format currency in INR
function formatCurrency(amount) {
    return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

// Utility: format a datetime string for display
function formatDateTime(dtStr) {
    if (!dtStr) return '';
    try {
        const dt = new Date(dtStr);
        if (isNaN(dt.getTime())) return dtStr;
        return dt.toLocaleString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: 'numeric', minute: '2-digit', hour12: true
        });
    } catch (e) {
        return dtStr;
    }
}

// Utility: get status badge class
function statusBadgeClass(status) {
    switch (status) {
        case 'ACTIVE': return 'badge-active';
        case 'UPCOMING': return 'badge-upcoming';
        case 'ENDED': return 'badge-ended';
        default: return '';
    }
}
