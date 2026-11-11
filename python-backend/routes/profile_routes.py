from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_connection
from routes.auth_routes import require_user, is_valid_email
from services.email_service import send_otp_email
import random
import datetime
from datetime import datetime as dt

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/', methods=['GET'])
@require_user
def get_profile():
    user_id = session.get("user_id")
    conn = get_connection()
    user = conn.execute("SELECT id, username, email, role, email_verified, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    
    # Get basic stats
    stats = {
        "total_bids": 0,
        "auctions_participated": 0,
        "auctions_won": 0,
        "active_bids": 0
    }
    
    bids_count = conn.execute("SELECT COUNT(*) FROM bids WHERE user_id = ?", (user_id,)).fetchone()[0]
    stats["total_bids"] = bids_count
    
    auctions_part = conn.execute("SELECT COUNT(DISTINCT auction_id) FROM bids WHERE user_id = ?", (user_id,)).fetchone()[0]
    stats["auctions_participated"] = auctions_part

    conn.close()
    
    return jsonify({
        "success": True,
        "user": dict(user),
        "stats": stats
    }), 200

@profile_bp.route('/username', methods=['PUT'])
@require_user
def change_username():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    new_username = data.get("new_username", "").strip()

    if not new_username:
        return jsonify({"success": False, "error": "New username cannot be empty"}), 400

    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (new_username,)).fetchone()
        if existing and existing['id'] != user_id:
            return jsonify({"success": False, "error": "Username already taken"}), 400
        
        conn.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, user_id))
        conn.commit()
        return jsonify({"success": True, "message": "Username updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to update username"}), 500
    finally:
        conn.close()

