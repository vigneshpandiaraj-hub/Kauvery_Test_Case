"""Home page, sign in / sign out, and the signed-in user's own profile."""
from flask import Blueprint, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash

from db import q
from helpers import fail, hash_pw, login_required, me_json

bp = Blueprint("auth", __name__)


@bp.get("/")
def index():
    return send_from_directory("static", "index.html")


# ---------- sign in ----------
@bp.post("/api/login")
def login():
    d = request.get_json(force=True)
    username = (d.get("username") or "").strip().lower()
    m = q("SELECT * FROM members WHERE lower(username)=%s", (username,), one=True)
    if not m or not m["password_hash"] or not check_password_hash(m["password_hash"], d.get("password") or ""):
        fail(401, "Wrong username or password")
    if not m.get("active", True):
        fail(403, "This account is inactive. Ask the Test Lead.")
    session.clear()
    session["uid"] = m["id"]
    return jsonify(me_json(m))


@bp.post("/api/logout")
def logout():
    session.clear()
    return "", 204


@bp.get("/api/me")
def me():
    return jsonify(me_json(login_required()))


@bp.post("/api/me/password")
def change_password():
    m = login_required()
    d = request.get_json(force=True)
    row = q("SELECT password_hash FROM members WHERE id=%s", (m["id"],), one=True)
    if not check_password_hash(row["password_hash"], d.get("old") or ""):
        fail(400, "Current password is wrong")
    new = d.get("new") or ""
    if len(new) < 6:
        fail(400, "New password must be at least 6 characters")
    q("UPDATE members SET password_hash=%s WHERE id=%s", (hash_pw(new), m["id"]), commit=True)
    return jsonify(ok=True)
