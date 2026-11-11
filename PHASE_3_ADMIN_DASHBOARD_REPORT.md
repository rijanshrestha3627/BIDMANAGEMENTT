# PHASE 3 — Admin Dashboard, Admin Management & Analytics

## Overview

Phase 3 adds a complete, data-driven Admin Dashboard to the University Auction Bid Management System. All existing Phase 1 and Phase 2 functionality is preserved.

---

## Files Changed

| File | Change |
|------|--------|
| `python-backend/routes/admin_routes.py` | **NEW** — all analytics + user-management API endpoints |
| `python-backend/app.py` | Register `admin_bp` at `/api/admin` |
| `frontend/admin.html` | Complete rewrite — tabbed dashboard with stats, charts, tables |
| `frontend/css/admin-dashboard.css` | **NEW** — dashboard styles extending existing design system |
| `frontend/js/admin.js` | Complete rewrite — dashboard logic, charts, user management |
| `frontend/js/api.js` | Added `credentials:include` to all admin calls + 8 new admin API methods |

---

## New API Endpoints

All endpoints require `ADMIN` session. Unauthenticated requests receive **403 Forbidden**.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/analytics` | Overall stats: users, auctions, bids |
| `GET` | `/api/admin/analytics/bids-over-time` | 14-day bid count chart data |
| `GET` | `/api/admin/analytics/top-bidders` | Top 10 bidders by total bids |
| `GET` | `/api/admin/analytics/auction-performance` | Per-auction bid statistics |
| `GET` | `/api/admin/users` | Paginated, searchable user list |
| `GET` | `/api/admin/users/<id>` | Safe user detail (no password/hash) |
| `GET` | `/api/admin/recent-activity` | Activity feed from real DB events |
| `GET` | `/api/admin/recent-auctions` | Last 8 auctions with bid counts |

---

## Dashboard Features

### Tab 1: Overview

- **9 statistics cards** — Total Users, Total Auctions, Total Bids, Active, Upcoming, Ended, Total Bid Value, Highest Bid, Average Bid
- **Bid Activity Chart** — SVG bar chart, 14 days of real data, zero-filled days shown
- **Auction Status Distribution** — horizontal bar chart (Active / Upcoming / Ended)
- **Top Bidders Table** — Rank, Username, Total Bids, Highest Bid, Total Amount (real SQL aggregation)
- **Recent Activity Feed** — ordered events: registrations + bids + auction creations
- **Recent Auctions** — last 8 auctions with thumbnail, status badge, bid count

### Tab 2: Auction Management

- **Create Auction** form (preserved from Phase 1)
- **Filter tabs** — All / Active / Upcoming / Ended
- **Manage Auctions** list — Edit, Start, End, Delete, View buttons (all existing endpoints)
- Edit modal preserved with image upload support

### Tab 3: User Management

- **Searchable user table** — ID, Username, Email, Role, Bids, Verified, Registered
- **Search** by username or email (server-side `LIKE` query)
- **Pagination** — 20 per page with ellipsis navigation
- **User Detail Modal** — safe fields only (no password hash, no OTP)
  - Username, Email, Role, Verified, Registered
  - Total Bids, Highest Bid, Total Amount, Auctions Participated

### Tab 4: Analytics

- **Auction Performance Table** — Title, Status, Starting Price, Highest Bid, Total Bids, Total Value
- **Bid Analytics summary** — Total, Value, Highest, Average (same live data as Overview)

---

## Statistics Calculations

All values are computed directly from SQLite using SQL aggregates — no hardcoding.

```sql
-- Auction status counts computed in Python via compute_status()
SELECT COUNT(*) AS total_bids,
       COALESCE(SUM(amount), 0)  AS total_value,
       COALESCE(MAX(amount), 0)  AS highest,
       COALESCE(AVG(amount), 0)  AS average
FROM bids;
```

```sql
-- Top bidders
SELECT u.username, COUNT(b.id), MAX(b.amount), SUM(b.amount)
FROM bids b JOIN users u ON b.user_id = u.id
GROUP BY b.user_id ORDER BY COUNT(b.id) DESC LIMIT 10;
```

```sql
-- 14-day chart
SELECT DATE(created_at) AS bid_date, COUNT(*) AS count
FROM bids WHERE created_at >= DATE('now', '-13 days')
GROUP BY DATE(created_at);
```

---

## Security

- Every admin endpoint uses `@require_admin` decorator (server-side session check)
- `require_admin` checks `session["role"] == "ADMIN"` — cannot be spoofed from the client
- Unauthenticated: **403 Forbidden**
- Unrecognised session: **403 Forbidden**
- No sensitive fields ever returned: no `password_hash`, no `otp_hash`, no session tokens
- Frontend guard added in `admin.js` (redirects non-admin to login page — defense-in-depth)

---

## Testing Performed

### A. Authentication
- ✅ Admin login → dashboard loads with real data
- ✅ Logout clears session

### B. Authorization (automated)
```
Unauthenticated analytics: HTTP 403 (expected 403: PASS)
Unauthenticated users: HTTP 403 (expected 403: PASS)
Health endpoint: OK
```

### C. Statistics
- All values derived from real SQLite rows
- Empty database returns 0 for all counters

### D. Existing functionality preserved
- ✅ Create Auction (POST /api/admin/auctions)
- ✅ Edit Auction (PUT /api/admin/auctions/<id>)
- ✅ Delete Ended Auction (DELETE /api/admin/auctions/<id>)
- ✅ Force Start / Force End
- ✅ Product image upload
- ✅ Java PriorityQueue untouched
- ✅ Flask sessions unchanged
- ✅ User registration / login / profile

### E. Responsive Design
- Stats cards: grid wraps to 2-column on mobile
- Tables: horizontally scrollable on small screens
- Charts: SVG with viewBox (scales with container)
- Tab bar: wraps on mobile

---

## How to Run

### 1. Start Java Engine
```bash
cd java-engine
java -jar bin/AuctionEngine.jar
# or
java -cp bin AuctionServer
```

### 2. Start Flask Backend
```bash
cd python-backend
pip install -r requirements.txt
python app.py
# Starts at http://localhost:5000
```

### 3. Serve Frontend
```bash
# Use VS Code Live Server or any static server on port 5500
# Open http://localhost:5500/frontend/admin.html
# Or open http://localhost:5500/frontend/admin-login.html first
```

### Default Admin Credentials
```
Email:    admin@example.com
Password: admin123
```

---

## Architecture Notes

- **No duplicate endpoints** — auction CRUD reuses existing `/api/admin/auctions/*`
- **No fake data** — all stats from real SQLite queries
- **No Java engine changes** — PriorityQueue and ReentrantLock untouched
- **No OTP/email changes** — deferred per Phase 3 spec
- **Lightweight chart** — pure SVG bar chart, no external chart library required

---

## Remaining / Known Issues

- OTP/email verification is intentionally deferred (Phase 4)
- Java engine shows `offline` when not running (graceful degradation — existing behaviour)
- Bid activity chart date labels may overlap if screen is very narrow (design tradeoff for density)