@profile_bp.route('/password', methods=['PUT'])
@require_user
def change_password():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not current_password or not new_password or not confirm_password:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    if new_password != confirm_password:
        return jsonify({"success": False, "error": "New passwords do not match"}), 400

    conn = get_connection()
    user = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not user or not check_password_hash(user["password_hash"], current_password):
        conn.close()
        return jsonify({"success": False, "error": "Incorrect current password"}), 401
    
    try:
        password_hash = generate_password_hash(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()
        return jsonify({"success": True, "message": "Password updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to update password"}), 500
    finally:
        conn.close()

@profile_bp.route('/email/request', methods=['POST'])
@require_user
def request_email_change():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    new_email = data.get("new_email", "").strip()

    if not new_email or not is_valid_email(new_email):
        return jsonify({"success": False, "error": "Invalid email address"}), 400

    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (new_email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "error": "Email is already in use"}), 400

    # Check cooldown (60 seconds)
    last_otp = conn.execute(
        "SELECT created_at FROM email_otps WHERE user_id = ? AND purpose = 'EMAIL_CHANGE' ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    
    if last_otp:
        created_time = datetime.datetime.strptime(last_otp['created_at'], '%Y-%m-%d %H:%M:%S')
        if (datetime.datetime.now() - created_time).total_seconds() < 60:
            conn.close()
            return jsonify({"success": False, "error": "Please wait before requesting another code."}), 429

    import secrets
    otp = "".join(secrets.choice("0123456789") for _ in range(6))
    otp_hash = generate_password_hash(otp)
    expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        conn.execute("DELETE FROM email_otps WHERE user_id = ? AND purpose = 'EMAIL_CHANGE'", (user_id,))
        conn.execute(
            "INSERT INTO email_otps (user_id, email, otp_hash, purpose, expires_at) VALUES (?, ?, ?, 'EMAIL_CHANGE', ?)",
            (user_id, new_email, otp_hash, expires_at)
        )
        conn.commit()
        
        # Send email
        subject = "University Auctions — Verify Your New Email"
        success = send_otp_email(new_email, otp, subject=subject)
        
        if not success:
            return jsonify({"success": False, "error": "Unable to send verification email. Please try again later."}), 500
        
        return jsonify({"success": True, "message": "Verification code sent to your email."}), 200
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to process request"}), 500
    finally:
        conn.close()

@profile_bp.route('/email/verify', methods=['POST'])
@require_user
def verify_email_change():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    otp = data.get("otp", "").strip()

    if not otp:
        return jsonify({"success": False, "error": "OTP is required"}), 400

    conn = get_connection()
    record = conn.execute(
        "SELECT * FROM email_otps WHERE user_id = ? AND purpose = 'EMAIL_CHANGE' ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"success": False, "error": "No pending email change request"}), 400

    if datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') > record["expires_at"]:
        conn.execute("DELETE FROM email_otps WHERE id = ?", (record["id"],))
        conn.commit()
        conn.close()
        return jsonify({"success": False, "error": "Verification code expired"}), 400

    if record["attempts"] >= 3:
        conn.execute("DELETE FROM email_otps WHERE id = ?", (record["id"],))
        conn.commit()
        conn.close()
        return jsonify({"success": False, "error": "Too many failed attempts. Request a new code."}), 400

    if not check_password_hash(record["otp_hash"], otp):
        conn.execute("UPDATE email_otps SET attempts = attempts + 1 WHERE id = ?", (record["id"],))
        conn.commit()
        conn.close()
        return jsonify({"success": False, "error": "Invalid verification code"}), 400

    try:
        new_email = record["email"]
        conn.execute("UPDATE users SET email = ?, email_verified = 1 WHERE id = ?", (new_email, user_id))
        conn.execute("DELETE FROM email_otps WHERE id = ?", (record["id"],))
        conn.commit()
        return jsonify({"success": True, "message": "Email updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to update email"}), 500
    finally:
        conn.close()


# ============================================================
# GET /api/profile/activity
# Returns user's auction history, statistics, and bid history.
# ALL data is scoped to session["user_id"] — never accepts client user_id.
# ============================================================
@profile_bp.route('/activity', methods=['GET'])
@require_user
def get_activity():
    user_id = session.get("user_id")
    conn = get_connection()
    try:
        # ── Extended statistics ────────────────────────────────────────────
        total_bids = conn.execute(
            "SELECT COUNT(*) FROM bids WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        auctions_participated = conn.execute(
            "SELECT COUNT(DISTINCT auction_id) FROM bids WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        highest_bid = conn.execute(
            "SELECT COALESCE(MAX(amount), 0) FROM bids WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        total_amount = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bids WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        # ── Per-auction summary ────────────────────────────────────────────
        auction_rows = conn.execute("""
            SELECT
                a.id, a.title, a.starting_price, a.current_highest_bid,
                a.start_time, a.end_time, a.image_path,
                COUNT(b.id)      AS user_bid_count,
                MAX(b.amount)    AS user_highest_bid,
                MIN(b.created_at) AS first_bid_at,
                MAX(b.created_at) AS last_bid_at
            FROM bids b
            JOIN auctions a ON b.auction_id = a.id
            WHERE b.user_id = ?
            GROUP BY a.id
            ORDER BY MAX(b.created_at) DESC
        """, (user_id,)).fetchall()

        def compute_status(start_str, end_str):
            now = dt.now()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
                try:
                    s = dt.strptime(start_str, fmt)
                    e = dt.strptime(end_str, fmt)
                    if now < s: return "UPCOMING"
                    elif now <= e: return "ACTIVE"
                    else: return "ENDED"
                except ValueError:
                    continue
            return "UNKNOWN"

        won_count = 0
        lost_count = 0
        active_bid_count = 0
        auctions_list = []

        for row in auction_rows:
            status = compute_status(row["start_time"], row["end_time"])
            user_high = row["user_highest_bid"] or 0
            current_high = row["current_highest_bid"] or 0

            if status == "ACTIVE":
                active_bid_count += 1
                result = "WINNING" if user_high >= current_high else "OUTBID"
            elif status == "ENDED":
                if user_high >= current_high and current_high > 0:
                    result = "WON"
                    won_count += 1
                else:
                    result = "LOST"
                    lost_count += 1
            else:
                result = "UPCOMING"

            auctions_list.append({
                "auction_id": row["id"],
                "title": row["title"],
                "image_path": row["image_path"],
                "starting_price": row["starting_price"],
                "current_highest_bid": current_high,
                "user_highest_bid": user_high,
                "user_bid_count": row["user_bid_count"],
                "first_bid_at": row["first_bid_at"],
                "last_bid_at": row["last_bid_at"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "status": status,
                "result": result
            })

        # ── Full bid history (all individual bids) ─────────────────────────
        bid_rows = conn.execute("""
            SELECT
                b.id, b.amount, b.created_at,
                a.id AS auction_id, a.title AS auction_title,
                a.current_highest_bid, a.start_time, a.end_time,
                a.image_path
            FROM bids b
            JOIN auctions a ON b.auction_id = a.id
            WHERE b.user_id = ?
            ORDER BY b.created_at DESC
        """, (user_id,)).fetchall()

        bids_list = []
        for row in bid_rows:
            status = compute_status(row["start_time"], row["end_time"])
            current_high = row["current_highest_bid"] or 0
            # Determine result for this individual bid
            if status == "ACTIVE":
                r = "WINNING" if row["amount"] >= current_high else "OUTBID"
            elif status == "ENDED":
                r = "WON" if row["amount"] >= current_high and current_high > 0 else "LOST"
            else:
                r = "UPCOMING"
            bids_list.append({
                "bid_id": row["id"],
                "auction_id": row["auction_id"],
                "auction_title": row["auction_title"],
                "auction_image": row["image_path"],
                "amount": row["amount"],
                "created_at": row["created_at"],
                "auction_status": status,
                "current_highest_bid": current_high,
                "result": r
            })

        return jsonify({
            "success": True,
            "stats": {
                "total_bids": total_bids,
                "auctions_participated": auctions_participated,
                "active_bids": active_bid_count,
                "won": won_count,
                "lost": lost_count,
                "highest_bid": round(highest_bid, 2),
                "total_amount_bid": round(total_amount, 2)
            },
            "auctions": auctions_list,
            "bids": bids_list
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"get_activity error: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve activity"}), 500
    finally:
        conn.close()


# ============================================================
# GET /api/profile/bids-over-time
# User's bids grouped by day, last 14 days.
# ============================================================
@profile_bp.route('/bids-over-time', methods=['GET'])
@require_user
def get_user_bids_over_time():
    user_id = session.get("user_id")
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT DATE(created_at) AS bid_date, COUNT(*) AS count
            FROM bids
            WHERE user_id = ? AND created_at >= DATE('now', '-13 days')
            GROUP BY DATE(created_at)
            ORDER BY bid_date ASC
        """, (user_id,)).fetchall()
        conn.close()

        from datetime import date, timedelta
        today = date.today()
        date_map = {row["bid_date"]: row["count"] for row in rows}
        result = []
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
        return jsonify({"error": "Failed to retrieve chart data"}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
