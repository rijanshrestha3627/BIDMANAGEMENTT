from flask import Blueprint, jsonify, request, session
from routes.auth_routes import require_admin
from database.db import get_connection
from datetime import datetime, timedelta
import logging

admin_bp = Blueprint('admin_analytics', __name__)
logger = logging.getLogger(__name__)


def compute_status(start_time_str, end_time_str):
    """Compute auction status from start/end time strings."""
    now = datetime.now()
    try:
        start = None
        end = None
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                start = datetime.strptime(start_time_str, fmt)
                break
            except ValueError:
                continue
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                end = datetime.strptime(end_time_str, fmt)
                break
            except ValueError:
                continue
        if start is None or end is None:
            return "UNKNOWN"
        if now < start:
            return "UPCOMING"
        elif now <= end:
            return "ACTIVE"
        else:
            return "ENDED"
    except Exception:
        return "UNKNOWN"


# ============================================================
# GET /api/admin/analytics
# ============================================================
@admin_bp.route('/analytics', methods=['GET'])
@require_admin
def get_analytics():
    """
    Returns real, database-derived analytics for the admin dashboard.
    No sensitive user data is exposed.
    """
    try:
        conn = get_connection()

        # Users
        total_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'USER'"
        ).fetchone()[0]

        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        new_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'USER' AND created_at >= ?",
            (seven_days_ago,)
        ).fetchone()[0]

        # Auctions
        auctions = conn.execute(
            "SELECT id, start_time, end_time FROM auctions"
        ).fetchall()

        total_auctions = len(auctions)
        active_count = sum(1 for a in auctions if compute_status(a["start_time"], a["end_time"]) == "ACTIVE")
        upcoming_count = sum(1 for a in auctions if compute_status(a["start_time"], a["end_time"]) == "UPCOMING")
        ended_count = sum(1 for a in auctions if compute_status(a["start_time"], a["end_time"]) == "ENDED")

        # Bids
        bid_stats = conn.execute("""
            SELECT
                COUNT(*)                   AS total_bids,
                COALESCE(SUM(amount), 0)   AS total_value,
                COALESCE(MAX(amount), 0)   AS highest,
                COALESCE(AVG(amount), 0)   AS average
            FROM bids
        """).fetchone()

        conn.close()

        return jsonify({
            "users": {
                "total": total_users,
                "new_last_7_days": new_users
            },
            "auctions": {
                "total": total_auctions,
                "active": active_count,
                "upcoming": upcoming_count,
                "ended": ended_count
            },
            "bids": {
                "total": bid_stats["total_bids"],
                "total_value": round(bid_stats["total_value"], 2),
                "highest": round(bid_stats["highest"], 2),
                "average": round(bid_stats["average"], 2)
            }
        })
    except Exception as e:
        logger.error(f"get_analytics error: {e}")
        return jsonify({"error": "Failed to retrieve analytics"}), 500


# ============================================================
# GET /api/admin/analytics/bids-over-time
# ============================================================
@admin_bp.route('/analytics/bids-over-time', methods=['GET'])
@require_admin
def get_bids_over_time():
    """Returns bid counts grouped by day for the past 14 days."""
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                DATE(created_at) AS bid_date,
                COUNT(*)         AS count
            FROM bids
            WHERE created_at >= DATE('now', '-13 days')
            GROUP BY DATE(created_at)
            ORDER BY bid_date ASC
        """).fetchall()
        conn.close()

        result = []
        today = datetime.now().date()
        date_map = {row["bid_date"]: row["count"] for row in rows}
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            result.append({
                "date": d_str,
                "label": d.strftime("%d %b"),
                "count": date_map.get(d_str, 0)
            })

        return jsonify(result)
    except Exception as e:
        logger.error(f"get_bids_over_time error: {e}")
        return jsonify({"error": "Failed to retrieve bid chart data"}), 500


# ============================================================
# GET /api/admin/analytics/top-bidders
# ============================================================
@admin_bp.route('/analytics/top-bidders', methods=['GET'])
@require_admin
def get_top_bidders():
    """Returns top bidders ranked by total bids. No passwords returned."""
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                u.username,
                COUNT(b.id)          AS total_bids,
                MAX(b.amount)        AS highest_bid,
                SUM(b.amount)        AS total_amount
            FROM bids b
            JOIN users u ON b.user_id = u.id
            GROUP BY b.user_id
            ORDER BY total_bids DESC, highest_bid DESC
            LIMIT 10
        """).fetchall()
        conn.close()

        result = []
        for i, row in enumerate(rows):
            result.append({
                "rank": i + 1,
                "username": row["username"],
                "total_bids": row["total_bids"],
                "highest_bid": round(row["highest_bid"], 2),
                "total_amount": round(row["total_amount"], 2)
            })

        return jsonify(result)
    except Exception as e:
        logger.error(f"get_top_bidders error: {e}")
        return jsonify({"error": "Failed to retrieve top bidders"}), 500


