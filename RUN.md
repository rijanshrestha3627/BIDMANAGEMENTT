# Running the University Auction Bid Management System

This document is the **single source of truth** for running the project locally.

## Project Requirements
- **Python**: 3.8 or higher
- **Java**: JDK 11 or higher
- **Packages**: `flask`, `flask-cors`, `werkzeug` (see `python-backend/requirements.txt`)

## First-Time Setup

1. **Install Python dependencies:**
   ```powershell
   cd python-backend
   pip install -r requirements.txt
   ```
2. **Configure environment variables:**
   - Copy `.env.example` to `.env` in the root directory.
   - Leave default values for local development. Do not use real credentials.
3. **Compile Java (if necessary):**
   - The `.class` files may already be compiled in `java-engine/src/engine`. 
   - If not, navigate to `java-engine` and run `javac -d bin src/engine/*.java`.
4. **Database:**
   - The SQLite database is automatically initialized at `python-backend/database/auction.db` when Flask starts.

## Startup Instructions

You must start the application in the following order. You can use the provided PowerShell helper scripts, or run the exact commands below in separate terminal windows.

### 1. Start the Java Engine
The Java engine must be running *before* Flask so that Flask can synchronize the auction state to Java memory on startup.

Using the helper script:
```powershell
.\run-java.ps1
```

Or using the exact command:
```powershell
cd java-engine
java -cp src engine.Main
```
*(Runs on port 9090)*

### 2. Start the Flask Backend
Using the helper script:
```powershell
.\run-backend.ps1
```

Or using the exact command:
```powershell
cd python-backend
python app.py
```
*(Runs on port 5000)*

### 3. Start the Frontend
Using the helper script:
```powershell
.\run-frontend.ps1
```

Or using the exact command:
```powershell
cd frontend
python -m http.server 5500
```
*(Runs on port 5500)*

## Test URLs
- **Main (User View):** http://localhost:5500/index.html
- **User Login:** http://localhost:5500/login.html
- **User Profile:** http://localhost:5500/profile.html
- **Admin Login:** http://localhost:5500/admin-login.html
- **Admin Dashboard:** http://localhost:5500/admin.html
- **Backend API:** http://localhost:5000
- **Java Health Check:** http://localhost:9090/health

## Default Development Admin
The system will automatically seed a default admin user if the database is empty:
- **Email:** `admin@example.com`
- **Password:** `admin123`

**⚠️ WARNING:** This is for DEVELOPMENT ONLY. Production credentials MUST be changed via environment variables (`ADMIN_EMAIL`, `ADMIN_PASSWORD`) before deployment.

## Troubleshooting

- **"Java port 9090 already in use"**
  - The Java engine is already running in another terminal. Find the process and kill it (e.g., `netstat -ano | findstr :9090` and then `taskkill /PID <PID> /F`).
- **"Flask port 5000 already in use" / "Frontend port 5500 already in use"**
  - Same as above; kill the existing Python processes.
- **CORS Issues**
  - Ensure you are accessing the frontend via `http://localhost:5500` exactly (not `127.0.0.1` or `0.0.0.0`, unless configured in Flask). Credentials require exact origin matches.
- **"Java engine offline" warning in Flask logs**
  - Start the Java engine, then restart the Flask server. Flask needs to sync the existing auctions to Java on startup.
- **Database locked**
  - This can happen if multiple Flask instances are trying to write to the SQLite database. Ensure only one Flask server is running.
- **Missing Python dependencies**
  - Run `pip install flask flask-cors werkzeug` in the `python-backend` directory.
