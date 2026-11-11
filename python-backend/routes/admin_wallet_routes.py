"""
admin_wallet_routes.py — Phase 7 Admin Wallet Management
=========================================================
All endpoints require ADMIN session role.
Every admin action is recorded in wallet_audit_log.
Admins cannot silently edit balances — every adjustment requires a reason
and creates an auditable record.
"""

from flask import Blueprint, jsonify, request, session
from routes.auth_routes import require_admin
from services import wallet_service
from database.db import get_connection
import logging

admin_wallet_bp = Blueprint('admin_wallet', __name__)
logger = logging.getLogger(__name__)


# ── GET /api/admin/wallet/overview ── System-wide wallet stats ────────────────
@admin_wallet_bp.route('/overview', methods=['GET'])
@require_admin
def wallet_overview():
    """Returns aggregate wallet statistics for the admin dashboard."""
    try:
        conn = get_connection()
        stats = conn.execute("""
            SELECT
                COUNT(*)                   AS total_wallets,
                COALESCE(SUM(balance),0)   AS total_balance,
                COALESCE(SUM(reserved),0)  AS total_reserved,
                COALESCE(MAX(balance),0)   AS max_balance,
                COALESCE(AVG(balance),0)   AS avg_balance
            FROM wallets
        """).fetchone()

        pending_wd = conn.execute("""
            SELECT COUNT(*) AS cnt, COALESCE(SUM(amount),0) AS total
            FROM withdrawal_requests WHERE status='PENDING'
        """).fetchone()

        total_deposited = conn.execute("""
            SELECT COALESCE(SUM(amount),0) FROM wallet_transactions
            WHERE type='DEPOSIT' AND status='COMPLETED'
        """).fetchone()[0]

        total_withdrawn = conn.execute("""
            SELECT COALESCE(SUM(amount),0) FROM wallet_transactions
            WHERE type='WITHDRAWAL' AND status='COMPLETED'
        """).fetchone()[0]

        pending_transactions_count = conn.execute("""
            SELECT COUNT(*) FROM wallet_transactions WHERE status='PENDING'
        """).fetchone()[0]

        total_spent = conn.execute("""
            SELECT COALESCE(SUM(amount),0) FROM wallet_transactions
            WHERE type='WIN_DEBIT' AND status='COMPLETED'
        """).fetchone()[0]

        conn.close()
        p2r = wallet_service.paise_to_rupees
        return jsonify({
            "success": True,
            "stats": {
                "total_wallets":       stats["total_wallets"],
                "total_balance":       p2r(stats["total_balance"]),
                "total_reserved":      p2r(stats["total_reserved"]),
                "total_available":     p2r(stats["total_balance"] - stats["total_reserved"]),
                "max_balance":         p2r(stats["max_balance"]),
                "avg_balance":         p2r(int(stats["avg_balance"])),
                "total_deposited":     p2r(total_deposited),
                "total_withdrawn":     p2r(total_withdrawn),
                "total_spent":         p2r(total_spent),
                "pending_transactions_count": pending_transactions_count,
                "pending_withdrawals_count": pending_wd["cnt"],
                "pending_withdrawals_total": p2r(pending_wd["total"])
            }
        })
    except Exception as e:
        logger.error(f"wallet_overview error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve wallet overview"}), 500


# ── GET /api/admin/wallet/users ── List users with wallet balances ─────────────
@admin_wallet_bp.route('/users', methods=['GET'])
@require_admin
def wallet_users():
    """Paginated list of user wallets."""
    try:
        search   = request.args.get('search', '').strip()
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 20))))
        offset   = (page - 1) * per_page

        conn = get_connection()
        p2r = wallet_service.paise_to_rupees

        base_q = """
            FROM users u
            INNER JOIN wallets w ON w.user_id = u.id
            WHERE u.role = 'USER'
        """
        params = []
        if search:
            base_q += " AND (u.username LIKE ? OR u.email LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        total = conn.execute(f"SELECT COUNT(*) {base_q}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT u.id, u.username, u.email, u.created_at, "
            f"w.balance, w.reserved, w.updated_at AS wallet_updated {base_q}"
            " ORDER BY w.balance DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

        conn.close()
        return jsonify({
            "success": True,
            "users": [{
                "id":               r["id"],
                "username":         r["username"],
                "email":            r["email"],
                "balance":          p2r(r["balance"]),
                "reserved":         p2r(r["reserved"]),
                "available":        p2r(r["balance"] - r["reserved"]),
                "wallet_updated":   r["wallet_updated"],
                "created_at":       r["created_at"]
            } for r in rows],
            "total":       total,
            "page":        page,
            "per_page":    per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)
        })
    except Exception as e:
        logger.error(f"wallet_users error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve user wallets"}), 500


