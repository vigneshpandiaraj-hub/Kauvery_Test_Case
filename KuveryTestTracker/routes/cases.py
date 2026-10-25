"""Test cases, the pass / fail workflow, and remarks."""
import os

from flask import Blueprint, jsonify, request

from config import (CASE_CREATORS, LOCKED_STATUSES, NEW_STATUS, PRIORITIES, TESTER_ASSIGNABLE, TESTERS,
                    UPLOAD_DIR)
from db import db, q
from helpers import (case_id_from_code, fail, fetch_cases, fetch_cases_page, ids_with_role, lead_only, leader_ids_for,
                     login_required, member_with_role, notify)

bp = Blueprint("cases", __name__)


# ---------- cases ----------
@bp.get("/api/cases")
def list_cases():
    """With ?page= the answer is one page: {items, total, counts, page, size, pages}. Filters: from, to, status."""
    me = login_required()
    if request.args.get("page"):
        return jsonify(fetch_cases_page(me, request.args.get))
    return jsonify(fetch_cases(me))


@bp.get("/api/cases/<int:cid>")
def one_case(cid):
    rows = fetch_cases(login_required(), cid)
    return jsonify(rows[0]) if rows else fail(404, "Case not found")


@bp.post("/api/cases")
def add_case():
    m = login_required()
    if m["role"] not in CASE_CREATORS:
        fail(403, "Your role cannot add cases")
    d = request.get_json(force=True)
    title, screen = (d.get("title") or "").strip(), (d.get("screen") or "").strip()
    priority = d.get("priority", "Medium")
    if not title or not screen or priority not in PRIORITIES:
        fail(400, "Description, screen name and a valid priority are required")
    branch_id, module_id = d.get("branch_id"), d.get("module_id")
    if not branch_id or not q("SELECT 1 FROM branches WHERE id=%s AND active", (branch_id,), one=True):
        fail(400, "Choose a valid branch")
    if not module_id or not q("SELECT 1 FROM modules WHERE id=%s AND active", (module_id,), one=True):
        fail(400, "Choose a valid module")
    ref_id = d.get("ref_case_id")
    if m["role"] == "Support" and not ref_id:
        fail(403, "Support can only raise a follow-up case from a deployed case")
    if ref_id and m["role"] != "Support":
        fail(403, "Only the Support team can raise a follow-up case")
    if ref_id and not isinstance(ref_id, int):
        fail(400, "Invalid reference case")
    if ref_id:
        ref = fetch_cases(m, ref_id)           # you can only refer to a case you are allowed to see
        if not ref:
            fail(400, "The case you are referring to was not found")
        if ref[0]["status"] not in ("Passed", "Deployed"):
            fail(400, "A follow-up case can only refer to a case that is Passed or Deployed")
        if m["role"] == "Support" and ref[0]["status"] != "Deployed":
            fail(400, "Support can raise a follow-up only on a deployed case")
    dup_id = None
    if (d.get("dup_of") or "").strip():
        dup_id = case_id_from_code(d["dup_of"])
        if not dup_id or not q("SELECT 1 FROM cases WHERE id=%s", (dup_id,), one=True):
            fail(400, "The 'possible duplicate of' case number was not found")
    # Testers are their own tester; Developer / Support cases wait for the Test Lead to choose a tester.
    if m["role"] in TESTERS:
        tester = m["id"]
    elif m["role"] in ("Developer", "Support"):
        tester = None
    else:
        tester = member_with_role(d.get("tester_id"), TESTER_ASSIGNABLE)
    if m["role"] == "Developer":
        dev = m["id"]
    elif m["role"] == "Support":
        dev = None
    else:
        dev = member_with_role(d.get("developer_id"), ("Developer",))
    row = q("INSERT INTO cases (title, screen, priority, tester_id, developer_id, branch_id, module_id, ref_case_id, created_by, dup_of_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (title, screen, priority, tester, dev, branch_id, module_id, ref_id or None, m["id"], dup_id), one=True)
    code = f"TC-{100 + row['id']}"
    if tester:
        notify([tester], row["id"], "assign", f"{code} was assigned to you to test: {title}", m["id"])
    if dev:
        notify([dev], row["id"], "assign", f"{code} was assigned to you: {title}", m["id"])
    if m["role"] in ("Developer", "Support"):
        notify(ids_with_role("Test Lead"), row["id"], "assign",
               f"{code} was added by {m['name']} ({m['role']}) and needs a tester: {title}", m["id"])
    if dup_id:
        notify([tester] if tester else ids_with_role("Test Lead"), row["id"], "info",
               f"{code} may be a duplicate of TC-{100 + dup_id}. Please decide.", m["id"])
    if ref_id:      # leave a note in the old case's history
        q("INSERT INTO remarks (case_id, author_id, author_name, author_role, action, round, text) "
          "VALUES (%s,%s,%s,%s,'followup',0,%s)",
          (ref_id, m["id"], m["name"], m["role"], f"Follow-up case TC-{100 + row['id']} created: {title}"))
    db().commit()
    return jsonify(fetch_cases(m, row["id"])[0]), 201


@bp.patch("/api/cases/<int:cid>")
def assign_case(cid):
    """Test Lead assigns the tester and/or the developer."""
    m = lead_only()
    d = request.get_json(force=True)
    before = fetch_cases(m, cid)
    if not before:
        fail(404, "Case not found")
    before, code = before[0], before[0]["code"]
    if before["status"] in LOCKED_STATUSES:
        fail(409, "This case has been approved and is with the deployment team. It can no longer be changed.")
    if "tester_id" in d:
        new_t = member_with_role(d["tester_id"], TESTER_ASSIGNABLE)
        if new_t != before["tester_id"]:
            notify([new_t], cid, "assign", f"{code} was assigned to you to test: {before['title']}", m["id"])
        q("UPDATE cases SET tester_id=%s, updated_at=now() WHERE id=%s",
          (new_t, cid))
    if "developer_id" in d:
        new_d = member_with_role(d["developer_id"], ("Developer",))
        if new_d != before["developer_id"]:
            notify([new_d], cid, "assign", f"{code} was assigned to you: {before['title']}", m["id"])
        q("UPDATE cases SET developer_id=%s, updated_at=now() WHERE id=%s",
          (new_d, cid))
    if "branch_id" in d:
        if not q("SELECT 1 FROM branches WHERE id=%s", (d["branch_id"],), one=True):
            fail(400, "Invalid branch")
        q("UPDATE cases SET branch_id=%s, updated_at=now() WHERE id=%s", (d["branch_id"], cid))
    if "module_id" in d:
        if not q("SELECT 1 FROM modules WHERE id=%s", (d["module_id"],), one=True):
            fail(400, "Invalid module")
        q("UPDATE cases SET module_id=%s, updated_at=now() WHERE id=%s", (d["module_id"], cid))
    db().commit()
    return jsonify(fetch_cases(m, cid)[0])


@bp.delete("/api/cases/<int:cid>")
def delete_case(cid):
    lead_only()
    stored = [r["stored_name"] for r in q("SELECT stored_name FROM attachments WHERE case_id=%s", (cid,))]
    q("DELETE FROM cases WHERE id=%s", (cid,), commit=True)      # attachment rows go with it (ON DELETE CASCADE)
    for name in stored:
        try:
            os.remove(os.path.join(UPLOAD_DIR, name))
        except OSError:
            pass
    return "", 204


@bp.post("/api/cases/<int:cid>/transition")
def transition(cid):
    """start / pass / fail / fix / block, with a remark."""
    m = login_required()
    rows = fetch_cases(m, cid)
    if not rows:
        fail(404, "Case not found")
    case = rows[0]
    d = request.get_json(force=True)
    action, remark = d.get("action"), (d.get("remark") or "").strip()
    if action not in case["actions"]:
        fail(403, "You cannot do that on this case right now")
    if action not in ("start", "pass", "resume", "approve") and not remark:
        fail(400, "A remark is required")
    fails, dfails, dev = case["fail_count"], case["deploy_fail_count"], case["developer_id"]
    round_num = fails
    if action == "fail":
        dev = member_with_role(d.get("developer_id") or dev, ("Developer",), keep=case["developer_id"])
        if not dev:
            fail(400, "Choose a developer to send this case to")
        fails += 1
        round_num = fails
    if action == "reject":
        fails = max(fails - 1, 0)                  # Failed 3 -> Failed 2; round_num keeps the number that was rejected
    if action == "clarify":
        dev = member_with_role(d.get("developer_id") or dev, ("Developer",), keep=case["developer_id"])
        if not dev:
            fail(400, "Choose the developer who can clarify this")
    if action == "deploy_fail":
        dev = member_with_role(d.get("developer_id") or dev, ("Developer",), keep=case["developer_id"])
        if not dev:
            fail(400, "Choose a developer to send this deployment issue to")
        dfails += 1
        round_num = dfails
    if action == "deploy_fix":
        round_num = dfails
    new_status, dup_id = NEW_STATUS.get(action, case["status"]), case["dup_of_id"]
    hold_prev = case["hold_prev_status"]
    if action == "hold":
        hold_prev = case["status"]                 # remember where it was
    if action == "resume":
        new_status, hold_prev = case["hold_prev_status"] or "Not run", None
    clar_prev = case["clarify_prev_status"]
    if action == "clarify":
        clar_prev = case["status"]                 # where the tester was when asking
    if action == "clarified":
        new_status, clar_prev = case["clarify_prev_status"] or "In progress", None
    if action == "duplicate":
        dup_id = dup_id or case_id_from_code(d.get("dup_of"))
        if not dup_id or dup_id == cid or not q("SELECT 1 FROM cases WHERE id=%s", (dup_id,), one=True):
            fail(400, "Enter the number of the case this duplicates (for example TC-105)")
        remark = f"Duplicate of TC-{100 + dup_id}. {remark}"
    if action == "not_dup":
        dup_id = None
    q("UPDATE cases SET status=%s, fail_count=%s, deploy_fail_count=%s, developer_id=%s, dup_of_id=%s, hold_prev_status=%s, clarify_prev_status=%s, updated_at=now() "
      "WHERE id=%s", (new_status, fails, dfails, dev, dup_id, hold_prev, clar_prev, cid))
    code, short = case["code"], (remark or "")[:120]
    pair = [case["tester_id"], dev]
    leads = ids_with_role("Test Lead")
    plan = {
        "pass": (leader_ids_for(dev), "pass", f"{code} passed testing and is waiting for your approval."),
        "approve": (ids_with_role("Promotion") + pair, "pass", f"{code} was approved by {m['name']} and is ready to deploy."),
        "clarify": ([dev], "ask", f"{code}: the tester needs a clarification. {short}"),
        "clarified": ([case["tester_id"]], "fix", f"{code} was clarified. Please carry on. {short}"),
        "fail": ([dev], "fail", f"{code} failed (Failed {fails}). Please fix. {short}"),
        "reject": ([case["tester_id"]], "ret", f"{code}: the developer says it is not a failure (back to Failed {fails}). Please check. {short}"),
        "fix": ([case["tester_id"]], "fix", f"{code} was fixed. Please retest. {short}"),
        "deploy": (pair + leads, "deploy", f"{code} was deployed."),
        "deploy_fail": ([dev], "fail", f"{code} deployment failed. Please fix. {short}"),
        "deploy_fix": (ids_with_role("Promotion"), "fix", f"{code} deployment issue fixed. Ready to redeploy."),
        "hold": (pair, "hold", f"{code} was put on hold by the Test Lead. {short}"),
        "resume": (pair, "assign", f"{code} was resumed. Carry on."),
        "cancel": (pair, "hold", f"{code} was cancelled by the Test Lead. {short}"),
        "duplicate": ([case["created_by"]] + leads, "info", f"{code} was closed as a duplicate."),
        "not_dup": ([case["created_by"]] + leads, "info", f"{code} is not a duplicate. Testing carries on."),
    }
    if action in plan:
        who, kind, text = plan[action]
        notify(who, cid, kind, text, m["id"])
    if action != "start" or remark:
        q("INSERT INTO remarks (case_id, author_id, author_name, author_role, action, round, text) "
          "VALUES (%s,%s,%s,%s,%s,%s,%s)", (cid, m["id"], m["name"], m["role"], action, round_num, remark))
    db().commit()
    return jsonify(fetch_cases(m, cid)[0])


@bp.get("/api/cases/<int:cid>/remarks")
def list_remarks(cid):
    m = login_required()
    if not fetch_cases(m, cid):
        fail(404, "Case not found")
    return jsonify(q("SELECT id, author_name, author_role, action, round, text, created_at "
                     "FROM remarks WHERE case_id=%s ORDER BY id", (cid,)))
