"""Masters: branches and modules (read: anyone signed in, write: Admin)."""
import psycopg2.errors
from flask import Blueprint, jsonify, request

from db import db, q
from helpers import admin_only, fail, login_required

bp = Blueprint("masters", __name__)


# ---------- masters: branches and modules (read: anyone signed in, write: Admin) ----------
@bp.get("/api/branches")
def list_branches():
    m = login_required()
    where = "" if m["role"] == "Admin" else "WHERE active "      # everyone else sees active ones only
    return jsonify(q("SELECT id, name, active FROM branches " + where + "ORDER BY name"))


@bp.post("/api/branches")
def add_branch():
    admin_only()
    name = ((request.get_json(force=True)).get("name") or "").strip()
    if not name:
        fail(400, "Branch name is required")
    try:
        row = q("INSERT INTO branches (name) VALUES (%s) RETURNING id, name", (name,), one=True, commit=True)
    except psycopg2.errors.UniqueViolation:
        db().rollback()
        fail(409, "That branch already exists")
    return jsonify(row), 201


@bp.patch("/api/branches/<int:bid>")
def update_branch(bid):
    admin_only()
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    if not name:
        fail(400, "Branch name is required")
    try:
        q("UPDATE branches SET name=%s, active=%s WHERE id=%s", (name, bool(d.get("active", True)), bid), commit=True)
    except psycopg2.errors.UniqueViolation:
        db().rollback()
        fail(409, "That branch already exists")
    row = q("SELECT id, name, active FROM branches WHERE id=%s", (bid,), one=True)
    return jsonify(row) if row else fail(404, "Branch not found")


@bp.delete("/api/branches/<int:bid>")
def delete_branch(bid):
    admin_only()
    q("UPDATE cases SET branch_id=NULL WHERE branch_id=%s", (bid,))
    q("DELETE FROM branches WHERE id=%s", (bid,), commit=True)
    return "", 204


@bp.get("/api/modules")
def list_modules():
    m = login_required()
    where = "" if m["role"] == "Admin" else "WHERE active "
    return jsonify(q("SELECT id, description, active FROM modules " + where + "ORDER BY description"))


@bp.post("/api/modules")
def add_module():
    admin_only()
    description = ((request.get_json(force=True)).get("description") or "").strip()
    if not description:
        fail(400, "Module name is required")
    try:
        row = q("INSERT INTO modules (description) VALUES (%s) RETURNING id, description",
                (description,), one=True, commit=True)
    except psycopg2.errors.UniqueViolation:
        db().rollback()
        fail(409, "That module already exists")
    return jsonify(row), 201


@bp.patch("/api/modules/<int:mid>")
def update_module(mid):
    admin_only()
    d = request.get_json(force=True)
    description = (d.get("description") or "").strip()
    if not description:
        fail(400, "Module name is required")
    try:
        q("UPDATE modules SET description=%s, active=%s WHERE id=%s", (description, bool(d.get("active", True)), mid), commit=True)
    except psycopg2.errors.UniqueViolation:
        db().rollback()
        fail(409, "That module already exists")
    row = q("SELECT id, description, active FROM modules WHERE id=%s", (mid,), one=True)
    return jsonify(row) if row else fail(404, "Module not found")


@bp.delete("/api/modules/<int:mid>")
def delete_module(mid):
    admin_only()
    q("UPDATE cases SET module_id=NULL WHERE module_id=%s", (mid,))
    q("DELETE FROM modules WHERE id=%s", (mid,), commit=True)
    return "", 204
