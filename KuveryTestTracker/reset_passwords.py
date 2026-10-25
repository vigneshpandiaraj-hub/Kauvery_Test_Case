"""Reset passwords to the default (pass123) without typing any SQL.
Usage (project folder, venv active):
    python reset_passwords.py            # everyone
    python reset_passwords.py alex       # just one user
"""
import sys

import psycopg2
from werkzeug.security import generate_password_hash

from config import DEFAULT_PASSWORD, DSN

who = sys.argv[1].strip().lower() if len(sys.argv) > 1 else None
conn = psycopg2.connect(DSN)
try:
    with conn, conn.cursor() as cur:
        h = generate_password_hash(DEFAULT_PASSWORD, method="pbkdf2:sha256")
        if who:
            cur.execute("UPDATE members SET password_hash=%s WHERE lower(username)=%s", (h, who))
        else:
            cur.execute("UPDATE members SET password_hash=%s", (h,))
        print(f"Password reset to '{DEFAULT_PASSWORD}' for {cur.rowcount} user(s).")
finally:
    conn.close()
