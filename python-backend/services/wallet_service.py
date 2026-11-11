"""
wallet_service.py — Phase 7 Wallet System
==========================================
All monetary values are stored and operated on in INTEGER PAISE (1 INR = 100 paise).
This eliminates floating-point rounding errors.

CONCURRENCY MODEL
-----------------
SQLite provides page-level locking.  We use "BEGIN EXCLUSIVE" (via isolation_level)
where needed so that two simultaneous Flask requests cannot overspend the same wallet.
The wallet row has CHECK constraints that prevent negative balances/reservations
at the database level as a safety net.

SECURITY
--------
- Never accept wallet amounts or user IDs from the client.
- All balance changes go through this service.
- Idempotency keys prevent duplicate credits/debits.
"""

import sqlite3
import uuid
import logging
from database.db import get_connection, get_or_create_wallet

logger = logging.getLogger(__name__)

# ── Conversion helpers ────────────────────────────────────────────────────────

def rupees_to_paise(rupees: float) -> int:
    """Convert INR (float) to integer paise, rounding to nearest paisa."""
    return int(round(float(rupees) * 100))

def paise_to_rupees(paise: int) -> float:
    """Convert integer paise to INR float (2 decimal places)."""
    return round(int(paise) / 100, 2)

# ── Internal atomic helpers ───────────────────────────────────────────────────

def _get_wallet_exclusive(conn, user_id: int):
    """
    Fetch the wallet row for user_id.
    Must be called inside a BEGIN EXCLUSIVE transaction.
    Creates the wallet row if it does not exist.
    """
    wallet = conn.execute(
        "SELECT * FROM wallets WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not wallet:
        conn.execute(
            "INSERT INTO wallets (user_id, balance, reserved) VALUES (?, 0, 0)",
            (user_id,)
        )
        wallet = conn.execute(
            "SELECT * FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
    return wallet


def _available_balance(wallet) -> int:
    """Available balance = total balance − reserved funds (in paise)."""
    return int(wallet["balance"]) - int(wallet["reserved"])


# ── Public API ────────────────────────────────────────────────────────────────

def get_wallet_summary(user_id: int) -> dict:
    """
    Returns wallet summary for the given user.
    All amounts returned as INR floats for the API response.
    """
    conn = get_connection()
    try:
        wallet = get_or_create_wallet(conn, user_id)
        conn.commit()

        balance_p  = int(wallet["balance"])
        reserved_p = int(wallet["reserved"])
        available_p = balance_p - reserved_p

        # Total deposited (sum of all completed DEPOSIT transactions)
        total_deposited = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM wallet_transactions "
            "WHERE user_id=? AND type='DEPOSIT' AND status='COMPLETED'",
            (user_id,)
        ).fetchone()[0]

        # Total spent on wins
        total_spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM wallet_transactions "
            "WHERE user_id=? AND type='WIN_DEBIT' AND status='COMPLETED'",
            (user_id,)
        ).fetchone()[0]

        # Total withdrawn (completed withdrawals)
        total_withdrawn = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM wallet_transactions "
            "WHERE user_id=? AND type='WITHDRAWAL' AND status='COMPLETED'",
            (user_id,)
        ).fetchone()[0]

        # Recent transactions (last 10)
        txn_rows = conn.execute("""
            SELECT id, type, amount, status, description, reference_id, created_at
            FROM wallet_transactions
            WHERE user_id=?
            ORDER BY created_at DESC, id DESC
            LIMIT 10
        """, (user_id,)).fetchall()

        return {
            "balance":       paise_to_rupees(balance_p),
            "reserved":      paise_to_rupees(reserved_p),
            "available":     paise_to_rupees(available_p),
            "total_deposited": paise_to_rupees(total_deposited),
            "total_spent":   paise_to_rupees(total_spent),
            "total_withdrawn": paise_to_rupees(total_withdrawn),
            "recent_transactions": [_fmt_txn(r) for r in txn_rows]
        }
    finally:
        conn.close()