# ── GET /api/admin/wallet/transactions ── All transactions (searchable) ────────
@admin_wallet_bp.route('/transactions', methods=['GET'])
@require_admin
def all_transactions():
    """Admin view of all wallet transactions with filters."""
    try:
        page      = max(1, int(request.args.get('page', 1)))
        per_page  = min(100, max(1, int(request.args.get('per_page', 30))))
        offset    = (page - 1) * per_page
        user_filter = request.args.get('user_id', None)
        type_filter = request.args.get('type', None)
        status_filter = request.args.get('status', None)

        conn = get_connection()
        p2r = wallet_service.paise_to_rupees

        where = "WHERE 1=1"
        params = []
        if user_filter:
            try:
                where += " AND wt.user_id=?"
                params.append(int(user_filter))
            except ValueError:
                pass
        if type_filter:
            where += " AND wt.type=?"
            params.append(type_filter.upper())
        if status_filter:
            where += " AND wt.status=?"
            params.append(status_filter.upper())

        total = conn.execute(
            f"SELECT COUNT(*) FROM wallet_transactions wt {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT wt.*, u.username FROM wallet_transactions wt "
            f"JOIN users u ON u.id = wt.user_id {where}"
            " ORDER BY wt.created_at DESC, wt.id DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

        conn.close()
        return jsonify({
            "success": True,
            "transactions": [{
                "id":             r["id"],
                "user_id":        r["user_id"],
                "username":       r["username"],
                "type":           r["type"],
                "amount":         p2r(r["amount"]),
                "status":         r["status"],
                "description":    r["description"],
                "reference_id":   r["reference_id"],
                "related_id":     r["related_id"],
                "created_at":     r["created_at"]
            } for r in rows],
            "total":       total,
            "page":        page,
            "per_page":    per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)
        })
    except Exception as e:
        logger.error(f"all_transactions error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve transactions"}), 500


# ── GET /api/admin/wallet/withdrawals ── List withdrawal requests ─────────────
@admin_wallet_bp.route('/withdrawals', methods=['GET'])
@require_admin
def list_withdrawals():
    """List all withdrawal requests with filter by status."""
    try:
        status_filter = request.args.get('status', 'PENDING').upper()
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 20))))
        offset   = (page - 1) * per_page
        p2r = wallet_service.paise_to_rupees

        conn = get_connection()
        valid_statuses = ('PENDING','APPROVED','REJECTED','COMPLETED','CANCELLED','ALL')
        if status_filter not in valid_statuses:
            status_filter = 'PENDING'

        where = "" if status_filter == 'ALL' else f"WHERE wr.status='{status_filter}'"
        params = []

        total = conn.execute(
            f"SELECT COUNT(*) FROM withdrawal_requests wr {where}"
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT wr.*, u.username, u.email "
            f"FROM withdrawal_requests wr JOIN users u ON u.id=wr.user_id "
            f"{where} ORDER BY wr.created_at DESC LIMIT ? OFFSET ?",
            [per_page, offset]
        ).fetchall()
        conn.close()

        return jsonify({
            "success": True,
            "withdrawals": [{
                "id":           r["id"],
                "user_id":      r["user_id"],
                "username":     r["username"],
                "email":        r["email"],
                "amount":       p2r(r["amount"]),
                "method":       r["method"],
                "upi_id":       r["upi_id"],
                "bank_account": r["bank_account"],
                "status":       r["status"],
                "admin_note":   r["admin_note"],
                "created_at":   r["created_at"],
                "updated_at":   r["updated_at"]
            } for r in rows],
            "total":       total,
            "page":        page,
            "per_page":    per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)
        })
    except Exception as e:
        logger.error(f"list_withdrawals error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve withdrawals"}), 500


# ── POST /api/admin/wallet/withdrawals/<id>/approve ── Approve withdrawal ──────
@admin_wallet_bp.route('/withdrawals/<int:wd_id>/approve', methods=['POST'])
@require_admin
def approve_withdrawal(wd_id):
    admin_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    note = str(data.get("note", "")).strip()[:500]

    result = wallet_service.admin_process_withdrawal(admin_id, wd_id, "APPROVE", note)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400


