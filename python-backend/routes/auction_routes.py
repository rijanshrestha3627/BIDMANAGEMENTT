from flask import Blueprint, jsonify, request, current_app, session
from routes.auth_routes import require_admin, require_user
from werkzeug.utils import secure_filename
import os
import uuid
from database.db import get_connection
from services.java_bridge import (
    load_auction_in_engine, place_bid_in_engine,
    get_auction_status_from_engine, check_java_engine,
    simulate_concurrent_bids, sync_single_auction_to_java,
    remove_auction_from_engine
)
from services import wallet_service
from datetime import datetime
import logging

auction_bp = Blueprint('auctions', __name__)

logger = logging.getLogger(__name__)


def compute_status(start_time_str, end_time_str):
    """Compute auction status from start/end time strings. Returns UNKNOWN on parse error."""
    now = datetime.now()
    try:
        try:
            start = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            start = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        try:
            end = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            end = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")

        if now < start:
            return "UPCOMING"
        elif now <= end:
            return "ACTIVE"
        else:
            return "ENDED"
    except (ValueError, TypeError) as e:
        logger.error(f"compute_status error: {e} (start={start_time_str}, end={end_time_str})")
        return "UNKNOWN"


def datetime_to_millis(dt_str):
    """Convert a datetime string to epoch milliseconds for Java. Returns 0 on error."""
    try:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError) as e:
        logger.error(f"datetime_to_millis error: {e} (value={dt_str})")
        return 0


def parse_datetime(dt_str):
    """Parse a datetime string in known formats. Returns None on failure."""
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def build_auction_dict(row):
    """Build a standardized auction dict from a DB row."""
    status = compute_status(row["start_time"], row["end_time"])
    minimum_next = (
        row["starting_price"] if row["current_highest_bid"] <= 0
        else row["current_highest_bid"] + row["minimum_increment"]
    )
    keys = row.keys()
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "starting_price": row["starting_price"],
        "current_highest_bid": row["current_highest_bid"],
        "minimum_increment": row["minimum_increment"],
        "minimum_next_bid": round(minimum_next, 2),
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "status": status,
        "created_at": row["created_at"],
        "image_path": row["image_path"] if "image_path" in keys else None,
        "bid_count": row["bid_count"] if "bid_count" in keys else None
    }



ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def handle_image_upload(request_files):
    if 'image' not in request_files:
        return None, None
    file = request_files['image']
    if file.filename == '':
        return None, None
    if file and allowed_file(file.filename):
        # file size checking can be done here or in nginx, but werkzeug takes care of basic safety
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"auction_{uuid.uuid4().hex[:8]}.{ext}"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        return f"uploads/auctions/{unique_filename}", None
    return None, "Invalid image format. Allowed: JPG, PNG, WEBP"

# ============================================
# GET /api/health
# ============================================
@auction_bp.route('/health', methods=['GET'])
def health_check():
    java_up = check_java_engine()
    return jsonify({
        "status": "ok",
        "message": "Python backend is running",
        "java_engine": "connected" if java_up else "offline"
    })