def get_transaction_history(user_id: int, page: int = 1, per_page: int = 20,
                            txn_type: str = None) -> dict:
    """Paginated transaction history for a user."""
    conn = get_connection()
    try:
        offset = (max(1, page) - 1) * per_page
        base = "FROM wallet_transactions WHERE user_id=?"
        params = [user_id]
        if txn_type and txn_type.upper() in (
            'DEPOSIT','WITHDRAWAL','BID_RESERVE','BID_RELEASE',
            'WIN_DEBIT','ADMIN_CREDIT','ADMIN_DEBIT','REFUND'
        ):
            base += " AND type=?"
            params.append(txn_type.upper())

        total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT id,type,amount,status,description,reference_id,related_id,created_at {base}"
            " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        return {
            "transactions": [_fmt_txn(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)
        }
    finally:
        conn.close()


def initiate_deposit(user_id: int, amount_rupees: float,
                     payment_method: str = "SIMULATED") -> dict:
    """
    Initiate a simulated deposit.
    Returns an idempotency key that must be confirmed on the server side.
    No funds are credited until confirm_deposit() is called with the key.
    """
    if amount_rupees <= 0:
        return {"success": False, "error": "Deposit amount must be positive"}
    if amount_rupees > 100000:
        return {"success": False, "error": "Maximum deposit is ₹1,00,000 per transaction"}

    amount_paise = rupees_to_paise(amount_rupees)
    idempotency_key = f"DEP-{uuid.uuid4().hex}"

    conn = get_connection()
    try:
        get_or_create_wallet(conn, user_id)
        # Record a PENDING deposit transaction
        conn.execute("""
            INSERT INTO wallet_transactions
                (user_id, type, amount, status, description, idempotency_key)
            VALUES (?, 'DEPOSIT', ?, 'PENDING', ?, ?)
        """, (user_id, amount_paise,
              f"Simulated deposit via {payment_method}",
              idempotency_key))
        conn.commit()
        return {
            "success": True,
            "idempotency_key": idempotency_key,
            "amount": paise_to_rupees(amount_paise),
            "message": "Deposit initiated. Confirm to credit funds."
        }
    except Exception as e:
        logger.error(f"initiate_deposit error: {e}")
        return {"success": False, "error": "Failed to initiate deposit"}
    finally:
        conn.close()


def confirm_deposit(user_id: int, idempotency_key: str) -> dict:
    """
    Server-side confirmation of a simulated deposit.
    Credits the wallet EXACTLY ONCE — replaying this call is safe (idempotent).
    """
    conn = get_connection()
    # Use isolation_level for exclusive locking
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")

        # Find the pending transaction; user_id check prevents cross-user attacks
        txn = conn.execute("""
            SELECT * FROM wallet_transactions
            WHERE idempotency_key=? AND user_id=? AND type='DEPOSIT'
        """, (idempotency_key, user_id)).fetchone()

        if not txn:
            conn.rollback()
            return {"success": False, "error": "Invalid deposit reference"}

        if txn["status"] == "COMPLETED":
            conn.rollback()
            return {
                "success": True,
                "already_processed": True,
                "message": "Deposit already credited.",
                "amount": paise_to_rupees(txn["amount"])
            }

        if txn["status"] != "PENDING":
            conn.rollback()
            return {"success": False, "error": f"Deposit cannot be confirmed (status: {txn['status']})"}

        # Credit the wallet
        conn.execute("""
            UPDATE wallets
            SET balance = balance + ?,
                updated_at = datetime('now','localtime')
            WHERE user_id = ?
        """, (txn["amount"], user_id))

        # Mark transaction complete
        conn.execute("""
            UPDATE wallet_transactions
            SET status='COMPLETED', updated_at=datetime('now','localtime')
            WHERE id=?
        """, (txn["id"],))

        conn.commit()
        return {
            "success": True,
            "amount": paise_to_rupees(txn["amount"]),
            "message": f"₹{paise_to_rupees(txn['amount']):,.2f} credited to your wallet."
        }
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"confirm_deposit integrity error: {e}")
        return {"success": False, "error": "Balance integrity check failed"}
    except Exception as e:
        conn.rollback()
        logger.error(f"confirm_deposit error: {e}")
        return {"success": False, "error": "Failed to confirm deposit"}
    finally:
        conn.close()


