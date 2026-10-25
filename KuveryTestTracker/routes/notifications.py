"""In-app notifications: what moved to me, newest first."""
from flask import Blueprint, jsonify, request

import mailer
from db import db, q
from helpers import admin_only, fail, login_required

bp = Blueprint("notifications", __name__)


@bp.get("/api/notifications")
def list_notifications():
    m = login_required()
    items = q("SELECT id, case_id, kind, message, is_read, created_at FROM notifications "
              "WHERE user_id=%s ORDER BY id DESC LIMIT 50", (m["id"],))
    unread = q("SELECT count(*) AS n FROM notifications WHERE user_id=%s AND NOT is_read", (m["id"],), one=True)["n"]
    return jsonify(items=items, unread=unread)


@bp.post("/api/notifications/read")
def mark_read():
    """Body {id} marks one as read; no id marks all of my notifications."""
    m = login_required()
    nid = (request.get_json(silent=True) or {}).get("id")
    if nid:
        q("UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND id=%s", (m["id"], nid))
    else:
        q("UPDATE notifications SET is_read=TRUE WHERE user_id=%s", (m["id"],))
    db().commit()
    return "", 204


@bp.get("/api/email/status")
def email_status():
    admin_only()
    ok, text = mailer.status()
    return jsonify(enabled=ok, text=text,
                   without_email=[r["name"] for r in q("SELECT name FROM members WHERE active AND coalesce(email,'')=''")])


@bp.post("/api/email/test")
def email_test():
    """Admin: send one real email now and show the real error if it fails."""
    m = admin_only()
    to = ((request.get_json(silent=True) or {}).get("to") or "").strip()
    if not to:
        row = q("SELECT email FROM members WHERE id=%s", (m["id"],), one=True)
        to = (row["email"] or "").strip()
    if not to:
        fail(400, "Type an email address to send the test to")
    err = mailer.send_test(to)
    if err:
        fail(502, err)
    return jsonify(ok=True, to=to)