# ============================================================
# GET /api/admin/analytics/auction-performance
# ============================================================
@admin_bp.route('/analytics/auction-performance', methods=['GET'])
@require_admin
def get_auction_performance():
    """Returns per-auction bid analytics."""
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                a.id,
                a.title,
                a.starting_price,
                a.current_highest_bid,
                a.start_time,
                a.end_time,
                a.image_path,
                COUNT(b.id)                AS bid_count,
                COALESCE(MAX(b.amount), 0) AS highest_bid,
                COALESCE(SUM(b.amount), 0) AS total_bid_value
            FROM auctions a
            LEFT JOIN bids b ON b.auction_id = a.id
            GROUP BY a.id
            ORDER BY bid_count DESC
            LIMIT 10
        """).fetchall()
        conn.close()

        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "title": row["title"],
                "status": compute_status(row["start_time"], row["end_time"]),
                "starting_price": row["starting_price"],
                "current_highest_bid": row["current_highest_bid"],
                "bid_count": row["bid_count"],
                "highest_bid": round(row["highest_bid"], 2),
                "total_bid_value": round(row["total_bid_value"], 2),
                "image_path": row["image_path"]
            })

        return jsonify(result)
    except Exception as e:
        logger.error(f"get_auction_performance error: {e}")
        return jsonify({"error": "Failed to retrieve auction performance"}), 500


# ============================================================
# GET /api/admin/users  — paginated, searchable user list
# ============================================================
@admin_bp.route('/users', methods=['GET'])
@require_admin
def get_users():
    """
    Returns paginated, searchable list of all users.
    Never exposes password_hash, OTP, or session secrets.
    """
    try:
        search = request.args.get('search', '').strip()
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 20))))
        offset = (page - 1) * per_page

        conn = get_connection()

        if search:
            pattern = f"%{search}%"
            total = conn.execute(
                "SELECT COUNT(*) FROM users WHERE username LIKE ? OR email LIKE ?",
                (pattern, pattern)
            ).fetchone()[0]
            rows = conn.execute("""
                SELECT
                    u.id, u.username, u.email, u.role, u.email_verified, u.created_at,
                    COUNT(b.id) AS total_bids
                FROM users u
                LEFT JOIN bids b ON b.user_id = u.id
                WHERE u.username LIKE ? OR u.email LIKE ?
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT ? OFFSET ?
            """, (pattern, pattern, per_page, offset)).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            rows = conn.execute("""
                SELECT
                    u.id, u.username, u.email, u.role, u.email_verified, u.created_at,
                    COUNT(b.id) AS total_bids
                FROM users u
                LEFT JOIN bids b ON b.user_id = u.id
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset)).fetchall()

        conn.close()

        users = []
        for row in rows:
            users.append({
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role": row["role"],
                "email_verified": bool(row["email_verified"]),
                "created_at": row["created_at"],
                "total_bids": row["total_bids"]
            })

        return jsonify({
            "users": users,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)
        })
    except Exception as e:
        logger.error(f"get_users error: {e}")
        return jsonify({"error": "Failed to retrieve users"}), 500