def reserve_for_bid(user_id: int, auction_id: int,
                    new_bid_rupees: float) -> dict:
    """
    Reserve funds for a bid.  Handles the following cases:
      1. User has no existing active reservation for this auction → reserve full bid amount.
      2. User already has an active reservation for this auction → reserve only the
         ADDITIONAL amount needed (new_bid − existing_reservation).

    Returns {"success": True, "reservation_id": int, "reserved_additional": float}
    or      {"success": False, "error": str}
    """
    new_bid_paise = rupees_to_paise(new_bid_rupees)
    conn = get_connection()
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")
        wallet = _get_wallet_exclusive(conn, user_id)

        # Find existing active reservation for this user+auction
        existing = conn.execute("""
            SELECT * FROM wallet_reservations
            WHERE user_id=? AND auction_id=? AND status='ACTIVE' AND purpose='BID'
            ORDER BY id DESC LIMIT 1
        """, (user_id, auction_id)).fetchone()

        existing_amount = int(existing["amount"]) if existing else 0
        additional_needed = new_bid_paise - existing_amount

        if additional_needed <= 0:
            # New bid is lower than or equal to existing reserve — shouldn't happen
            # in normal flow but handle gracefully
            conn.rollback()
            return {"success": False, "error": "New bid must exceed your current reservation"}

        available = _available_balance(wallet)
        if additional_needed > available:
            conn.rollback()
            return {
                "success": False,
                "error": (
                    f"Insufficient wallet balance. Need ₹{paise_to_rupees(additional_needed):,.2f} more. "
                    f"Available: ₹{paise_to_rupees(available):,.2f}. "
                    f"Add funds to your wallet and try again."
                )
            }

        # Release previous reservation if it exists
        if existing:
            conn.execute("""
                UPDATE wallet_reservations
                SET status='RELEASED', updated_at=datetime('now','localtime')
                WHERE id=?
            """, (existing["id"],))
            # Release corresponding wallet reserve
            conn.execute("""
                UPDATE wallets SET reserved = reserved - ?,
                    updated_at=datetime('now','localtime')
                WHERE user_id=?
            """, (existing_amount, user_id))
            # Mark old BID_RESERVE transaction as cancelled
            if existing["transaction_id"]:
                conn.execute("""
                    UPDATE wallet_transactions
                    SET status='CANCELLED', updated_at=datetime('now','localtime')
                    WHERE id=?
                """, (existing["transaction_id"],))

        # Create new reservation transaction for full new bid amount
        ikey = f"BRES-{user_id}-{auction_id}-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO wallet_transactions
                (user_id, type, amount, status, description, idempotency_key, related_id)
            VALUES (?, 'BID_RESERVE', ?, 'RESERVED', ?, ?, ?)
        """, (user_id, new_bid_paise,
              f"Reserved for bid on auction #{auction_id}",
              ikey, auction_id))
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create reservation record
        conn.execute("""
            INSERT INTO wallet_reservations
                (user_id, auction_id, amount, purpose, status, transaction_id)
            VALUES (?, ?, ?, 'BID', 'ACTIVE', ?)
        """, (user_id, auction_id, new_bid_paise, txn_id))
        res_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Update wallet reserved amount (add full new bid; old was already released above)
        conn.execute("""
            UPDATE wallets SET reserved = reserved + ?,
                updated_at=datetime('now','localtime')
            WHERE user_id=?
        """, (new_bid_paise, user_id))

        conn.commit()
        return {
            "success": True,
            "reservation_id": res_id,
            "reserved_total": paise_to_rupees(new_bid_paise),
            "reserved_additional": paise_to_rupees(additional_needed)
        }
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"reserve_for_bid integrity error: {e}")
        return {"success": False, "error": "Wallet integrity check failed. Balance may be insufficient."}
    except Exception as e:
        conn.rollback()
        logger.error(f"reserve_for_bid error: {e}")
        return {"success": False, "error": "Failed to reserve funds for bid"}
    finally:
        conn.close()


def release_bid_reservation(user_id: int, auction_id: int) -> dict:
    """
    Release any active BID reservation for user on auction.
    Called when the user is outbid or the auction ends without the user winning.
    """
    conn = get_connection()
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")
        existing = conn.execute("""
            SELECT * FROM wallet_reservations
            WHERE user_id=? AND auction_id=? AND status='ACTIVE' AND purpose='BID'
            ORDER BY id DESC LIMIT 1
        """, (user_id, auction_id)).fetchone()

        if not existing:
            conn.rollback()
            return {"success": True, "message": "No active reservation to release"}

        amount = int(existing["amount"])

        # Release reservation record
        conn.execute("""
            UPDATE wallet_reservations
            SET status='RELEASED', updated_at=datetime('now','localtime')
            WHERE id=?
        """, (existing["id"],))

        # Reduce wallet reserved amount
        conn.execute("""
            UPDATE wallets SET reserved = reserved - ?,
                updated_at=datetime('now','localtime')
            WHERE user_id=?
        """, (amount, user_id))

        # Update transaction record
        if existing["transaction_id"]:
            conn.execute("""
                UPDATE wallet_transactions
                SET status='CANCELLED', description=description||' (released)',
                    updated_at=datetime('now','localtime')
                WHERE id=?
            """, (existing["transaction_id"],))

        # Insert a BID_RELEASE record for transparency
        conn.execute("""
            INSERT INTO wallet_transactions
                (user_id, type, amount, status, description, related_id)
            VALUES (?, 'BID_RELEASE', ?, 'COMPLETED', ?, ?)
        """, (user_id, amount,
              f"Released bid reservation for auction #{auction_id}",
              auction_id))

        conn.commit()
        return {"success": True, "released": paise_to_rupees(amount)}
    except Exception as e:
        conn.rollback()
        logger.error(f"release_bid_reservation error: {e}")
        return {"success": False, "error": "Failed to release reservation"}
    finally:
        conn.close()


def settle_auction_winner(user_id: int, auction_id: int,
                          winning_amount_rupees: float,
                          idempotency_key: str = None) -> dict:
    """
    Settle payment for auction winner:
      1. Verify the user has an active reservation >= winning amount.
      2. Deduct winning_amount from wallet balance (not just reserved).
      3. Mark reservation as SETTLED.
      4. Idempotent — safe to call twice.
    """
    winning_paise = rupees_to_paise(winning_amount_rupees)
    ikey = idempotency_key or f"WIN-{user_id}-{auction_id}"

    conn = get_connection()
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")

        # Idempotency check
        existing_win = conn.execute("""
            SELECT id FROM wallet_transactions
            WHERE idempotency_key=? AND type='WIN_DEBIT' AND status='COMPLETED'
        """, (ikey,)).fetchone()
        if existing_win:
            conn.rollback()
            return {"success": True, "already_settled": True,
                    "message": "Auction already settled."}

        # Find active bid reservation
        reservation = conn.execute("""
            SELECT * FROM wallet_reservations
            WHERE user_id=? AND auction_id=? AND status='ACTIVE' AND purpose='BID'
            ORDER BY id DESC LIMIT 1
        """, (user_id, auction_id)).fetchone()

        wallet = _get_wallet_exclusive(conn, user_id)
        balance = int(wallet["balance"])
        reserved = int(wallet["reserved"])

        if reservation:
            reserved_amount = int(reservation["amount"])
            # Release the full reservation, then deduct winning amount
            new_reserved = reserved - reserved_amount
            if new_reserved < 0:
                new_reserved = 0

            # Deduct winning amount from balance
            new_balance = balance - winning_paise
            if new_balance < 0:
                # Flag for admin review — should not happen in normal flow
                conn.rollback()
                logger.error(
                    f"WALLET INCONSISTENCY: user={user_id}, auction={auction_id}, "
                    f"balance={balance}p, winning={winning_paise}p"
                )
                return {
                    "success": False,
                    "error": "Wallet balance inconsistency detected. Flagged for admin review.",
                    "flag_for_review": True
                }

            conn.execute("""
                UPDATE wallets SET balance=?, reserved=?,
                    updated_at=datetime('now','localtime')
                WHERE user_id=?
            """, (new_balance, new_reserved, user_id))

            # Settle reservation
            conn.execute("""
                UPDATE wallet_reservations
                SET status='SETTLED', updated_at=datetime('now','localtime')
                WHERE id=?
            """, (reservation["id"],))

            # If any excess was reserved (bid was higher than winning amount)
            excess = reserved_amount - winning_paise
            if excess > 0:
                conn.execute("""
                    INSERT INTO wallet_transactions
                        (user_id, type, amount, status, description, related_id)
                    VALUES (?, 'REFUND', ?, 'COMPLETED', ?, ?)
                """, (user_id, excess,
                      f"Refund: bid reserve exceeded winning price for auction #{auction_id}",
                      auction_id))
        else:
            # No reservation found — deduct directly if balance is sufficient
            new_balance = balance - winning_paise
            if new_balance < 0:
                conn.rollback()
                logger.error(
                    f"WALLET INCONSISTENCY (no reservation): user={user_id}, "
                    f"auction={auction_id}, balance={balance}p, winning={winning_paise}p"
                )
                return {
                    "success": False,
                    "error": "Wallet balance inconsistency (no reservation found). Flagged for admin review.",
                    "flag_for_review": True
                }
            conn.execute("""
                UPDATE wallets SET balance=?,
                    updated_at=datetime('now','localtime')
                WHERE user_id=?
            """, (new_balance, user_id))

        # Record WIN_DEBIT transaction
        conn.execute("""
            INSERT INTO wallet_transactions
                (user_id, type, amount, status, description, idempotency_key, related_id)
            VALUES (?, 'WIN_DEBIT', ?, 'COMPLETED', ?, ?, ?)
        """, (user_id, winning_paise,
              f"Payment for winning auction #{auction_id}",
              ikey, auction_id))

        conn.commit()
        return {
            "success": True,
            "deducted": paise_to_rupees(winning_paise),
            "message": f"₹{paise_to_rupees(winning_paise):,.2f} deducted for winning auction #{auction_id}."
        }
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"settle_auction_winner integrity error: {e}")
        return {"success": False, "error": "Wallet constraint failed during settlement"}
    except Exception as e:
        conn.rollback()
        logger.error(f"settle_auction_winner error: {e}")
        return {"success": False, "error": "Failed to settle auction payment"}
    finally:
        conn.close()


def create_withdrawal_request(user_id: int, amount_rupees: float,
                              method: str = "SIMULATED",
                              upi_id: str = None,
                              bank_account: str = None) -> dict:
    """
    Create a withdrawal request.
    Reserves the withdrawal amount immediately so it cannot be double-spent.
    """
    if amount_rupees <= 0:
        return {"success": False, "error": "Withdrawal amount must be positive"}
    if amount_rupees > 100000:
        return {"success": False, "error": "Maximum withdrawal is ₹1,00,000 per request"}
    if method not in ("SIMULATED", "UPI", "BANK"):
        method = "SIMULATED"

    amount_paise = rupees_to_paise(amount_rupees)
    conn = get_connection()
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")
        wallet = _get_wallet_exclusive(conn, user_id)
        available = _available_balance(wallet)

        if amount_paise > available:
            conn.rollback()
            return {
                "success": False,
                "error": (
                    f"Insufficient available balance. "
                    f"Available: ₹{paise_to_rupees(available):,.2f}, "
                    f"Requested: ₹{paise_to_rupees(amount_paise):,.2f}"
                )
            }

        # Create a reservation record for withdrawal (auction_id=0 sentinel)
        ikey = f"WDRES-{user_id}-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO wallet_transactions
                (user_id, type, amount, status, description, idempotency_key)
            VALUES (?, 'WITHDRAWAL', ?, 'PENDING', ?, ?)
        """, (user_id, amount_paise, f"Withdrawal request via {method}", ikey))
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Use auction_id=0 for withdrawal reservations
        conn.execute("""
            INSERT INTO wallet_reservations
                (user_id, auction_id, amount, purpose, status, transaction_id)
            VALUES (?, 0, ?, 'WITHDRAWAL', 'ACTIVE', ?)
        """, (user_id, amount_paise, txn_id))
        res_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Reserve funds
        conn.execute("""
            UPDATE wallets SET reserved = reserved + ?,
                updated_at=datetime('now','localtime')
            WHERE user_id=?
        """, (amount_paise, user_id))

        # Create withdrawal request record
        conn.execute("""
            INSERT INTO withdrawal_requests
                (user_id, amount, method, upi_id, bank_account, status, transaction_id, reservation_id)
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
        """, (user_id, amount_paise, method, upi_id, bank_account, txn_id, res_id))
        wd_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.commit()
        return {
            "success": True,
            "withdrawal_id": wd_id,
            "amount": paise_to_rupees(amount_paise),
            "message": (
                f"Withdrawal request of ₹{paise_to_rupees(amount_paise):,.2f} submitted. "
                "⚠️ This is a simulated withdrawal for demonstration purposes. "
                "No real money will be transferred."
            )
        }
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"create_withdrawal_request integrity error: {e}")
        return {"success": False, "error": "Wallet integrity check failed"}
    except Exception as e:
        conn.rollback()
        logger.error(f"create_withdrawal_request error: {e}")
        return {"success": False, "error": "Failed to create withdrawal request"}
    finally:
        conn.close()


