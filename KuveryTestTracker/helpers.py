"""Shared helpers: errors, sign-in checks, who can see / do what on a case."""
from flask import abort, jsonify, make_response, session
from werkzeug.security import generate_password_hash

from config import CASE_CREATORS, LOCKED_STATUSES, TESTERS, UPLOADERS
from db import q


def fail(code, msg):
    abort(make_response(jsonify(error=msg), code))


def hash_pw(pw):
    return generate_password_hash(pw, method="pbkdf2:sha256")


def me_json(m):
    return {"id": m["id"], "name": m["name"], "username": m["username"], "role": m["role"],
            "can_add_case": m["role"] in CASE_CREATORS}


def current():
    uid = session.get("uid")
    if not uid:
        return None
    return q("SELECT id, name, username, role FROM members WHERE id=%s AND active", (uid,), one=True)


def login_required():
    m = current()
    if not m:
        session.clear()
        fail(401, "Please sign in")
    return m


def lead_only():
    m = login_required()
    if m["role"] != "Test Lead":
        fail(403, "Only a Test Lead can do this")
    return m


def admin_only():
    """Team and Masters screens (members, branches, modules, team leaders) belong to the Admin."""
    m = login_required()
    if m["role"] != "Admin":
        fail(403, "Only an Admin can do this")
    return m


def last_admin(member_id):
    m = q("SELECT role FROM members WHERE id=%s", (member_id,), one=True)
    n = q("SELECT count(*) AS n FROM members WHERE role='Admin' AND active", one=True)["n"]
    return bool(m) and m["role"] == "Admin" and n < 2


def last_lead(member_id):
    m = q("SELECT role FROM members WHERE id=%s", (member_id,), one=True)
    n = q("SELECT count(*) AS n FROM members WHERE role='Test Lead' AND active", one=True)["n"]
    return bool(m) and m["role"] == "Test Lead" and n < 2


def scope(me):
    """Which cases this person may see. Testers and developers only see their own.
    Promotion sees every Passed/Deployed case, as a shared queue."""
    if me["role"] in TESTERS:
        return "c.tester_id = %s", (me["id"],)
    if me["role"] == "Developer":
        return "(c.developer_id = %s OR c.created_by = %s)", (me["id"], me["id"])
    if me["role"] == "Team Leader":  # pending cases of developers who report to this leader, and the ones this leader approved
        return ("((c.status IN ('Pending Approval', 'On Hold') AND (d.reports_to = %s OR d.reports_to IS NULL)) OR EXISTS (SELECT 1 FROM remarks r "
                "WHERE r.case_id = c.id AND r.action = 'approve' AND r.author_id = %s))"), (me["id"], me["id"])
    if me["role"] == "Support":      # deployed cases (to refer to) and the follow-ups they raised
        return "(c.status = 'Deployed' OR c.created_by = %s)", (me["id"],)
    if me["role"] == "Promotion":
        return "c.status IN ('Passed', 'Deploy Failed', 'Deployed')", ()
    return "TRUE", ()          # Admin, Test Lead and Viewer see everything (Admin and Viewer are read only)


def allowed(me, case):
    """Workflow actions this person can take on this case right now."""
    lead = me["role"] == "Test Lead"
    is_tester = lead or (me["role"] in TESTERS and case["tester_id"] == me["id"])
    is_dev = lead or (me["role"] == "Developer" and case["developer_id"] == me["id"])
    is_leader = me["role"] == "Team Leader"
    is_promo = me["role"] == "Promotion"       # deploying is the promotion team's job, not the Test Lead's
    st, acts = case["status"], []
    if st == "On Hold":                            # frozen: only the Test Lead can bring it back
        return ["resume", "cancel"] if lead else []
    if is_tester:
        if st in ("Not run", "Blocked"):
            acts.append("start")
        if st in ("Not run", "In progress", "Fixed", "Returned"):
            acts += ["pass", "fail", "clarify"]
        if st in ("Not run", "In progress"):
            acts.append("duplicate")               # the tester decides whether it is a duplicate
            if case.get("dup_of_id"):
                acts.append("not_dup")
    if is_dev and st == "Clarification":
        acts.append("clarified")
    if is_leader and st == "Pending Approval" and case.get("dev_leader_id") in (None, me["id"]):
        acts.append("approve")             # only the team leader the developer reports to (any leader if none is set)
    if lead and st not in ("Cancelled", "Duplicate") + LOCKED_STATUSES:
        acts += ["hold", "cancel"]                 # cancel replaces delete / block: the case stays on record
    if is_dev and st == "Failed":
        acts.append("fix")
    if me["role"] == "Developer" and case["developer_id"] == me["id"] and st == "Failed":
        acts.append("reject")                      # "this is not a failure" - back to the tester
    if is_dev and st == "Deploy Failed":
        acts.append("deploy_fix")
    if is_promo and st == "Passed":
        acts += ["deploy", "deploy_fail"]
    return acts


def can_upload(me, case):
    """Test Lead can attach files to any case; a tester only to a case assigned to them."""
    if case["status"] in LOCKED_STATUSES:       # approved: nobody changes it any more
        return False
    if me["role"] == "Test Lead":
        return True
    return me["role"] in UPLOADERS and case["tester_id"] == me["id"]


