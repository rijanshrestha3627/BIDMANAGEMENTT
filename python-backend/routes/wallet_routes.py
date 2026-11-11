"""
wallet_routes.py — Phase 7 Wallet API Endpoints
================================================
All endpoints require an authenticated session.
No wallet amount or user ID is accepted from the client;
all values are server-side only.
"""

from flask import Blueprint, jsonify, request, session
from routes.auth_routes import require_user
from services import wallet_service
from database.db import get_connection
import logging

wallet_bp = Blueprint('wallet', __name__)
logger = logging.getLogger(__name__)


# ── GET /api/wallet ── Balance summary ────────────────────────────────────────
@wallet_bp.route('/', methods=['GET'])
@require_user
def get_wallet():
    user_id = session["user_id"]
    try:
        summary = wallet_service.get_wallet_summary(user_id)
        return jsonify({"success": True, "wallet": summary})
    except Exception as e:
        logger.error(f"get_wallet error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve wallet"}), 500


# ── GET /api/wallet/transactions ── Transaction history ───────────────────────
@wallet_bp.route('/transactions', methods=['GET'])
@require_user
def get_transactions():
    user_id = session["user_id"]
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 20))))
        txn_type = request.args.get('type', None)
        result = wallet_service.get_transaction_history(user_id, page, per_page, txn_type)
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.error(f"get_transactions error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve transactions"}), 500


# ── POST /api/wallet/deposit/initiate ── Start simulated deposit ──────────────
@wallet_bp.route('/deposit/initiate', methods=['POST'])
@require_user
def initiate_deposit():
    """
    Step 1 of the 2-step simulated deposit flow.
    Returns an idempotency key for server-side confirmation.
    ⚠️  SIMULATED PAYMENT — no real money is processed.
    """
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}

    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Amount must be a number"}), 400

    if amount <= 0:
        return jsonify({"success": False, "error": "Amount must be positive"}), 400

    method = str(data.get("method", "SIMULATED")).upper()
    if method not in ("SIMULATED", "CARD", "UPI", "NETBANKING"):
        method = "SIMULATED"

    result = wallet_service.initiate_deposit(user_id, amount, method)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400


# ── POST /api/wallet/deposit/confirm ── Confirm simulated deposit ─────────────
@wallet_bp.route('/deposit/confirm', methods=['POST'])
@require_user
def confirm_deposit():
    """
    Step 2 of the simulated deposit flow.
    Idempotent — safe to call twice with same key.
    ⚠️  SIMULATED PAYMENT — no real money is processed.
    """
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}

    idempotency_key = str(data.get("idempotency_key", "")).strip()
    if not idempotency_key:
        return jsonify({"success": False, "error": "idempotency_key is required"}), 400

    result = wallet_service.confirm_deposit(user_id, idempotency_key)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400


# ── POST /api/wallet/withdraw ── Create withdrawal request ────────────────────
@wallet_bp.route('/withdraw', methods=['POST'])
@require_user
def create_withdrawal():
    """
    Create a simulated withdrawal request.
    Funds are reserved immediately; actual processing requires admin approval.
    ⚠️  SIMULATED — no real bank/UPI transfer occurs.
    """
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}

    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Amount must be a number"}), 400

    if amount <= 0:
        return jsonify({"success": False, "error": "Amount must be positive"}), 400

    method = str(data.get("method", "SIMULATED")).strip().upper()
    if method not in ("SIMULATED", "UPI", "BANK"):
        method = "SIMULATED"

    # Sanitize optional fields — never trust client data
    upi_id = str(data.get("upi_id", "") or "").strip()[:100] or None
    bank_account = str(data.get("bank_account", "") or "").strip()[:100] or None

    # Never store sensitive info like PINs or passwords
    result = wallet_service.create_withdrawal_request(
        user_id, amount, method, upi_id, bank_account
    )
    if result.get("success"):
        return jsonify(result), 201
    return jsonify(result), 400


# ── GET /api/wallet/withdrawals ── List user's withdrawal requests ─────────────
@wallet_bp.route('/withdrawals', methods=['GET'])
@require_user
def list_withdrawals():
    user_id = session["user_id"]
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT id, amount, method, upi_id, bank_account,
                   status, admin_note, created_at, updated_at
            FROM withdrawal_requests
            WHERE user_id=?
            ORDER BY created_at DESC
            LIMIT 50
        """, (user_id,)).fetchall()
        conn.close()
        return jsonify({
            "success": True,
            "withdrawals": [{
                "id":           r["id"],
                "amount":       wallet_service.paise_to_rupees(r["amount"]),
                "method":       r["method"],
                "upi_id":       r["upi_id"],
                "bank_account": r["bank_account"],
                "status":       r["status"],
                "admin_note":   r["admin_note"],
                "created_at":   r["created_at"],
                "updated_at":   r["updated_at"]
            } for r in rows]
        })
    except Exception as e:
        logger.error(f"list_withdrawals error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve withdrawals"}), 500


# ── DELETE /api/wallet/withdrawals/<id> ── Cancel pending withdrawal ──────────
@wallet_bp.route('/withdrawals/<int:withdrawal_id>', methods=['DELETE'])
@require_user
def cancel_withdrawal(withdrawal_id):
    user_id = session["user_id"]
    result = wallet_service.cancel_withdrawal_request(user_id, withdrawal_id)
    if result.get("success"):
        return jsonify(result), 200
    return jsonify(result), 400