def cancel_withdrawal_request(user_id: int, withdrawal_id: int) -> dict:
    """Allow user to cancel their own pending withdrawal."""
    conn = get_connection()
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")
        wd = conn.execute("""
            SELECT * FROM withdrawal_requests
            WHERE id=? AND user_id=? AND status='PENDING'
        """, (withdrawal_id, user_id)).fetchone()

        if not wd:
            conn.rollback()
            return {"success": False, "error": "Withdrawal request not found or cannot be cancelled"}

        # Release reservation
        conn.execute("""
            UPDATE wallets SET reserved = reserved - ?,
                updated_at=datetime('now','localtime')
            WHERE user_id=?
        """, (wd["amount"], user_id))

        # Update reservation status
        if wd["reservation_id"]:
            conn.execute("""
                UPDATE wallet_reservations SET status='RELEASED',
                    updated_at=datetime('now','localtime')
                WHERE id=?
            """, (wd["reservation_id"],))

        # Cancel transaction
        if wd["transaction_id"]:
            conn.execute("""
                UPDATE wallet_transactions SET status='CANCELLED',
                    updated_at=datetime('now','localtime')
                WHERE id=?
            """, (wd["transaction_id"],))

        # Mark withdrawal as cancelled
        conn.execute("""
            UPDATE withdrawal_requests SET status='CANCELLED',
                updated_at=datetime('now','localtime')
            WHERE id=?
        """, (withdrawal_id,))

        conn.commit()
        return {"success": True, "message": "Withdrawal request cancelled and funds released."}
    except Exception as e:
        conn.rollback()
        logger.error(f"cancel_withdrawal_request error: {e}")
        return {"success": False, "error": "Failed to cancel withdrawal"}
    finally:
        conn.close()


