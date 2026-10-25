"""File attachments on test cases (images, PDFs, documents and so on).

Upload / delete: Test Lead, and QA / Automation Engineers on their own cases.
Download: anyone who is allowed to see the case.
"""
import os
import re
import uuid

from flask import Blueprint, jsonify, request, send_from_directory

import config
from db import db, q
from helpers import can_upload, fail, fetch_cases, login_required

bp = Blueprint("files", __name__)


def clean_name(name):
    """Keep the person's file name for display, minus any folder part or odd characters."""
    name = os.path.basename((name or "").replace("\\", "/"))
    name = "".join(ch for ch in name if ch.isprintable()).strip(" .")
    stem, ext = os.path.splitext(name)
    return (stem[:120] + ext[:15]) if stem else ""


def case_for(me, cid):
    rows = fetch_cases(me, cid)           # also enforces who may see the case
    if not rows:
        fail(404, "Case not found")
    return rows[0]


def files_json(me, case):
    rows = q("SELECT id, uploaded_by, uploader_name, original_name, mime_type, size_bytes, created_at "
             "FROM attachments WHERE case_id=%s ORDER BY id", (case["id"],))
    upload = can_upload(me, case)
    for r in rows:
        r["can_delete"] = case["status"] not in config.LOCKED_STATUSES and (
            me["role"] == "Test Lead" or (upload and r["uploaded_by"] == me["id"]))
    return {"can_upload": upload, "max_mb": config.MAX_UPLOAD_MB, "files": rows}


@bp.get("/api/cases/<int:cid>/files")
def list_files(cid):
    me = login_required()
    return jsonify(files_json(me, case_for(me, cid)))


@bp.post("/api/cases/<int:cid>/files")
def upload_files(cid):
    me = login_required()
    case = case_for(me, cid)
    if not can_upload(me, case):
        fail(403, "Only the Test Lead or the assigned tester can upload files")
    incoming = [f for f in request.files.getlist("file") if f and f.filename]
    if not incoming:
        fail(400, "Choose a file to upload")
    for f in incoming:
        name = clean_name(f.filename)
        if not name:
            fail(400, "Invalid file name")
        if os.path.splitext(name)[1].lower() in config.BLOCKED_EXTENSIONS:
            fail(400, f"{name}: this file type is not allowed")
    saved = []
    try:
        for f in incoming:
            name = clean_name(f.filename)
            ext = os.path.splitext(name)[1].lower()
            stored = uuid.uuid4().hex + (ext if re.fullmatch(r"\.[a-z0-9]{1,10}", ext) else "")
            path = os.path.join(config.UPLOAD_DIR, stored)
            f.save(path)
            saved.append(path)
            size = os.path.getsize(path)
            if size == 0:
                fail(400, f"{name} is empty")
            q("INSERT INTO attachments (case_id, uploaded_by, uploader_name, original_name, stored_name, "
              "mime_type, size_bytes) VALUES (%s,%s,%s,%s,%s,%s,%s)",
              (cid, me["id"], me["name"], name, stored, f.mimetype, size))
        db().commit()
    except BaseException:
        db().rollback()
        for path in saved:                  # do not leave orphan files behind
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    return jsonify(files_json(me, case)), 201


@bp.get("/api/files/<int:fid>/download")
def download_file(fid):
    me = login_required()
    row = q("SELECT case_id, original_name, stored_name, mime_type FROM attachments WHERE id=%s", (fid,), one=True)
    if not row:
        fail(404, "File not found")
    case_for(me, row["case_id"])
    resp = send_from_directory(config.UPLOAD_DIR, row["stored_name"], as_attachment=True,
                               download_name=row["original_name"], mimetype=row["mime_type"] or None)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@bp.delete("/api/files/<int:fid>")
def delete_file(fid):
    me = login_required()
    row = q("SELECT id, case_id, uploaded_by, stored_name FROM attachments WHERE id=%s", (fid,), one=True)
    if not row:
        fail(404, "File not found")
    case = case_for(me, row["case_id"])
    if case["status"] in config.LOCKED_STATUSES or not (
            me["role"] == "Test Lead" or (can_upload(me, case) and row["uploaded_by"] == me["id"])):
        fail(403, "You cannot delete this file")
    q("DELETE FROM attachments WHERE id=%s", (fid,), commit=True)
    try:
        os.remove(os.path.join(config.UPLOAD_DIR, row["stored_name"]))
    except OSError:
        pass
    return "", 204
