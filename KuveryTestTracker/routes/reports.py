"""Test report and CSV download."""
import csv
import io

from flask import Blueprint, Response, jsonify, request

from db import q
from helpers import date_filter, login_required, page_args, scope

bp = Blueprint("reports", __name__)


# ---------- report ----------
def status_label(st, fails, dfails):
    if st == "Failed":
        return f"Failed {fails}"
    if st == "Fixed":
        return "Fixed, retest"
    if st == "Returned":
        return "Returned to tester"
    if st == "Deploy Failed":
        return f"Deploy failed {dfails}"
    return st


def fmt_date(dt):
    return dt.strftime("%d/%m/%Y") if dt else None


def fmt_dt(dt):
    """Date and time, e.g. 25/10/2026 14:35 (the time zone of the database server)."""
    return dt.strftime("%d/%m/%Y %H:%M") if dt else None


def report_rows(me, paged=False):
    cond, args = scope(me)
    args = list(args)
    if request.args.get("status"):
        cond += " AND c.status = %s"
        args.append(request.args["status"])
    if request.args.get("screen"):
        cond += " AND c.screen = %s"
        args.append(request.args["screen"])
    dsql, dargs = date_filter(request.args.get)
    cond, args = cond + dsql, args + dargs
    total = q("SELECT count(*) AS n FROM cases c LEFT JOIN members d ON d.id = c.developer_id WHERE " + cond,
              tuple(args), one=True)["n"] if paged else None
    tail = ""
    if paged:
        page, size = page_args(request.args.get, 50)
        page = min(page, max((total + size - 1) // size, 1))
        tail, args = " LIMIT %s OFFSET %s", args + [size, (page - 1) * size]
    sql = ("SELECT 'TC-' || (100 + c.id) AS test_id, c.title AS description, c.screen, "
           "COALESCE(br.name, 'Unassigned') AS branch, COALESCE(mo.description, 'Unassigned') AS module, "
           "COALESCE(d.name, 'Unassigned') AS assigned_to, COALESCE(t.name, 'Unassigned') AS tester, "
           "c.status, c.fail_count, c.deploy_fail_count, c.updated_at, "
           "CASE WHEN c.ref_case_id IS NULL THEN '' ELSE 'TC-' || (100 + c.ref_case_id) END AS ref_code, "
           "CASE WHEN c.dup_of_id IS NULL THEN '' ELSE 'TC-' || (100 + c.dup_of_id) END AS dup_code, "
           "(SELECT MIN(created_at) FROM remarks WHERE case_id = c.id AND action = 'start') AS start_date, "
           "(SELECT MAX(created_at) FROM remarks WHERE case_id = c.id AND action = 'fix') AS fixed_date, "
           "(SELECT MAX(created_at) FROM remarks WHERE case_id = c.id AND action = 'deploy') AS deploy_time, "
           "(SELECT string_agg('Deploy failed ' || round || ': ' || text, ' | ' ORDER BY id) "
           " FROM remarks WHERE case_id = c.id AND action = 'deploy_fail') AS deploy_fail_details "
           "FROM cases c "
           "LEFT JOIN members t ON t.id = c.tester_id LEFT JOIN members d ON d.id = c.developer_id "
           "LEFT JOIN branches br ON br.id = c.branch_id LEFT JOIN modules mo ON mo.id = c.module_id "
           "WHERE " + cond + " ORDER BY c.id" + (" DESC" if paged else "") + tail)
    rows = q(sql, tuple(args))
    for r in rows:
        raw_status = r["status"]
        r["status"] = status_label(raw_status, r["fail_count"], r["deploy_fail_count"])
        updated_at = r.pop("updated_at")
        r["passed_date"] = fmt_date(updated_at) if raw_status == "Passed" else None
        deploy_time = r.pop("deploy_time") or updated_at          # old cases without a deploy remark: last update
        r["deployed_date"] = fmt_dt(deploy_time) if raw_status == "Deployed" else None
        r["start_date"] = fmt_date(r.pop("start_date"))
        r["fixed_date"] = fmt_dt(r.pop("fixed_date"))
        r["deploy_fail_details"] = r.pop("deploy_fail_details") or ""
    return (rows, total, page, size) if paged else rows


@bp.get("/api/report")
def report():
    """One page of the report plus the screen names for the filter: {rows, total, page, size, pages, screens}."""
    me = login_required()
    rows, total, page, size = report_rows(me, paged=True)
    cond, args = scope(me)
    screens = [r["screen"] for r in q("SELECT DISTINCT c.screen FROM cases c LEFT JOIN members d ON d.id = c.developer_id WHERE "
                                      + cond + " ORDER BY 1", tuple(args))]
    return jsonify(rows=rows, total=total, page=page, size=size, pages=max((total + size - 1) // size, 1), screens=screens)


@bp.get("/api/report.csv")
def report_csv():
    rows = report_rows(login_required())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Test ID", "Test Case Description", "Screen Name", "Branch", "Module",
                "Assigned To (Developer)", "Tester Assigned", "Fail Count", "Start Date",
                "Developer Fixed Date", "Deploy Fail Count", "Deployment Date",
                "Deploy Fail Details", "Status Of Test", "Passed On", "Follow-Up Of (Reference Case)",
                "Duplicate Of"])
    for r in rows:
        w.writerow([r["test_id"], r["description"], r["screen"], r["branch"], r["module"],
                    r["assigned_to"], r["tester"], r["fail_count"], r["start_date"] or "",
                    r["fixed_date"] or "", r["deploy_fail_count"], r["deployed_date"] or "",
                    r["deploy_fail_details"], r["status"], r["passed_date"] or "", r["ref_code"], r["dup_code"]])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=test-report.csv"})
