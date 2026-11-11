# Gmail SMTP OTP Setup Guide

This document explains how to configure the University Auction Bid Management System to send real One-Time Passwords (OTPs) via Gmail SMTP for email verification and password resets.

## IMPORTANT SECURITY WARNING
**NEVER use your primary Gmail account password.**
You must generate a specific "App Password" to allow the application to send emails securely without exposing your main account credentials.

## Step 1: Enable 2-Step Verification
To use App Passwords, your Google account must have 2-Step Verification enabled.
1. Go to your Google Account (https://myaccount.google.com/).
2. On the left navigation panel, choose **Security**.
3. Under "How you sign in to Google," select **2-Step Verification** and turn it on (follow the on-screen prompts).

## Step 2: Create an App Password
1. In your Google Account Security settings, use the search bar at the top and type **App passwords**.
2. Alternatively, go directly to https://myaccount.google.com/apppasswords.
3. You will be prompted to enter a name for the app (e.g., "University Auctions").
4. Click **Create**.
5. A 16-character password will be generated (e.g., `abcd efgh ijkl mnop`).

## Step 3: Configure `.env`
Create a `.env` file in the root of the project (if you haven't already by copying `.env.example`).
Update the Email / OTP section with your credentials:

```env
# ── Email / OTP ───────────────────────────────────────────────────────────────
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your.actual.email@gmail.com
MAIL_PASSWORD=abcdefghijklmnop   # The 16-character app password (no spaces)
MAIL_FROM=your.actual.email@gmail.com
```

## Step 4: Verification
1. Restart the Flask Python backend.
2. The terminal should log: `✓ SMTP email service configured.`
3. Test the flow by attempting to change your email in the profile or requesting a password reset. You should receive a professional email with a 6-digit verification code.

## Troubleshooting
- **"Unable to send verification email"**: Double-check that `MAIL_PASSWORD` has no spaces. Ensure `MAIL_USERNAME` exactly matches the account that generated the app password.
- **Port Issues**: Ensure port 587 is not blocked by your university/corporate firewall.
- **File Not Ignored**: Never commit the `.env` file to version control. It is already included in `.gitignore`.
