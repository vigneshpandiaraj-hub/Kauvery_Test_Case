"""Run a .sql file on the tracker database without needing psql.
Usage (in the project folder, with the venv active):
    python run_sql.py migration_notifications.sql
Uses the same database address as the app (config.py / DATABASE_URL).
"""
import sys

import psycopg2

from config import DSN

if len(sys.argv) != 2:
    sys.exit("Usage: python run_sql.py <file.sql>")
sql = open(sys.argv[1], encoding="utf-8").read()
conn = psycopg2.connect(DSN)
try:
    with conn, conn.cursor() as cur:       # all-or-nothing: commits at the end, rolls back on error
        cur.execute(sql)
    print("Done:", sys.argv[1])
except psycopg2.Error as e:
    sys.exit(f"Failed, nothing was changed: {e}")
finally:
    conn.close()