BASE_SQL = ("SELECT c.id, 'TC-' || (100 + c.id) AS code, c.title, c.screen, c.priority, "
            "c.tester_id, c.developer_id, t.name AS tester_name, d.name AS developer_name, d.reports_to AS dev_leader_id, "
            "c.branch_id, br.name AS branch_name, c.module_id, mo.description AS module_desc, "
            "c.status, c.created_at, c.fail_count, c.deploy_fail_count, c.ref_case_id, c.hold_prev_status, c.clarify_prev_status, c.created_by, c.dup_of_id, "
            "CASE WHEN c.dup_of_id IS NULL THEN NULL ELSE 'TC-' || (100 + c.dup_of_id) END AS dup_code, "
            "CASE WHEN c.ref_case_id IS NULL THEN NULL ELSE 'TC-' || (100 + c.ref_case_id) END AS ref_code, "
            "(SELECT string_agg('TC-' || (100 + f.id), ', ' ORDER BY f.id) FROM cases f WHERE f.ref_case_id = c.id) AS followup_codes "
            "FROM cases c "
            "LEFT JOIN members t ON t.id = c.tester_id LEFT JOIN members d ON d.id = c.developer_id "
            "LEFT JOIN branches br ON br.id = c.branch_id LEFT JOIN modules mo ON mo.id = c.module_id ")


def date_filter(args_get, col="c.created_at"):
    """From / To (YYYY-MM-DD, both days included) -> extra SQL and its arguments."""
    import re
    sql, args = "", []
    f, t = (args_get("from") or "").strip(), (args_get("to") or "").strip()
    for val, name in ((f, "From"), (t, "To")):
        if val and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", val):
            fail(400, f"{name} date is not valid")
    if f and t and f > t:
        fail(400, "The From date is after the To date")
    if f:
        sql += f" AND {col} >= %s::date"
        args.append(f)
    if t:
        sql += f" AND {col} < %s::date + 1"
        args.append(t)
    return sql, args


def page_args(args_get, default=25):
    try:
        page, size = max(int(args_get("page") or 1), 1), int(args_get("size") or default)
    except ValueError:
        fail(400, "Invalid page")
    return page, min(max(size, 5), 200)


def fetch_cases_page(me, args_get):
    """One page of cases (newest first) for the From / To / status filter, plus counts per status for the whole filter."""
    cond, args = scope(me)
    dsql, dargs = date_filter(args_get)
    cond, args = cond + dsql, list(args) + dargs
    counts = {r["status"]: r["n"] for r in q(
        "SELECT c.status, count(*) AS n FROM cases c LEFT JOIN members d ON d.id = c.developer_id WHERE " + cond +
        " GROUP BY c.status", tuple(args))}
    status = args_get("status")
    total = counts.get(status, 0) if status else sum(counts.values())
    if status:
        cond += " AND c.status = %s"
        args.append(status)
    page, size = page_args(args_get)
    pages = max((total + size - 1) // size, 1)
    page = min(page, pages)
    rows = q(BASE_SQL + "WHERE " + cond + " ORDER BY c.id DESC LIMIT %s OFFSET %s", tuple(args + [size, (page - 1) * size]))
    for r in rows:
        r["actions"] = allowed(me, r)
    return {"items": rows, "total": total, "counts": counts, "page": page, "size": size, "pages": pages}


def fetch_cases(me, cid=None):
    cond, args = scope(me)
    args = list(args)
    if cid is not None:
        cond += " AND c.id = %s"
        args.append(cid)
    rows = q(BASE_SQL + "WHERE " + cond + " ORDER BY c.id", tuple(args))
    for r in rows:
        r["actions"] = allowed(me, r)
    return rows


def member_with_role(mid, roles, keep=None):
    """Check a person may be given a field. `keep` = the person already in it (allowed even if now inactive)."""
    if not mid:
        return None
    m = q("SELECT id, role, active FROM members WHERE id=%s", (mid,), one=True)
    if not m or m["role"] not in roles:
        fail(400, "That person does not have the right role for this field")
    if not m["active"] and mid != keep:
        fail(400, "That person is inactive. Choose someone active.")
    return m["id"]


def case_id_from_code(text):
    """'TC-105' or '105' -> case id 5 (codes are 100 + id). None if it does not look like a case number."""
    import re
    m = re.fullmatch(r"\s*(?:TC-?)?(\d+)\s*", str(text or ""), re.I)
    return int(m.group(1)) - 100 if m and int(m.group(1)) > 100 else None


# ---------- notifications ----------
def leader_ids_for(developer_id):
    """Who approves this developer's cases: the team leader tagged to them, else every active Team Leader."""
    row = q("SELECT l.id FROM members d JOIN members l ON l.id = d.reports_to "
            "WHERE d.id=%s AND l.active AND l.role='Team Leader'", (developer_id,), one=True) if developer_id else None
    return [row["id"]] if row else ids_with_role("Team Leader")


def ids_with_role(role):
    return [r["id"] for r in q("SELECT id FROM members WHERE role=%s AND active", (role,))]


def notify(user_ids, case_id, kind, text, actor_id=None):
    """Tell each person (never the person who did the action). The caller commits."""
    import mailer
    ids = {u for u in user_ids if u and u != actor_id}
    if ids:                                          # inactive people are not notified
        ids = {r["id"] for r in q("SELECT id FROM members WHERE id = ANY(%s) AND active", (list(ids),))}
    for uid in ids:
        q("INSERT INTO notifications (user_id, case_id, kind, message) VALUES (%s,%s,%s,%s)",
          (uid, case_id, kind, text[:300]))
    if ids and mailer.enabled():
        try:
            people = q("SELECT name, email FROM members WHERE id = ANY(%s) AND coalesce(email, '') <> ''", (list(ids),))
            mailer.send_many([(p["email"], "[Test Tracker] " + text[:80], f"Hello {p['name']},\n\n{text}")
                              for p in people])
        except Exception as e:                      # noqa: BLE001
            print("Email skipped:", e)
