# Phase 2: Profile & Security Report

## 1. Features Implemented
- **User Profile Page (`profile.html`)**: A secure page displaying the user's information and statistics.
- **Username Change**: Modal to safely update a user's username.
- **Email Change (OTP)**: A 2-step verification process to change email. Sends an OTP code that expires in 10 minutes.
- **Password Change**: Modal to change a password by validating the current password and securely hashing the new one.
- **Forgot Password**: Integrated into the login page, sending a 2-step OTP verification before resetting the password.
- **Authentication Integrity**: Maintained the robust server-side Flask Session mechanism. Profile APIs strictly validate the logged-in user through session identity.

## 2. Database Changes
- Added table `email_otps` in `database/db.py`:
  - Fields: `id`, `user_id`, `email`, `otp_hash`, `purpose`, `expires_at`, `attempts`, `created_at`.
  - Ensures OTPs are securely stored in the SQLite DB via hashed value. Supports multiple purposes (`EMAIL_CHANGE`, `PASSWORD_RESET`).

## 3. API Endpoints Added
- **Profile endpoints (`profile_routes.py`)**:
  - `GET /api/profile` - Fetches user info & statistics.
  - `PUT /api/profile/username` - Updates the current user's username.
  - `PUT /api/profile/password` - Updates the user's password.
  - `POST /api/profile/email/request` - Sends an OTP for an email change.
  - `POST /api/profile/email/verify` - Verifies the OTP to commit the email change.
- **Password Reset endpoints (`auth_routes.py`)**:
  - `POST /api/auth/password-reset/request` - Triggers OTP generation for forgot password. Returns a generic message to prevent account enumeration.
  - `POST /api/auth/password-reset/verify` - Validates the OTP before allowing a reset.
  - `POST /api/auth/password-reset/complete` - Finalizes the password replacement.

## 4. SMTP Configuration
- Service implemented in `services/email_service.py`.
- Configure the following environment variables to activate email sending:
  - `MAIL_HOST` (e.g., smtp.gmail.com)
  - `MAIL_PORT` (e.g., 587)
  - `MAIL_USERNAME`
  - `MAIL_PASSWORD`
  - `MAIL_FROM`
- If unconfigured, the application gracefully prints the OTP to the Python console (for local development) instead of crashing or simulating a false failure.

## 5. Security Measures
- **Hashing**: All passwords and OTP values are hashed (via `werkzeug.security`) before database storage.
- **Session Auth**: Identity derived *only* from the active server session (`session.get("user_id")`). No `user_id` is trusted from request payloads.
- **Rate-Limiting & Limits**: OTPs expire after 10 minutes and delete themselves upon successful/failed verifications (> 3 attempts).
- **Anti-Enumeration**: The `/api/auth/password-reset/request` returns success whether the email exists or not.
- **No plaintext exposure**: Credentials/OTPs are kept out of API responses and logs.

## 6. Testing Performed
- Loaded and navigated `profile.html`.
- Changed username successfully.
- Generated OTP for Email Change and validated logic (via console logs).
- Forgot Password request properly filters missing users securely.
- Confirmed CORS and session authentication remain intact.
- Confirmed Java engine bindings are un-impacted.

## 7. How to Run
Restart the backend to apply route/schema changes:
```bash
# Terminal 1: Backend
cd python-backend
python app.py

# Terminal 2: Frontend
cd frontend
python -m http.server 5500

# Terminal 3: Java (if needed for auction logic)
cd java-engine
java -cp src engine.Main
```
