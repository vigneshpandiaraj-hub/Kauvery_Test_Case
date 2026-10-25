"""Optional email sending (SMTP). Never raises: a mail problem must not stop a test action."""
import smtplib
import threading
from email.message import EmailMessage

import config


def enabled():
    return bool(config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASSWORD)


def status():
    """What is missing, in plain words (used by the Admin email check and printed at start-up)."""
    missing = [n for n, v in (("SMTP_HOST", config.SMTP_HOST), ("SMTP_USER", config.SMTP_USER),
                              ("SMTP_PASSWORD", config.SMTP_PASSWORD)) if not v]
    if missing:
        return False, "Email is OFF. Not set: " + ", ".join(missing) + ". Set them in the same window where you run python app.py."
    return True, f"Email is ON ({config.SMTP_USER} via {config.SMTP_HOST}:{config.SMTP_PORT})."


def send_test(to):
    """Send one message right now and return None if it worked, else the real error text."""
    ok, why = status()
    if not ok:
        return why
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = config.SMTP_FROM, to, "[Test Tracker] Test email"
    m.set_content("This is a test email from the Test Tracker. If you can read it, email notifications work.")
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
            if config.SMTP_TLS:
                s.starttls()
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(m)
    except smtplib.SMTPAuthenticationError:
        return "Login refused. For Gmail use a 16-character App Password (2-Step Verification must be on), not your normal password."
    except Exception as e:                                   # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    return None


def _send(messages):
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
            if config.SMTP_TLS:
                s.starttls()
            if config.SMTP_USER and config.SMTP_PASSWORD:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            for m in messages:
                s.send_message(m)
    except Exception as e:                                   # noqa: BLE001 - log and carry on
        print("Email not sent:", e)


def send_many(items):
    """items: list of (to_address, subject, body). Sent in the background."""
    if not enabled() or not items:
        return
    msgs = []
    for to, subject, body in items:
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = config.SMTP_FROM, to, subject
        m.set_content(body + "\n\nOpen the tracker: " + config.APP_URL)
        msgs.append(m)
    threading.Thread(target=_send, args=(msgs,), daemon=True).start()