# ── POST /api/admin/wallet/withdrawals/<id>/reject ── Reject withdrawal ────────
@admin_wallet_bp.route('/withdrawals/<int:wd_id>/reject', methods=['POST'])
@require_admin
def reject_withdrawal(wd_id):
    admin_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    note = str(data.get("note", "")).strip()[:500]

    if not note:
        return jsonify({"success": False, "error": "A reason is required to reject a withdrawal"}), 400

    result = wallet_service.admin_process_withdrawal(admin_id, wd_id, "REJECT", note)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400


# ── POST /api/admin/wallet/adjust ── Manual balance adjustment ─────────────────
@admin_wallet_bp.route('/adjust', methods=['POST'])
@require_admin
def adjust_balance():
    """
    Admin balance adjustment (CREDIT or DEBIT).
    A reason is MANDATORY. Creates an auditable adjustment entry.
    Admins cannot silently edit balances.
    """
    admin_id = session["user_id"]
    data = request.get_json(silent=True) or {}

    try:
        target_user_id = int(data.get("user_id", 0))
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "user_id and amount must be numbers"}), 400

    direction = str(data.get("direction", "")).strip().upper()
    reason    = str(data.get("reason", "")).strip()

    if not target_user_id:
        return jsonify({"success": False, "error": "user_id is required"}), 400
    if not reason:
        return jsonify({"success": False, "error": "A reason is required for balance adjustments"}), 400

    result = wallet_service.admin_adjust_balance(admin_id, target_user_id, amount, direction, reason)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400


# ── GET /api/admin/wallet/audit-log ── Audit log ──────────────────────────────
@admin_wallet_bp.route('/audit-log', methods=['GET'])
@require_admin
def get_audit_log():
    """Returns recent wallet admin audit log entries."""
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 30))))
        offset   = (page - 1) * per_page

        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) FROM wallet_audit_log").fetchone()[0]
        rows = conn.execute("""
            SELECT wal.*, a.username AS admin_name, u.username AS target_name
            FROM wallet_audit_log wal
            JOIN users a ON a.id = wal.admin_id
            LEFT JOIN users u ON u.id = wal.target_user_id
            ORDER BY wal.created_at DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset)).fetchall()
        conn.close()

        return jsonify({
            "success": True,
            "audit_log": [{
                "id":           r["id"],
                "admin_id":     r["admin_id"],
                "admin_name":   r["admin_name"],
                "action":       r["action"],
                "target_user_id": r["target_user_id"],
                "target_name":  r["target_name"],
                "details":      r["details"],
                "created_at":   r["created_at"]
            } for r in rows],
            "total":       total,
            "page":        page,
            "per_page":    per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)
        })
    except Exception as e:
        logger.error(f"get_audit_log error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve audit log"}), 500


# ── GET /api/admin/wallet/users/<id> ── Single user wallet detail ─────────────
@admin_wallet_bp.route('/users/<int:user_id>', methods=['GET'])
@require_admin
def get_user_wallet(user_id):
    """Detailed wallet information for a specific user (admin only)."""
    try:
        p2r = wallet_service.paise_to_rupees
        conn = get_connection()
        user = conn.execute(
            "SELECT id, username, email FROM users WHERE id=? AND role='USER'",
            (user_id,)
        ).fetchone()
        if not user:
            conn.close()
            return jsonify({"success": False, "error": "User not found"}), 404

        wallet = conn.execute(
            "SELECT * FROM wallets WHERE user_id=?", (user_id,)
        ).fetchone()

        recent_txns = conn.execute("""
            SELECT * FROM wallet_transactions
            WHERE user_id=? ORDER BY created_at DESC LIMIT 20
        """, (user_id,)).fetchall()

        pending_wds = conn.execute("""
            SELECT * FROM withdrawal_requests
            WHERE user_id=? AND status='PENDING'
        """, (user_id,)).fetchall()

        conn.close()

        w = wallet
        return jsonify({
            "success": True,
            "user": {"id": user["id"], "username": user["username"], "email": user["email"]},
            "wallet": {
                "balance":    p2r(w["balance"]) if w else 0,
                "reserved":   p2r(w["reserved"]) if w else 0,
                "available":  p2r(w["balance"] - w["reserved"]) if w else 0,
            },
            "recent_transactions": [wallet_service._fmt_txn(r) for r in recent_txns],
            "pending_withdrawals": [{
                "id":       r["id"],
                "amount":   p2r(r["amount"]),
                "method":   r["method"],
                "status":   r["status"],
                "created_at": r["created_at"]
            } for r in pending_wds]
        })
    except Exception as e:
        logger.error(f"get_user_wallet error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve user wallet"}), 500