# ============================================
# GET /api/auctions — List all auctions
# ============================================
@auction_bp.route('/auctions', methods=['GET'])
def get_auctions():
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT a.*, COUNT(b.id) as bid_count
            FROM auctions a
            LEFT JOIN bids b ON b.auction_id = a.id
            GROUP BY a.id
            ORDER BY a.created_at DESC
        """).fetchall()
        conn.close()
        return jsonify([build_auction_dict(row) for row in rows])
    except Exception as e:
        logger.error(f"get_auctions error: {e}")
        return jsonify({"error": "Failed to retrieve auctions"}), 500


# ============================================
# GET /api/auctions/<id> — Get single auction
# ============================================
@auction_bp.route('/auctions/<int:auction_id>', methods=['GET'])
def get_auction(auction_id):
    try:
        conn = get_connection()
        row = conn.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Auction not found"}), 404
        return jsonify(build_auction_dict(row))
    except Exception as e:
        logger.error(f"get_auction error: {e}")
        return jsonify({"error": "Failed to retrieve auction"}), 500


# ============================================
# POST /api/admin/auctions — Create a new auction
# ============================================
@auction_bp.route('/admin/auctions', methods=['POST'])
@require_admin
def create_auction():
    # Handle multipart/form-data for image uploads
    if request.content_type.startswith('multipart/form-data'):
        data = request.form
        image_path, err = handle_image_upload(request.files)
        if err:
            return jsonify({"error": err}), 400
    else:
        data = request.get_json(silent=True) or {}
        image_path = None

    required = ["title", "description", "starting_price", "minimum_increment", "start_time", "end_time"]
    for field in required:
        if field not in data or data[field] == "" or data[field] is None:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    title = str(data["title"]).strip()
    description = str(data["description"]).strip()

    if not title or not description:
        return jsonify({"error": "Title and Description cannot be empty"}), 400

    try:
        starting_price = float(data["starting_price"])
        minimum_increment = float(data["minimum_increment"])
    except (ValueError, TypeError):
        return jsonify({"error": "Starting price and minimum increment must be numbers"}), 400

    if starting_price <= 0 or minimum_increment <= 0:
        return jsonify({"error": "Starting price and minimum increment must be greater than 0"}), 400

    start_time = str(data["start_time"]).strip()
    end_time = str(data["end_time"]).strip()

    start_dt = parse_datetime(start_time)
    end_dt = parse_datetime(end_time)
    if start_dt is None or end_dt is None or end_dt <= start_dt:
        return jsonify({"error": "Invalid dates. End time must be after start time."}), 400

    try:
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO auctions (title, description, starting_price, minimum_increment,
               start_time, end_time, current_highest_bid, image_path)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
            (title, description, starting_price, minimum_increment, start_time, end_time, image_path)
        )
        auction_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"create_auction DB error: {e}")
        return jsonify({"error": "Failed to save auction to database"}), 500

    engine_data = {
        "id": auction_id,
        "title": title,
        "description": description,
        "starting_price": starting_price,
        "minimum_increment": minimum_increment,
        "current_highest_bid": 0,
        "start_time_ms": datetime_to_millis(start_time),
        "end_time_ms": datetime_to_millis(end_time)
    }
    load_auction_in_engine(engine_data)

    return jsonify({"message": "Auction created successfully", "id": auction_id}), 201

# ============================================
# PUT /api/admin/auctions/<id> - Edit auction
# ============================================
@auction_bp.route('/admin/auctions/<int:auction_id>', methods=['PUT'])
@require_admin
def edit_auction(auction_id):
    try:
        conn = get_connection()
        auction = conn.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        if not auction:
            conn.close()
            return jsonify({"error": "Auction not found"}), 404

        if request.content_type.startswith('multipart/form-data'):
            data = request.form
            image_path, err = handle_image_upload(request.files)
            if err:
                conn.close()
                return jsonify({"error": err}), 400
        else:
            data = request.get_json(silent=True) or {}
            image_path = None
        
        # Validation
        title = str(data.get("title", auction["title"])).strip()
        description = str(data.get("description", auction["description"])).strip()
        start_time = str(data.get("start_time", auction["start_time"])).strip()
        end_time = str(data.get("end_time", auction["end_time"])).strip()

        try:
            starting_price = float(data.get("starting_price", auction["starting_price"]))
            minimum_increment = float(data.get("minimum_increment", auction["minimum_increment"]))
        except (ValueError, TypeError):
            conn.close()
            return jsonify({"error": "Prices must be numbers"}), 400

        # Safety rule: If bids exist, we cannot raise the starting_price above current_highest_bid
        if auction["current_highest_bid"] > 0:
            if starting_price > auction["current_highest_bid"]:
                conn.close()
                return jsonify({"error": "Cannot change starting price above current highest bid because bids exist."}), 400

        start_dt = parse_datetime(start_time)
        end_dt = parse_datetime(end_time)
        if start_dt is None or end_dt is None or end_dt <= start_dt:
            conn.close()
            return jsonify({"error": "Invalid dates"}), 400

        # Keep existing image if no new one was provided
        existing_image = auction["image_path"] if "image_path" in auction.keys() else None
        final_image_path = image_path if image_path else existing_image

        conn.execute(
            """UPDATE auctions 
               SET title=?, description=?, starting_price=?, minimum_increment=?, 
                   start_time=?, end_time=?, image_path=? 
               WHERE id=?""",
            (title, description, starting_price, minimum_increment, start_time, end_time, final_image_path, auction_id)
        )
        conn.commit()
        conn.close()
        
        # Sync to Java
        sync_single_auction_to_java(auction_id)
        return jsonify({"message": "Auction updated successfully"}), 200
    except Exception as e:
        logger.error(f"edit_auction error: {e}")
        return jsonify({"error": "Failed to update auction"}), 500

# ============================================
# DELETE /api/admin/auctions/<id>
# ============================================
@auction_bp.route('/admin/auctions/<int:auction_id>', methods=['DELETE'])
@require_admin
def delete_auction(auction_id):
    try:
        conn = get_connection()
        auction = conn.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        if not auction:
            conn.close()
            return jsonify({"error": "Auction not found"}), 404

        status = compute_status(auction["start_time"], auction["end_time"])
        if status != "ENDED":
            conn.close()
            return jsonify({"success": False, "message": "Only ended auctions can be deleted."}), 400

        # 1. Cleanup uploaded image
        image_path = auction["image_path"] if "image_path" in auction.keys() else None
        if image_path and image_path.startswith("uploads/"):
            try:
                base_dir = os.path.dirname(current_app.config['UPLOAD_FOLDER']) # is uploads/auctions
                # wait, current_app.config is uploads/auctions, so we need to construct it properly
                full_path = os.path.join(current_app.root_path, image_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception as e:
                logger.warning(f"Failed to delete image file: {e}")

        # 2. Delete bids
        conn.execute("DELETE FROM bids WHERE auction_id = ?", (auction_id,))
        
        # 3. Delete auction
        conn.execute("DELETE FROM auctions WHERE id = ?", (auction_id,))
        conn.commit()
        conn.close()

        # 4. Remove from Java
        remove_auction_from_engine(auction_id)

        return jsonify({"success": True, "message": "Auction and bids deleted successfully"}), 200
    except Exception as e:
        logger.error(f"delete_auction error: {e}")
        return jsonify({"success": False, "message": "Internal error deleting auction"}), 500

# ============================================
# POST /api/auctions/<id>/bids — Place a bid
# ============================================
@auction_bp.route('/auctions/<int:auction_id>/bids', methods=['POST'])
@require_user
def place_bid(auction_id):
    try:
        conn = get_connection()
        auction = conn.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        if not auction:
            conn.close()
            return jsonify({"success": False, "message": "Auction not found"}), 404

        data = request.get_json(silent=True)
        if not data:
            conn.close()
            return jsonify({"success": False, "message": "Invalid or missing JSON request body"}), 400

        # Get bidder name from user session
        user_id = session.get("user_id")
        user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({"success": False, "message": "User not found"}), 404
            
        bidder_name = user["username"]


        try:
            amount = float(data.get("amount", 0))
        except (ValueError, TypeError):
            conn.close()
            return jsonify({"success": False, "message": "Bid amount must be a number"}), 400

        if amount <= 0:
            conn.close()
            return jsonify({"success": False, "message": "Bid amount must be positive"}), 400

        # Sanity check: reject absurdly large bids (prevent float overflow in Java)
        if amount > 999_999_999:
            conn.close()
            return jsonify({"success": False, "message": "Bid amount exceeds maximum allowed value"}), 400

        # Check auction status (quick server-side check before hitting Java)
        status = compute_status(auction["start_time"], auction["end_time"])
        if status == "UPCOMING":
            conn.close()
            return jsonify({"success": False, "message": "Auction has not started yet"}), 409
        if status == "ENDED":
            conn.close()
            return jsonify({"success": False, "message": "Auction has already ended"}), 409

        # ── WALLET CHECK: reserve funds before sending to Java ─────────────────
        # This check happens before we hit Java to avoid reserving funds for
        # bids that Java would reject for other reasons (min increment etc.)
        # We first do a quick available-balance check (non-exclusive), then
        # after Java accepts, we do the exclusive reservation.
        wallet_summary = wallet_service.get_wallet_summary(user_id)
        available = wallet_summary["available"]

        # Determine how much additional funds are needed:
        # If user already has a reservation for this auction, they only need the delta.
        from database.db import get_connection as _gc
        _wconn = _gc()
        existing_res = _wconn.execute("""
            SELECT amount FROM wallet_reservations
            WHERE user_id=? AND auction_id=? AND status='ACTIVE' AND purpose='BID'
            ORDER BY id DESC LIMIT 1
        """, (user_id, auction_id)).fetchone()
        _wconn.close()

        existing_reserved_paise = int(existing_res["amount"]) if existing_res else 0
        new_bid_paise = wallet_service.rupees_to_paise(amount)
        additional_needed = wallet_service.paise_to_rupees(
            max(0, new_bid_paise - existing_reserved_paise)
        )

        if additional_needed > available:
            conn.close()
            return jsonify({
                "success": False,
                "message": (
                    f"Insufficient wallet balance. "
                    f"You need ₹{additional_needed:,.2f} more. "
                    f"Available: ₹{available:,.2f}. "
                    f"Please add funds to your wallet."
                )
            }), 400
        # ──────────────────────────────────────────────────────────────────────

        conn.close()  # Close before Java call to avoid holding connections

        # Send bid to Java engine for authoritative validation
        engine_result = place_bid_in_engine(auction_id, bidder_name, amount)

        if engine_result.get("success"):
            # ── Reserve wallet funds (exclusive, atomic) ───────────────────────
            reserve_result = wallet_service.reserve_for_bid(user_id, auction_id, amount)
            if not reserve_result.get("success"):
                # Java accepted but wallet reservation failed — return error
                # The Java engine's bid will be the latest accepted but we don't
                # persist to DB; user should retry.
                logger.error(
                    f"Wallet reservation failed after Java accepted bid: "
                    f"user={user_id}, auction={auction_id}, amount={amount}, "
                    f"error={reserve_result.get('error')}"
                )
                return jsonify({
                    "success": False,
                    "message": reserve_result.get("error", "Wallet reservation failed")
                }), 400
            # ──────────────────────────────────────────────────────────────────

            conn2 = get_connection()
            conn2.execute(
                "INSERT INTO bids (auction_id, user_id, bidder_name, amount) VALUES (?, ?, ?, ?)",
                (auction_id, user_id, bidder_name, amount)
            )
            conn2.execute(
                "UPDATE auctions SET current_highest_bid = ? WHERE id = ?",
                (amount, auction_id)
            )
            conn2.commit()
            conn2.close()
            return jsonify({
                "success": True,
                "message": "Bid accepted",
                "highestBid": amount,
                "wallet_reserved": reserve_result.get("reserved_total", amount)
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": engine_result.get("message", "Bid rejected by auction engine")
            }), 400

    except Exception as e:
        logger.error(f"place_bid error: {e}")
        return jsonify({"success": False, "message": "An internal error occurred. Please try again."}), 500


# ============================================
# GET /api/auctions/<id>/bids — Get bid history
# ============================================
@auction_bp.route('/auctions/<int:auction_id>/bids', methods=['GET'])
def get_bids(auction_id):
    try:
        conn = get_connection()
        auction = conn.execute("SELECT id FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        if not auction:
            conn.close()
            return jsonify({"error": "Auction not found"}), 404

        rows = conn.execute(
            "SELECT * FROM bids WHERE auction_id = ? ORDER BY amount DESC, created_at ASC",
            (auction_id,)
        ).fetchall()
        conn.close()

        bids = [{
            "id": row["id"],
            "bidder_name": row["bidder_name"],
            "amount": row["amount"],
            "created_at": row["created_at"]
        } for row in rows]

        return jsonify(bids)
    except Exception as e:
        logger.error(f"get_bids error: {e}")
        return jsonify({"error": "Failed to retrieve bids"}), 500


# ============================================
# GET /api/auctions/<id>/queue — Get Java PriorityQueue contents
# ============================================
@auction_bp.route('/auctions/<int:auction_id>/queue', methods=['GET'])
def get_auction_queue(auction_id):
    """
    Returns the exact contents of the PriorityQueue for the specified auction.
    Prefers Java engine's live PriorityQueue, falls back to SQLite DB if Java is offline.
    """
    from services.java_bridge import get_bids_from_engine
    try:
        # Try fetching from Java engine first
        java_queue = get_bids_from_engine(auction_id)
        if java_queue and java_queue.get("success"):
            return jsonify({
                "source": "java_priority_queue",
                "auction_id": auction_id,
                "size": java_queue.get("totalBids", 0),
                "bids": java_queue.get("queue", [])
            })

        # Fallback to database if Java is offline or hasn't loaded this auction yet
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM bids WHERE auction_id = ? ORDER BY amount DESC, created_at ASC",
            (auction_id,)
        ).fetchall()
        conn.close()

        bids = [{
            "bidderName": row["bidder_name"],
            "amount": row["amount"],
            "timestamp": row["created_at"]
        } for row in rows]

        return jsonify({
            "source": "sqlite_database",
            "auction_id": auction_id,
            "size": len(bids),
            "bids": bids
        })
    except Exception as e:
        logger.error(f"get_auction_queue error: {e}")
        return jsonify({"error": "Failed to retrieve auction queue"}), 500


# ============================================
# POST /api/demo/seed — Seed demo data (ADMIN ONLY)
# ============================================
@auction_bp.route('/demo/seed', methods=['POST'])
@require_admin
def seed_demo():
    """Seed standard realistic demo auctions and sync to Java engine. Admin only."""
    from database.db import seed_demo_data
    try:
        seeded = seed_demo_data(force=True)
        # Sync all auctions to Java engine
        conn = get_connection()
        rows = conn.execute("SELECT id FROM auctions").fetchall()
        conn.close()

        for row in rows:
            sync_single_auction_to_java(row["id"])

        return jsonify({"success": True, "message": "Demo data seeded and synced to Java engine."})
    except Exception as e:
        logger.error(f"seed_demo error: {e}")
        return jsonify({"success": False, "message": "Internal error seeding demo data"}), 500


# ============================================
# POST /api/auctions/<id>/sync — Sync single auction to Java
# ============================================
@auction_bp.route('/auctions/<int:auction_id>/sync', methods=['POST'])
def sync_auction_endpoint(auction_id):
    """Re-synchronize an auction and its bids from SQLite to Java memory."""
    try:
        result = sync_single_auction_to_java(auction_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"sync_auction_endpoint error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500



# ============================================
# POST /api/auctions/<id>/start — Force start
# ============================================
@auction_bp.route('/auctions/<int:auction_id>/start', methods=['POST'])
@require_admin
def start_auction(auction_id):
    try:
        conn = get_connection()
        auction = conn.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        if not auction:
            conn.close()
            return jsonify({"error": "Auction not found"}), 404

        # Bug Fix #3: Cannot start if end_time is already in the past
        end_dt = parse_datetime(auction["end_time"])
        if end_dt and end_dt <= datetime.now():
            conn.close()
            return jsonify({"error": "Cannot start auction: end time is already in the past"}), 409

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE auctions SET start_time = ? WHERE id = ?", (now_str, auction_id))
        conn.commit()
        conn.close()

        sync_single_auction_to_java(auction_id)
        return jsonify({"message": "Auction started", "start_time": now_str})
    except Exception as e:
        logger.error(f"start_auction error: {e}")
        return jsonify({"error": "Failed to start auction"}), 500


# ============================================
# POST /api/auctions/<id>/end — Force end
# ============================================
@auction_bp.route('/auctions/<int:auction_id>/end', methods=['POST'])
@require_admin
def end_auction(auction_id):
    try:
        conn = get_connection()
        auction = conn.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        if not auction:
            conn.close()
            return jsonify({"error": "Auction not found"}), 404

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE auctions SET end_time = ? WHERE id = ?", (now_str, auction_id))
        conn.commit()

        # Identify winner (highest bid for this auction)
        winner_bid = conn.execute("""
            SELECT b.user_id, b.bidder_name, b.amount
            FROM bids b
            WHERE b.auction_id = ? AND b.user_id IS NOT NULL
            ORDER BY b.amount DESC, b.created_at ASC
            LIMIT 1
        """, (auction_id,)).fetchone()

        # Get all unique bidders for this auction
        all_bidders = conn.execute("""
            SELECT DISTINCT user_id FROM bids
            WHERE auction_id = ? AND user_id IS NOT NULL
        """, (auction_id,)).fetchall()
        conn.close()

        settlement_result = None
        if winner_bid and winner_bid["user_id"]:
            winning_user_id = winner_bid["user_id"]
            winning_amount  = winner_bid["amount"]

            # Settle payment for winner (idempotent)
            ikey = f"WIN-{winning_user_id}-{auction_id}"
            settlement_result = wallet_service.settle_auction_winner(
                winning_user_id, auction_id, winning_amount, ikey
            )
            if not settlement_result.get("success"):
                if settlement_result.get("flag_for_review"):
                    logger.error(
                        f"WALLET REVIEW REQUIRED: auction={auction_id}, "
                        f"winner={winning_user_id}, amount={winning_amount}. "
                        f"Error: {settlement_result.get('error')}"
                    )
                # Don't block end_auction — flag but continue

            # Release reservations for all losing bidders
            for bidder_row in all_bidders:
                bid_user_id = bidder_row["user_id"]
                if bid_user_id != winning_user_id:
                    wallet_service.release_bid_reservation(bid_user_id, auction_id)

        sync_single_auction_to_java(auction_id)
        response = {"message": "Auction ended", "end_time": now_str}
        if settlement_result:
            response["settlement"] = settlement_result
        return jsonify(response)
    except Exception as e:
        logger.error(f"end_auction error: {e}")
        return jsonify({"error": "Failed to end auction"}), 500


# ============================================
# POST /api/auctions/<id>/simulate-concurrent-bids
# ============================================
@auction_bp.route('/auctions/<int:auction_id>/simulate-concurrent-bids', methods=['POST'])
@require_admin
def simulate_bids(auction_id):
    try:
        conn = get_connection()
        auction = conn.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)).fetchone()
        if not auction:
            conn.close()
            return jsonify({"success": False, "message": "Auction not found"}), 404

        status = compute_status(auction["start_time"], auction["end_time"])
        if status != "ACTIVE":
            conn.close()
            return jsonify({"success": False, "message": f"Auction is {status}. Must be ACTIVE to simulate."}), 409

        data = request.get_json(silent=True)
        if not data or "bidders" not in data:
            conn.close()
            return jsonify({"success": False, "message": "Missing bidders list"}), 400

        bidders = data["bidders"]
        if not isinstance(bidders, list) or len(bidders) == 0:
            conn.close()
            return jsonify({"success": False, "message": "Bidders must be a non-empty list"}), 400

        # Validate each bidder entry
        validated_bidders = []
        for i, b in enumerate(bidders):
            if not isinstance(b, dict):
                conn.close()
                return jsonify({"success": False, "message": f"Bidder {i+1} is invalid"}), 400
            name = str(b.get("name", "")).strip()
            if not name:
                conn.close()
                return jsonify({"success": False, "message": f"Bidder {i+1} is missing a name"}), 400
            try:
                amount = float(b.get("amount", 0))
                if amount <= 0:
                    raise ValueError("non-positive")
            except (ValueError, TypeError):
                conn.close()
                return jsonify({"success": False, "message": f"Bidder {i+1} has an invalid amount"}), 400
            validated_bidders.append({"name": name, "amount": amount})

        # Cap at 50 threads to prevent overload
        if len(validated_bidders) > 50:
            conn.close()
            return jsonify({"success": False, "message": "Maximum 50 bidder threads per simulation"}), 400

        # Bug Fix #4: Close connection BEFORE calling Java (which can take time)
        conn.close()

        result = simulate_concurrent_bids(auction_id, validated_bidders)

        if result.get("success"):
            # Reopen connection for DB writes only after Java is done
            conn2 = get_connection()
            try:
                current_highest = auction["current_highest_bid"]
                for r in result.get("results", []):
                    if r.get("status") == "ACCEPTED":
                        conn2.execute(
                            "INSERT INTO bids (auction_id, bidder_name, amount) VALUES (?, ?, ?)",
                            (auction_id, r["bidder"], r["amount"])
                        )
                        if r["amount"] > current_highest:
                            current_highest = r["amount"]
                conn2.execute(
                    "UPDATE auctions SET current_highest_bid = ? WHERE id = ?",
                    (current_highest, auction_id)
                )
                conn2.commit()
            finally:
                conn2.close()

        return jsonify(result)

    except Exception as e:
        logger.error(f"simulate_bids error: {e}")
        return jsonify({"success": False, "message": "Simulation failed. Internal server error."}), 500