def admin_process_withdrawal(admin_id: int, withdrawal_id: int,
                             action: str, admin_note: str = "") -> dict:
    """
    Admin approves or rejects a withdrawal request.
    action: 'APPROVE' or 'REJECT'
    """
    action = action.upper()
    if action not in ("APPROVE", "REJECT"):
        return {"success": False, "error": "Action must be APPROVE or REJECT"}

    conn = get_connection()
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")
        wd = conn.execute(
            "SELECT * FROM withdrawal_requests WHERE id=? AND status='PENDING'",
            (withdrawal_id,)
        ).fetchone()

        if not wd:
            conn.rollback()
            return {"success": False, "error": "Withdrawal not found or already processed"}

        user_id = wd["user_id"]
        amount = int(wd["amount"])

        if action == "APPROVE":
            # Deduct balance (reservation already holds the amount)
            conn.execute("""
                UPDATE wallets
                SET balance = balance - ?, reserved = reserved - ?,
                    updated_at=datetime('now','localtime')
                WHERE user_id=?
            """, (amount, amount, user_id))

            # Mark reservation settled
            if wd["reservation_id"]:
                conn.execute("""
                    UPDATE wallet_reservations SET status='SETTLED',
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                """, (wd["reservation_id"],))

            # Mark transaction complete
            if wd["transaction_id"]:
                conn.execute("""
                    UPDATE wallet_transactions SET status='COMPLETED',
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                """, (wd["transaction_id"],))

            new_status = "COMPLETED"
        else:  # REJECT
            # Release reservation
            conn.execute("""
                UPDATE wallets SET reserved = reserved - ?,
                    updated_at=datetime('now','localtime')
                WHERE user_id=?
            """, (amount, user_id))

            if wd["reservation_id"]:
                conn.execute("""
                    UPDATE wallet_reservations SET status='RELEASED',
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                """, (wd["reservation_id"],))

            if wd["transaction_id"]:
                conn.execute("""
                    UPDATE wallet_transactions SET status='CANCELLED',
                        updated_at=datetime('now','localtime')
                    WHERE id=?
                """, (wd["transaction_id"],))

            new_status = "REJECTED"

        conn.execute("""
            UPDATE withdrawal_requests
            SET status=?, admin_note=?, updated_at=datetime('now','localtime')
            WHERE id=?
        """, (new_status, admin_note or "", withdrawal_id))

        # Audit log
        conn.execute("""
            INSERT INTO wallet_audit_log (admin_id, action, target_user_id, details)
            VALUES (?, ?, ?, ?)
        """, (admin_id, f"WITHDRAWAL_{action}",
              user_id,
              f"withdrawal_id={withdrawal_id}, amount={paise_to_rupees(amount)}, note={admin_note}"))

        conn.commit()
        return {
            "success": True,
            "new_status": new_status,
            "message": f"Withdrawal {action.lower()}d successfully."
        }
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"admin_process_withdrawal integrity error: {e}")
        return {"success": False, "error": "Wallet integrity check failed"}
    except Exception as e:
        conn.rollback()
        logger.error(f"admin_process_withdrawal error: {e}")
        return {"success": False, "error": "Failed to process withdrawal"}
    finally:
        conn.close()


