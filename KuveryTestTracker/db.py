"""Database connection helpers."""
import psycopg2
import psycopg2.extras
from flask import g

from config import DSN


def db():
    if "db" not in g:
        g.db = psycopg2.connect(DSN, cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db


def close_db(_=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_app(app):
    """Close the connection at the end of every request."""
    app.teardown_appcontext(close_db)


def q(sql, args=(), one=False, commit=False):
    with db().cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall() if cur.description else []
    if commit:
        db().commit()
    return (rows[0] if rows else None) if one else rows
