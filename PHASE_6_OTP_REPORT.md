# Phase 6 — OTP Email System Report

## 1. Overview
The University Auction Bid Management System has been upgraded to support real OTP (One-Time Password) email delivery via Gmail SMTP. This functionality protects the Email Change and Password Reset flows. The implementation preserves all existing Java auction engine logic, UI designs, and database schemas.

## 2. SMTP Implementation
- **Provider:** Gmail SMTP (`smtp.gmail.com:587`).
- **Security:** STARTTLS is used for secure transmission.
- **Authentication:** Gmail App Passwords are required to prevent exposing primary account passwords.
- **Configuration:** Credentials are read strictly from the `.env` file (`MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`).
- **Startup Validation:** The Flask application checks for SMTP configuration on startup and logs either `✓ SMTP email service configured.` or `⚠ SMTP email service not configured.` without crashing the auction functionality.

## 3. OTP Generation & Storage
- **Generation:** Cryptographically secure OTPs are generated using Python's `secrets.choice` to ensure a strict 6-digit numeric format (e.g., `048291`), preserving leading zeroes.
- **Hashing:** OTPs are never stored in plaintext. They are hashed using Werkzeug's `generate_password_hash` before insertion into the `email_otps` SQLite table.
- **Separation of Concerns:** The `purpose` column strictly separates `EMAIL_CHANGE` from `PASSWORD_RESET` OTPs.

## 4. OTP Lifecycle & Security
- **Expiration:** OTPs strictly expire 10 minutes after generation.
- **Attempt Limits:** A maximum of 3 incorrect attempts is enforced. On the 3rd failure, the OTP is deleted/invalidated.
- **Resend Cooldown:** A 60-second cooldown is enforced server-side before a new OTP can be requested.
- **Cleanup:** Upon successful verification, expiration, or maximum attempts, the OTP record is purged from the database to prevent accumulation.
- **Anti-Enumeration:** The Password Reset request returns a generic success message ("If the account exists, a verification code has been sent.") regardless of whether the email is registered in the system.

## 5. UI Updates
- **Design:** The OTP input interface has been updated to feature a prominent, centered, monospace 6-digit input field.
- **Timer:** A real-time countdown timer (10:00) displays the expiration window.
- **Resend Mechanism:** A dynamic "Resend code (60s)" button unlocks only after the 60-second cooldown expires.

## 6. Email Content
Emails are formatted cleanly without exposing internal server data:
```
University Auctions

Your verification code is:
[123456]

This code expires in 10 minutes.

If you did not request this verification, you can safely ignore this email.
```
- Custom subjects are applied dynamically depending on the flow ("University Auctions — Verify Your New Email" vs. "University Auctions — Password Reset OTP").

## 7. Failure Handling
- If SMTP authentication fails or network issues occur, the backend cleanly returns: `Unable to send verification email. Please try again later.`
- The stack trace and SMTP credentials are NOT exposed to the client or the development console.
- In development mode without an `.env` file, the OTP is masked in the terminal log (e.g., `OTP 82**** would be sent...`) to prevent accidental log leakage.

## 8. Files Changed
1. `python-backend/app.py` (Added startup SMTP config check)
2. `python-backend/services/email_service.py` (Cleaned email body, custom subjects, failure catching)
3. `python-backend/routes/auth_routes.py` (Secure OTP generation, 60s cooldown, password reset flow)
4. `python-backend/routes/profile_routes.py` (Secure OTP generation, 60s cooldown, email change flow)
5. `frontend/login.html` (OTP UI, 6-digit input, timer)
6. `frontend/profile.html` (OTP UI, 6-digit input, timer)
7. `frontend/js/auth.js` (Countdown timer logic, Resend OTP hook)
8. `frontend/js/profile.js` (Countdown timer logic, Resend OTP hook)
9. `.env.example` (Updated SMTP block)
10. `OTP_SETUP.md` (Created documentation)

## 9. Tests Performed
- **TEST:** Startup logging validates `.env` presence.
- **TEST:** `EMAIL_CHANGE` generates a secure OTP and sends an email via Gmail SMTP.
- **TEST:** 60-second resend cooldown successfully blocks rapid requests.
- **TEST:** Incorrect OTP increments attempt counter and returns generic failure.
- **TEST:** 3rd incorrect OTP deletes the record.
- **TEST:** Correct OTP successfully changes the user's email and deletes the OTP record.
- **TEST:** `PASSWORD_RESET` sends OTP without confirming email existence.
- **TEST:** Passwords successfully update via validated OTP.
- **TEST:** `EMAIL_CHANGE` OTP cannot authorize a `PASSWORD_RESET`.
- **TEST:** Network/SMTP failure safely returns a generic error string.

## 10. Known Limitations
- The system still relies on synchronous SMTP blocking calls during the HTTP request. For a high-traffic production system, email dispatch should be offloaded to a background task queue (e.g., Celery or Redis).
- Expiration cleanup is currently lazy (deleted upon access attempt). A background cron job would be needed to automatically delete stale OTPs from the database if they are never accessed.
