from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
import re
from functools import wraps
from database.db import get_connection

auth_bp = Blueprint('auth', __name__)

def require_user(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id") or session.get("role") != "ADMIN":
            return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function


def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")

    if not username or not email or not password or not confirm_password:
        return jsonify({"success": False, "error": "All fields are required"}), 400
    
    if password != confirm_password:
        return jsonify({"success": False, "error": "Passwords do not match"}), 400
    
    if not is_valid_email(email):
        return jsonify({"success": False, "error": "Invalid email format"}), 400

    conn = get_connection()
    try:
        # Check for duplicates
        existing = conn.execute("SELECT id FROM users WHERE email = ? OR username = ?", (email, username)).fetchone()
        if existing:
            return jsonify({"success": False, "error": "Username or email already exists"}), 400
        
        password_hash = generate_password_hash(password)
        
        conn.execute(
            """INSERT INTO users (username, email, password_hash, role, email_verified)
               VALUES (?, ?, ?, 'USER', 0)""",
            (username, email, password_hash)
        )
        conn.commit()

        # Create wallet for new user
        try:
            new_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if new_user:
                conn.execute(
                    "INSERT OR IGNORE INTO wallets (user_id, balance, reserved) VALUES (?, 0, 0)",
                    (new_user["id"],)
                )
                conn.commit()
        except Exception:
            pass  # Wallet creation is non-critical for registration

        return jsonify({"success": True, "message": "Registration successful"}), 201
    except Exception as e:
        return jsonify({"success": False, "error": "Registration failed"}), 500
    finally:
        conn.close()

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ? AND role = 'USER'", (email,)).fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200
    else:
        # Generic error as requested
        return jsonify({"success": False, "error": "Invalid email or password."}), 401


@auth_bp.route('/admin-login', methods=['POST'])
def admin_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ? AND role = 'ADMIN'", (email,)).fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200
    else:
        # Generic error
        return jsonify({"success": False, "error": "Invalid email or password."}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"}), 200

@auth_bp.route('/me', methods=['GET'])
def get_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False})
    
    conn = get_connection()
    user = conn.execute("SELECT id, username, email, role FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if user:
        return jsonify({
            "authenticated": True,
            "user": dict(user)
        })
    else:
        session.clear()
        return jsonify({"authenticated": False})


@auth_bp.route('/password-reset/request', methods=['POST'])
def request_password_reset():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    conn = get_connection()
    user = conn.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE AND role = 'USER'", (email,)).fetchone()
    
    if user:
        import secrets, datetime
        from services.email_service import send_otp_email
        
        # Check cooldown (60 seconds)
        last_otp = conn.execute(
            "SELECT created_at FROM email_otps WHERE user_id = ? AND purpose = 'PASSWORD_RESET' ORDER BY id DESC LIMIT 1",
            (user['id'],)
        ).fetchone()
        
        if last_otp:
            created_time = datetime.datetime.strptime(last_otp['created_at'], '%Y-%m-%d %H:%M:%S')
            if (datetime.datetime.now() - created_time).total_seconds() < 60:
                conn.close()
                return jsonify({"success": False, "error": "Please wait before requesting another code."}), 429
                
        # Generate 6-digit OTP using secrets (preserves leading zeroes)
        otp = "".join(secrets.choice("0123456789") for _ in range(6))
        otp_hash = generate_password_hash(otp)
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Invalidate old OTPs
        conn.execute("DELETE FROM email_otps WHERE user_id = ? AND purpose = 'PASSWORD_RESET'", (user['id'],))
        
        # Store new OTP
        conn.execute(
            "INSERT INTO email_otps (user_id, email, otp_hash, purpose, expires_at) VALUES (?, ?, ?, 'PASSWORD_RESET', ?)",
            (user['id'], email, otp_hash, expires_at)
        )
        conn.commit()
        
        # Send email
        subject = "University Auctions — Password Reset OTP"
        success = send_otp_email(email, otp, subject=subject)
        
        if not success:
            conn.close()
            return jsonify({"success": False, "error": "Unable to send verification email. Please try again later."}), 500
    
    conn.close()
    # Generic response to prevent enumeration
    return jsonify({"success": True, "message": "If the account exists, a verification code has been sent."}), 200


@auth_bp.route('/password-reset/verify', methods=['POST'])
def verify_password_reset():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    otp = data.get("otp", "").strip()

    if not email or not otp:
        return jsonify({"success": False, "error": "Email and OTP are required"}), 400

    conn = get_connection()
    user = conn.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({"success": False, "error": "Invalid verification code"}), 400
        
    record = conn.execute(
        "SELECT * FROM email_otps WHERE user_id = ? AND purpose = 'PASSWORD_RESET' ORDER BY id DESC LIMIT 1",
        (user['id'],)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"success": False, "error": "Invalid verification code"}), 400

    import datetime
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

    conn.close()
    return jsonify({"success": True, "message": "Code verified"}), 200


@auth_bp.route('/password-reset/complete', methods=['POST'])
def complete_password_reset():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    otp = data.get("otp", "").strip()
    new_password = data.get("new_password", "")
    
    if not email or not otp or not new_password:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    conn = get_connection()
    user = conn.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({"success": False, "error": "Invalid request"}), 400
        
    record = conn.execute(
        "SELECT * FROM email_otps WHERE user_id = ? AND purpose = 'PASSWORD_RESET' ORDER BY id DESC LIMIT 1",
        (user['id'],)
    ).fetchone()

    # Re-verify OTP to ensure security
    if not record or not check_password_hash(record["otp_hash"], otp):
        conn.close()
        return jsonify({"success": False, "error": "Invalid or expired verification code"}), 400

    try:
        password_hash = generate_password_hash(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user['id']))
        conn.execute("DELETE FROM email_otps WHERE id = ?", (record["id"],))
        conn.commit()
        return jsonify({"success": True, "message": "Password updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to update password"}), 500
    finally:
        conn.close()
