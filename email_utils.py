import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)


def email_configured():
    return all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD])


def send_email(to_address, subject, body):
    """Send a plain-text email. Returns True on success, False otherwise.

    Requires SMTP_HOST, SMTP_USER, SMTP_PASSWORD (and optionally SMTP_PORT,
    SMTP_FROM) to be set as environment variables. See README.md for setup
    with common providers (Gmail app password, SendGrid, etc.).
    """
    if not email_configured():
        raise RuntimeError(
            "Email is not configured. Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD "
            "environment variables (see README.md)."
        )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_address

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to_address], msg.as_string())

    return True
