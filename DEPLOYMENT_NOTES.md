# Deployment Notes

**STATUS: NOT CURRENTLY DEPLOYED**

The University Auction Bid Management System is currently architected and configured for **local development and academic demonstration**. It utilizes separate ports for the frontend (5500), Flask backend (5000), and Java engine (9090). 

To deploy this application to a production environment (e.g., AWS, DigitalOcean, Heroku, or a university server), several architectural changes and configuration updates must be made.

## 1. Environment Variables
Before deployment, a `.env` file must be created on the production server (never commit this file to version control). The following variables are absolutely required:

- `SECRET_KEY`: Must be a long, cryptographically secure random string (used for signing Flask session cookies).
- `FRONTEND_ORIGIN`: Must be set to the exact public URL of the frontend (e.g., `https://auction.myschool.edu`) to allow CORS with credentials.
- `ADMIN_EMAIL` & `ADMIN_PASSWORD`: Must be set to secure values. The default `admin123` is strictly for local testing.

## 2. Server Architecture
The local 3-server setup is not viable for production.

### Reverse Proxy (Nginx)
A reverse proxy like Nginx must be placed in front of the application. It will:
- Serve the static frontend HTML/CSS/JS files directly.
- Terminate SSL/HTTPS.
- Route `/api/*` traffic internally to the Flask backend.

### WSGI Server (Gunicorn)
Flask's built-in development server (which prints `WARNING: This is a development server`) cannot be used in production.
- Flask must be run using a production WSGI server like Gunicorn or uWSGI.
- Example: `gunicorn -w 4 -b 127.0.0.1:5000 app:app`

### Java Engine Daemon
The Java engine must be run as a background service (e.g., using `systemd` on Linux) to ensure it stays alive and restarts on failure.

## 3. Persistent Storage
- **Database:** The SQLite file (`auction.db`) must be stored on a persistent volume. If deploying to ephemeral containers (like Heroku or Docker without volumes), the database will be wiped on restart. For scalable cloud deployments, migrating from SQLite to PostgreSQL is highly recommended.
- **Image Uploads:** The `python-backend/uploads/` directory must also be on a persistent volume. Alternatively, the image upload logic should be refactored to use a cloud storage provider like AWS S3.

## 4. Security Enhancements
- **HTTPS:** SSL certificates (e.g., Let's Encrypt) are mandatory. Browsers will reject cross-origin cookies in production without `Secure=True` and HTTPS.
- **Session Cookies:** In `app.py`, `SESSION_COOKIE_SECURE` must be changed from `False` to `True`.
- **CORS:** Ensure `FRONTEND_ORIGIN` precisely matches the deployed URL. Do not use wildcard `*` for authenticated routes.

## 5. Email & OTP Verification
The OTP email infrastructure is currently deferred. To activate it in production:
1. Obtain an SMTP provider (e.g., SendGrid, Mailgun, or an App Password for a Gmail account).
2. Configure `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, and `MAIL_PASSWORD` in the production environment.
3. Remove development masking logs in `email_service.py`.

## Summary of Deployment Blockers
1. Needs Nginx + Gunicorn setup.
2. Needs HTTPS/SSL certificates.
3. Needs `SESSION_COOKIE_SECURE=True`.
4. Needs strong `SECRET_KEY` and changed admin passwords.
5. Needs persistent volume configuration for SQLite and uploads.
