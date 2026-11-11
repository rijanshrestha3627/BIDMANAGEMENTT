import sqlite3
import os
from werkzeug.security import generate_password_hash

# Database file is stored in the python-backend directory
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auction.db')

def get_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """
    Create all required tables if they don't already exist.
    This is called automatically when the Flask app starts.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            starting_price REAL NOT NULL,
            current_highest_bid REAL DEFAULT 0,
            minimum_increment REAL NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT DEFAULT 'UPCOMING',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            image_path TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'USER',
            email_verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id INTEGER NOT NULL,
            user_id INTEGER,
            bidder_name TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (auction_id) REFERENCES auctions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            purpose TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Migration for existing bids table to add user_id if it doesn't exist
    try:
        cursor.execute("ALTER TABLE bids ADD COLUMN user_id INTEGER REFERENCES users(id)")
    except sqlite3.OperationalError:
        pass # Column already exists

    # ── PHASE 7: Wallet System Tables ──────────────────────────────────────────
    # All monetary values stored as INTEGER paise (1 INR = 100 paise)
    # to avoid floating-point rounding errors.

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL UNIQUE,
            balance     INTEGER NOT NULL DEFAULT 0,
            reserved    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            CHECK (balance >= 0),
            CHECK (reserved >= 0),
            CHECK (balance >= reserved)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            type            TEXT    NOT NULL,
            amount          INTEGER NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'PENDING',
            description     TEXT,
            reference_id    TEXT,
            idempotency_key TEXT    UNIQUE,
            related_id      INTEGER,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            CHECK (amount > 0),
            CHECK (type IN ('DEPOSIT','WITHDRAWAL','BID_RESERVE','BID_RELEASE','WIN_DEBIT','ADMIN_CREDIT','ADMIN_DEBIT','REFUND')),
            CHECK (status IN ('PENDING','COMPLETED','FAILED','CANCELLED','RESERVED'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallet_reservations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            auction_id      INTEGER NOT NULL,
            amount          INTEGER NOT NULL,
            purpose         TEXT    NOT NULL DEFAULT 'BID',
            status          TEXT    NOT NULL DEFAULT 'ACTIVE',
            transaction_id  INTEGER,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id)      REFERENCES users(id),
            FOREIGN KEY (auction_id)   REFERENCES auctions(id),
            FOREIGN KEY (transaction_id) REFERENCES wallet_transactions(id),
            CHECK (amount > 0),
            CHECK (purpose IN ('BID','WITHDRAWAL')),
            CHECK (status IN ('ACTIVE','RELEASED','SETTLED'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawal_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            amount          INTEGER NOT NULL,
            method          TEXT    NOT NULL DEFAULT 'SIMULATED',
            upi_id          TEXT,
            bank_account    TEXT,
            status          TEXT    NOT NULL DEFAULT 'PENDING',
            admin_note      TEXT,
            transaction_id  INTEGER,
            reservation_id  INTEGER,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id)         REFERENCES users(id),
            FOREIGN KEY (transaction_id)  REFERENCES wallet_transactions(id),
            FOREIGN KEY (reservation_id)  REFERENCES wallet_reservations(id),
            CHECK (amount > 0),
            CHECK (status IN ('PENDING','APPROVED','REJECTED','COMPLETED','CANCELLED'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallet_audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id    INTEGER NOT NULL,
            action      TEXT    NOT NULL,
            target_user_id INTEGER,
            details     TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (admin_id)       REFERENCES users(id),
            FOREIGN KEY (target_user_id) REFERENCES users(id)
        )
    ''')

    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wt_user_id ON wallet_transactions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wr_user_id ON wallet_reservations(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wr_auction_id ON wallet_reservations(auction_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wdr_user_id ON withdrawal_requests(user_id)")

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

    # Ensure every existing user has a wallet row
    _ensure_wallets_for_existing_users()

    # Seed demo data if database has no auctions
    seed_demo_data()

    # Seed default admin user
    seed_admin_user()


def _ensure_wallets_for_existing_users():
    """
    Migration helper: create wallet rows for any users that don't have one.
    Safe to call multiple times (idempotent).
    """
    conn = get_connection()
    try:
        # Find all user IDs that don't have a wallet
        rows = conn.execute("""
            SELECT u.id FROM users u
            LEFT JOIN wallets w ON w.user_id = u.id
            WHERE w.id IS NULL
        """).fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO wallets (user_id, balance, reserved) VALUES (?, 0, 0)",
                (row["id"],)
            )
        conn.commit()
        if rows:
            print(f"  Created wallet rows for {len(rows)} existing user(s).")
    except Exception as e:
        print(f"  WARNING: Could not ensure wallets for existing users: {e}")
    finally:
        conn.close()


def get_or_create_wallet(conn, user_id):
    """
    Return the wallet row for user_id, creating it if absent.
    Caller must pass an open connection; caller is responsible for commit.
    Returns a sqlite3.Row (or None on fatal error).
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


def seed_admin_user():
    """Seed a default admin user if one does not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    existing = cursor.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
    if not existing:
        cursor.execute(
            """INSERT INTO users (username, email, password_hash, role, email_verified)
               VALUES (?, ?, ?, 'ADMIN', 1)""",
            ('Admin', admin_email, generate_password_hash(admin_password))
        )
        conn.commit()
        print(f"Default admin seeded: {admin_email}")
    conn.close()


def seed_demo_data(force=False):
    """
    Seed standard realistic demo auctions if the database is currently empty
    or if force=True (without overwriting existing user-created auctions).
    """
    from datetime import datetime, timedelta
    conn = get_connection()
    cursor = conn.cursor()

    count = cursor.execute("SELECT COUNT(*) FROM auctions").fetchone()[0]
    if count > 0 and not force:
        conn.close()
        return False

    now = datetime.now()
    start_time = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    demo_items = [
        {
            "title": "Wireless Headphones",
            "description": "Noise-cancelling wireless over-ear headphones with 30-hour battery life.",
            "starting_price": 2500.0,
            "minimum_increment": 100.0
        },
        {
            "title": "Mechanical Keyboard",
            "description": "Tactile mechanical gaming keyboard with customizable RGB backlighting.",
            "starting_price": 3000.0,
            "minimum_increment": 200.0
        },
        {
            "title": "Laptop",
            "description": "High-performance laptop with 16GB RAM and fast 512GB SSD storage.",
            "starting_price": 45000.0,
            "minimum_increment": 500.0
        },
        {
            "title": "Smart Watch",
            "description": "Fitness smartwatch with AMOLED display and optical heart rate monitor.",
            "starting_price": 4000.0,
            "minimum_increment": 200.0
        },
        {
            "title": "Gaming Mouse",
            "description": "Ergonomic gaming mouse with high-precision optical sensor and customizable DPI.",
            "starting_price": 1500.0,
            "minimum_increment": 100.0
        }
    ]

    for item in demo_items:
        # Avoid duplicating title if it already exists
        existing = cursor.execute("SELECT id FROM auctions WHERE title = ?", (item["title"],)).fetchone()
        if not existing:
            cursor.execute(
                """INSERT INTO auctions (title, description, starting_price, minimum_increment,
                   start_time, end_time, current_highest_bid)
                   VALUES (?, ?, ?, ?, ?, ?, 0)""",
                (item["title"], item["description"], item["starting_price"],
                 item["minimum_increment"], start_time, end_time)
            )

    conn.commit()
    conn.close()
    print("Demo auctions seeded successfully.")
    return True