# ============================================================
# GET /api/admin/users/<id>  — safe user detail view
# ============================================================
@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@require_admin
def get_user_detail(user_id):
    """
    Returns safe account information for a specific user.
    Never exposes password_hash, OTP data, or session secrets.
    """
    try:
        conn = get_connection()
        user = conn.execute(
            "SELECT id, username, email, role, email_verified, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            conn.close()
            return jsonify({"error": "User not found"}), 404

        stats = conn.execute("""
            SELECT
                COUNT(b.id)                          AS total_bids,
                COALESCE(SUM(b.amount), 0)           AS total_amount,
                COALESCE(MAX(b.amount), 0)           AS highest_bid,
                COUNT(DISTINCT b.auction_id)         AS auctions_participated
            FROM bids b
            WHERE b.user_id = ?
        """, (user_id,)).fetchone()

        conn.close()

        return jsonify({
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "email_verified": bool(user["email_verified"]),
            "created_at": user["created_at"],
            "stats": {
                "total_bids": stats["total_bids"],
                "total_amount": round(stats["total_amount"], 2),
                "highest_bid": round(stats["highest_bid"], 2),
                "auctions_participated": stats["auctions_participated"]
            }
        })
    except Exception as e:
        logger.error(f"get_user_detail error: {e}")
        return jsonify({"error": "Failed to retrieve user details"}), 500


# ============================================================
# GET /api/admin/recent-activity
# ============================================================
@admin_bp.route('/recent-activity', methods=['GET'])
@require_admin
def get_recent_activity():
    """Returns real recent events derived from existing database data."""
    try:
        conn = get_connection()
        events = []

        new_users = conn.execute("""
            SELECT username, created_at FROM users
            WHERE role = 'USER'
            ORDER BY created_at DESC LIMIT 5
        """).fetchall()
        for u in new_users:
            events.append({
                "type": "user_registered",
                "icon": "person",
                "message": f"New user registered: {u['username']}",
                "time": u["created_at"]
            })

        recent_bids = conn.execute("""
            SELECT b.bidder_name, b.amount, b.created_at, a.title
            FROM bids b
            JOIN auctions a ON b.auction_id = a.id
            ORDER BY b.created_at DESC LIMIT 8
        """).fetchall()
        for b in recent_bids:
            events.append({
                "type": "bid_placed",
                "icon": "gavel",
                "message": f"{b['bidder_name']} bid \u20b9{b['amount']:,.0f} on \"{b['title']}\"",
                "time": b["created_at"]
            })

        recent_auctions = conn.execute("""
            SELECT title, created_at FROM auctions
            ORDER BY created_at DESC LIMIT 5
        """).fetchall()
        for a in recent_auctions:
            events.append({
                "type": "auction_created",
                "icon": "add_circle",
                "message": f"Auction created: \"{a['title']}\"",
                "time": a["created_at"]
            })

        conn.close()

        def parse_time(ev):
            t = ev.get("time", "")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
                try:
                    return datetime.strptime(t, fmt)
                except ValueError:
                    continue
            return datetime.min

        events.sort(key=parse_time, reverse=True)
        return jsonify(events[:15])
    except Exception as e:
        logger.error(f"get_recent_activity error: {e}")
        return jsonify({"error": "Failed to retrieve recent activity"}), 500


# ============================================================
# GET /api/admin/recent-auctions
# ============================================================
@admin_bp.route('/recent-auctions', methods=['GET'])
@require_admin
def get_recent_auctions():
    """Returns recent auctions with bid counts for the admin dashboard."""
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                a.id, a.title, a.starting_price, a.current_highest_bid,
                a.start_time, a.end_time, a.image_path, a.created_at,
                COUNT(b.id) AS bid_count
            FROM auctions a
            LEFT JOIN bids b ON b.auction_id = a.id
            GROUP BY a.id
            ORDER BY a.created_at DESC
            LIMIT 8
        """).fetchall()
        conn.close()

        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "title": row["title"],
                "status": compute_status(row["start_time"], row["end_time"]),
                "starting_price": row["starting_price"],
                "current_highest_bid": row["current_highest_bid"],
                "bid_count": row["bid_count"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "image_path": row["image_path"],
                "created_at": row["created_at"]
            })

        return jsonify(result)
    except Exception as e:
        logger.error(f"get_recent_auctions error: {e}")
        return jsonify({"error": "Failed to retrieve recent auctions"}), 500
