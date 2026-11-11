import os
import smtplib
from email.message import EmailMessage

def send_otp_email(to_email, otp, subject="Your Verification Code"):
    """
    Sends an OTP email. Uses environment variables for configuration.
    If not configured, it will simulate sending (for local development).
    """
    mail_host = os.environ.get('MAIL_HOST')
    mail_port = os.environ.get('MAIL_PORT', 587)
    mail_username = os.environ.get('MAIL_USERNAME')
    mail_password = os.environ.get('MAIL_PASSWORD')
    mail_from = os.environ.get('MAIL_FROM', 'noreply@universityauctions.com')

    if not mail_host or not mail_username or not mail_password:
        # DEV MODE: OTP delivery is not configured.
        # Mask the OTP in output to prevent accidental log exposure.
        masked = otp[:2] + ('*' * (len(otp) - 2)) if len(otp) > 2 else '****'
        print(f"[DEV] Email not configured. OTP {masked} would be sent to {to_email} with subject '{subject}'.")
        print("[DEV] Set MAIL_HOST, MAIL_USERNAME, MAIL_PASSWORD in .env to enable delivery.")
        return False

    msg = EmailMessage()
    
    # Clean professional email content
    body = f"""University Auctions

Your verification code is:

{otp}

This code expires in 10 minutes.

If you did not request this verification, you can safely ignore this email."""

    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = mail_from
    msg['To'] = to_email

    try:
        server = smtplib.SMTP(mail_host, int(mail_port))
        server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