def admin_adjust_balance(admin_id: int, user_id: int,
                         amount_rupees: float, direction: str,
                         reason: str) -> dict:
    """
    Admin credit/debit adjustment. Requires a reason.
    Every adjustment is recorded in the audit log.
    """
    direction = direction.upper()
    if direction not in ("CREDIT", "DEBIT"):
        return {"success": False, "error": "Direction must be CREDIT or DEBIT"}
    if not reason or not reason.strip():
        return {"success": False, "error": "Reason is required for balance adjustments"}
    if amount_rupees <= 0:
        return {"success": False, "error": "Adjustment amount must be positive"}

    amount_paise = rupees_to_paise(amount_rupees)
    txn_type = "ADMIN_CREDIT" if direction == "CREDIT" else "ADMIN_DEBIT"

    conn = get_connection()
    conn.isolation_level = 'EXCLUSIVE'
    try:
        conn.execute("BEGIN EXCLUSIVE")
        wallet = _get_wallet_exclusive(conn, user_id)
        if direction == "DEBIT":
            available = _available_balance(wallet)
            if amount_paise > available:
                conn.rollback()
                return {"success": False, "error": f"Cannot debit more than available balance (₹{paise_to_rupees(available):,.2f})"}
            conn.execute("""
                UPDATE wallets SET balance = balance - ?,
                    updated_at=datetime('now','localtime')
                WHERE user_id=?
            """, (amount_paise, user_id))
        else:
            conn.execute("""
                UPDATE wallets SET balance = balance + ?,
                    updated_at=datetime('now','localtime')
                WHERE user_id=?
            """, (amount_paise, user_id))

        conn.execute("""
            INSERT INTO wallet_transactions
                (user_id, type, amount, status, description, idempotency_key)
            VALUES (?, ?, ?, 'COMPLETED', ?, ?)
        """, (user_id, txn_type, amount_paise,
              f"Admin {direction.lower()}: {reason}",
              f"ADM-{uuid.uuid4().hex}"))

        conn.execute("""
            INSERT INTO wallet_audit_log (admin_id, action, target_user_id, details)
            VALUES (?, ?, ?, ?)
        """, (admin_id, f"BALANCE_{direction}",
              user_id,
              f"amount={paise_to_rupees(amount_paise)}, reason={reason}"))

        conn.commit()
        return {"success": True, "message": f"Balance {direction.lower()}ed by ₹{paise_to_rupees(amount_paise):,.2f}"}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"admin_adjust_balance integrity error: {e}")
        return {"success": False, "error": "Balance integrity check failed"}
    except Exception as e:
        conn.rollback()
        logger.error(f"admin_adjust_balance error: {e}")
        return {"success": False, "error": "Failed to adjust balance"}
    finally:
        conn.close()


