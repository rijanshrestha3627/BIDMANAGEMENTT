from flask import Flask, send_from_directory
from flask_cors import CORS
from database.db import init_db, get_connection
from routes.auction_routes import auction_bp, datetime_to_millis
from services.java_bridge import load_auction_in_engine, check_java_engine
import os

app = Flask(__name__)

# ── Secret key (must be set before session config) ────────────────────────────
app.secret_key = os.environ.get('SECRET_KEY', 'default-dev-secret-key-change-in-prod')

# ── Session cookie — compatible with cross-port localhost dev (HTTP) ──────────
# SameSite=Lax: cookie is sent on same-origin requests and top-level navigations.
# Secure=False: required for plain HTTP on localhost.
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False   # HTTP only in dev; set True in prod (HTTPS)

# ── CORS — specific origin required for credentialed requests ─────────────────
# Access-Control-Allow-Origin: * is incompatible with credentials:include.
# We must name the exact origin(s).
CORS(
    app,
    supports_credentials=True,
    origins=["http://localhost:5500", "http://127.0.0.1:5500"]
)

# ── Uploads ───────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'auctions')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/uploads/auctions/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ── Blueprints ────────────────────────────────────────────────────────────────
app.register_blueprint(auction_bp, url_prefix='/api')

from routes.auth_routes import auth_bp
app.register_blueprint(auth_bp, url_prefix='/api/auth')

from routes.profile_routes import profile_bp
app.register_blueprint(profile_bp, url_prefix='/api/profile')

from routes.admin_routes import admin_bp
app.register_blueprint(admin_bp, url_prefix='/api/admin')

from routes.wallet_routes import wallet_bp
app.register_blueprint(wallet_bp, url_prefix='/api/wallet')

from routes.admin_wallet_routes import admin_wallet_bp
app.register_blueprint(admin_wallet_bp, url_prefix='/api/admin/wallet')

# ── Startup sync ──────────────────────────────────────────────────────────────
from services.java_bridge import load_auction_in_engine, check_java_engine, sync_single_auction_to_java

def sync_auctions_to_java():
    """
    On Flask startup, load all existing auctions and their bid history from SQLite into
    the Java engine so its BidPriorityQueue can be reconstructed.

    This ensures that even if the Java engine is restarted, the auction
    data and PriorityQueue state are fully reconstructed from the database.
    """
    if not check_java_engine():
        print("WARNING: Java engine is offline. Auctions will not be synced.")
        print("Start the Java engine and restart Flask to sync.")
        return

    conn = get_connection()
    rows = conn.execute("SELECT id, title FROM auctions").fetchall()
    conn.close()

    for row in rows:
        result = sync_single_auction_to_java(row["id"])
        print(f"  Synced auction #{row['id']}: {row['title']} -> {result}")

    print(f"Synced {len(rows)} auction(s) and their PriorityQueue states to Java engine.")


if __name__ == '__main__':
    init_db()
    sync_auctions_to_java()
    
    mail_host = os.environ.get('MAIL_HOST')
    mail_user = os.environ.get('MAIL_USERNAME')
    mail_pass = os.environ.get('MAIL_PASSWORD')
    if mail_host and mail_user and mail_pass:
        print("\nSMTP email service configured.")
    else:
        print("\nSMTP email service not configured. OTP delivery will be disabled.")
        
    print("Flask server starting on http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)
