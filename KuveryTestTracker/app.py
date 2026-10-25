"""Test case tracker: Flask + PostgreSQL.

Run with:  python app.py
Settings are in config.py, the database helpers in db.py, shared rules in helpers.py,
and the web routes are split by area in the routes/ folder.
"""
import os

import psycopg2
from flask import Flask, jsonify

import config
import db
from db import db as get_db, q
from helpers import hash_pw
from routes import auth, cases, files, masters, members, notifications, reports


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.secret_key = config.SECRET_KEY
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      MAX_CONTENT_LENGTH=config.MAX_UPLOAD_MB * 1024 * 1024)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    db.init_app(app)
    for module in (auth, members, masters, cases, files, reports, notifications):
        app.register_blueprint(module.bp)

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(error=f"Upload is too large (limit {config.MAX_UPLOAD_MB} MB)"), 413
    return app


app = create_app()


def ensure_default_passwords():
    """Give every member without a password the default one (they can change it in Profile)."""
    with app.app_context():
        for m in q("SELECT id FROM members WHERE password_hash IS NULL"):
            q("UPDATE members SET password_hash=%s WHERE id=%s", (hash_pw(config.DEFAULT_PASSWORD), m["id"]))
        get_db().commit()


if __name__ == "__main__":
    try:
        ensure_default_passwords()
    except psycopg2.Error as e:
        print("Could not reach the database:", e)
    import mailer
    print(mailer.status()[1])
    app.run(debug=True, port=5000)