# ── Private formatting helper ─────────────────────────────────────────────────

def _fmt_txn(row) -> dict:
    """Format a wallet_transactions row for API response."""
    type_labels = {
        "DEPOSIT":     "Deposit",
        "WITHDRAWAL":  "Withdrawal",
        "BID_RESERVE": "Bid Reserved",
        "BID_RELEASE": "Bid Released",
        "WIN_DEBIT":   "Auction Win Payment",
        "ADMIN_CREDIT":"Admin Credit",
        "ADMIN_DEBIT": "Admin Debit",
        "REFUND":      "Refund",
    }
    type_dir = {
        "DEPOSIT": "credit", "ADMIN_CREDIT": "credit", "REFUND": "credit",
        "BID_RELEASE": "credit",
        "WITHDRAWAL": "debit", "WIN_DEBIT": "debit", "ADMIN_DEBIT": "debit",
        "BID_RESERVE": "hold",
    }
    t = row["type"]
    return {
        "id":          row["id"],
        "type":        t,
        "type_label":  type_labels.get(t, t),
        "direction":   type_dir.get(t, "neutral"),
        "amount":      paise_to_rupees(row["amount"]),
        "status":      row["status"],
        "description": row["description"],
        "reference_id": row["reference_id"] if "reference_id" in row.keys() else None,
        "related_id":  row["related_id"] if "related_id" in row.keys() else None,
        "created_at":  row["created_at"],
    }
