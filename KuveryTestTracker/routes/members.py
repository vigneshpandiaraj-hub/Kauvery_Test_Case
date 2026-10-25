"""Team members (Admin only) and the names used in the assign drop-downs."""
import re

import psycopg2.errors
from flask import Blueprint, jsonify, request

from config import ROLES, TESTERS
from db import db, q
from helpers import admin_only, fail, hash_pw, last_admin, last_lead, login_required

bp = Blueprint("members", __name__)


def clean_email(value):
    value = (value or "").strip()
    if value and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        fail(400, "That email address does not look right")
    return value or None


# ---------- members (Admin only) ----------
@bp.get("/api/members")
def list_members():
    admin_only()
    return jsonify(q("SELECT id, name, username, role, email, reports_to, active FROM members ORDER BY id"))


@bp.post("/api/members")
def add_member():
    admin_only()
    d = request.get_json(force=True)
    name, role = (d.get("name") or "").strip(), d.get("role")
    username, pw = (d.get("username") or "").strip().lower(), d.get("password") or ""
    email = clean_email(d.get("email"))
    if not name or not username or role not in ROLES:
        fail(400, "Name, username and a valid role are required")
    if len(pw) < 6:
        fail(400, "Password must be at least 6 characters")
    try:
        row = q("INSERT INTO members (name, username, role, password_hash, email) VALUES (%s,%s,%s,%s,%s) "
                "RETURNING id, name, username, role, email", (name, username, role, hash_pw(pw), email), one=True, commit=True)
    except psycopg2.errors.UniqueViolation:
        db().rollback()
        fail(409, "That username is already taken")
    return jsonify(row), 201


@bp.patch("/api/members/<int:mid>")
def update_member(mid):
    admin_id = admin_only()["id"]
    d = request.get_json(force=True)
    if "role" in d:
        if d["role"] not in ROLES:
            fail(400, "Invalid role")
        if d["role"] != "Test Lead" and last_lead(mid):
            fail(409, "The team needs at least one Test Lead")
        if d["role"] != "Admin" and last_admin(mid):
            fail(409, "There must be at least one Admin")
        q("UPDATE members SET role=%s WHERE id=%s", (d["role"], mid))
        if d["role"] != "Team Leader":              # nobody can keep a team leader who is no longer one
            q("UPDATE members SET reports_to=NULL WHERE reports_to=%s", (mid,))
    if "name" in d:
        if not (d["name"] or "").strip():
            fail(400, "Name cannot be empty")
        q("UPDATE members SET name=%s WHERE id=%s", (d["name"].strip(), mid))
    if "active" in d:
        if not d["active"]:
            if mid == admin_id:
                fail(409, "You cannot make yourself inactive")
            if last_lead(mid):
                fail(409, "The team needs at least one active Test Lead")
            if last_admin(mid):
                fail(409, "There must be at least one active Admin")
            q("UPDATE members SET reports_to=NULL WHERE reports_to=%s", (mid,))
        q("UPDATE members SET active=%s WHERE id=%s", (bool(d["active"]), mid))
    if "reports_to" in d:
        boss = d["reports_to"]
        if boss:
            if boss == mid or not q("SELECT 1 FROM members WHERE id=%s AND active AND role='Team Leader'", (boss,), one=True):
                fail(400, "Choose an active Team Leader")
        q("UPDATE members SET reports_to=%s WHERE id=%s", (boss or None, mid))
    if "email" in d:
        q("UPDATE members SET email=%s WHERE id=%s", (clean_email(d["email"]), mid))
    if "password" in d:
        if len(d["password"] or "") < 6:
            fail(400, "Password must be at least 6 characters")
        q("UPDATE members SET password_hash=%s WHERE id=%s", (hash_pw(d["password"]), mid))
    db().commit()
    row = q("SELECT id, name, username, role, email, reports_to, active FROM members WHERE id=%s", (mid,), one=True)
    return jsonify(row) if row else fail(404, "Member not found")


@bp.delete("/api/members/<int:mid>")
def delete_member(mid):
    m = admin_only()
    if mid == m["id"]:
        fail(409, "You cannot remove yourself")
    if last_lead(mid):
        fail(409, "The team needs at least one Test Lead")
    if last_admin(mid):
        fail(409, "There must be at least one Admin")
    q("DELETE FROM members WHERE id=%s", (mid,), commit=True)
    return "", 204


@bp.get("/api/people")
def people():
    """Names for the assign drop-downs. Each role only gets the names it needs."""
    m = login_required()
    if m["role"] == "Test Lead":
        roles = ["QA Engineer", "Automation Engineer", "Test Lead", "Developer"]
    elif m["role"] in TESTERS or m["role"] == "Promotion":
        roles = ["Developer"]
    else:
        return jsonify([])
    return jsonify(q("SELECT id, name, role FROM members WHERE role = ANY(%s) AND active ORDER BY id", (roles,)))
