"""Tester performance report for the test-case tracker.

Live data :  python tester_report.py --dsn postgresql://postgres:PASSWORD@127.0.0.1:5433/testtracker
             (or set DATABASE_URL)   -> needs `pip install psycopg2-binary openpyxl`
Demo data :  python tester_report.py --sample   (uses the 7 sample cases from schema.sql)
Options   :  --since 2026-10-01   only count activity from this date   --out report.xlsx
Read-only: it only runs SELECT queries.
"""
import argparse
import os
from datetime import datetime, timedelta, timezone

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

TESTERS = ("QA Engineer", "Automation Engineer")
NOW = datetime.now(timezone.utc)
INCLUDE_INACTIVE = False


# ---------------------------------------------------------------- data
def load_live(dsn, since):
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT id, name, role, reports_to, active FROM members")
    members = cur.fetchall()
    cur.execute("SELECT * FROM cases")
    cases = cur.fetchall()
    cur.execute("SELECT case_id, author_id, action, round, text, created_at FROM remarks ORDER BY id")
    remarks = cur.fetchall()
    cur.execute("SELECT uploaded_by, created_at FROM attachments")
    atts = cur.fetchall()
    conn.close()
    if since:
        remarks = [r for r in remarks if r["created_at"] >= since]
        atts = [a for a in atts if a["created_at"] >= since]
    return members, cases, remarks, atts


def load_sample():
    """Same data as the INSERTs in schema.sql."""
    ago = lambda **k: NOW - timedelta(**k)
    members = [dict(id=i, name=n, role=r) for i, n, r in [
        (1, "Alex", "Test Lead"), (2, "Sam", "QA Engineer"), (3, "Jordan", "Automation Engineer"),
        (4, "Riley", "QA Engineer"), (5, "Priya", "Developer"), (6, "Chen", "Developer"),
        (7, "Dana", "Promotion"), (8, "Morgan", "Viewer")]]
    rows = [  # title, screen, priority, tester, dev, status, fails
        ("Log in with valid credentials", "Login Screen", "High", 2, 5, "Passed", 0),
        ("Reject wrong password", "Login Screen", "High", 2, 5, "Passed", 0),
        ("Reset password by email", "Forgot Password Screen", "Medium", 4, 5, "Failed", 1),
        ("Add item to cart", "Cart Screen", "High", 3, 6, "In progress", 0),
        ("Apply discount code", "Cart Screen", "Medium", 4, 6, "Fixed", 2),
        ("Pay with saved card", "Payment Screen", "High", 3, 6, "Not run", 0),
        ("Export report as CSV", "Reports Screen", "Low", None, None, "Not run", 0)]
    cases = [dict(id=i + 1, title=t, screen=s, priority=p, tester_id=te, developer_id=d, status=st,
                  fail_count=f, deploy_fail_count=0, updated_at=NOW) for i, (t, s, p, te, d, st, f) in enumerate(rows)]
    remarks = [
        dict(case_id=3, author_id=4, action="fail", round=1, created_at=ago(hours=2),
             text="Reset email is never sent. No error shown on screen."),
        dict(case_id=5, author_id=4, action="fail", round=1, created_at=ago(days=3),
             text="Code SAVE10 gives no discount on the cart total."),
        dict(case_id=5, author_id=6, action="fix", round=1, created_at=ago(days=2),
             text="Discount was applied before tax. Now applied to the subtotal."),
        dict(case_id=5, author_id=4, action="fail", round=2, created_at=ago(days=1),
             text="Works for one item, but fails when the cart has two or more."),
        dict(case_id=5, author_id=6, action="fix", round=2, created_at=ago(hours=3),
             text="Fixed the loop that only discounted the first line item.")]
    return members, cases, remarks, []


# ---------------------------------------------------------------- metrics
def compute(members, cases, remarks, atts):
    out = []
    for m in members:
        if not m.get("active", True) and not INCLUDE_INACTIVE:     # only active people are reported
            continue
        mine = [c for c in cases if c["tester_id"] == m["id"] and c["status"] not in ("Cancelled", "Duplicate", "On Hold")]   # cancelled / duplicate / held tests are not counted
        if m["role"] not in TESTERS and not (m["role"] == "Test Lead" and mine):   # the Test Lead appears only when they test cases themselves
            continue
        cnt = lambda *st: sum(1 for c in mine if c["status"] in st)
        my_fails = [r for r in remarks if r["author_id"] == m["id"] and r["action"] in ("fail", "deploy_fail")]
        mine_ids = {c["id"] for c in mine}
        rejected = sum(1 for r in remarks if r["action"] == "reject" and r["case_id"] in mine_ids)
        # retest turnaround: developer "fix" (or "not a failure") -> this tester's next pass/fail on that case
        turns = []
        for c in mine:
            seq = [r for r in remarks if r["case_id"] == c["id"]]
            for i, r in enumerate(seq):
                if r["action"] not in ("fix", "reject", "clarified"):
                    continue
                nxt = next((x for x in seq[i + 1:] if x["action"] in ("pass", "fail") and x["author_id"] == m["id"]), None)
                if nxt:
                    turns.append((nxt["created_at"] - r["created_at"]).total_seconds() / 3600)
        idle = sum(1 for c in mine if c["status"] in ("Not run", "In progress", "Fixed", "Returned", "Blocked")
                   and (NOW - c["updated_at"]).days >= 7)
        out.append(dict(
            boss=next((x["name"] for x in members if x["id"] == m.get("reports_to")), ""), name=m["name"], role=m["role"], assigned=len(mine), done=cnt("Passed", "Deployed", "Pending Approval"),
            inprog=cnt("In progress"), notrun=cnt("Not run"), blocked=cnt("Blocked"),
            withdev=cnt("Failed", "Deploy Failed", "Clarification"), retest=cnt("Fixed", "Returned"), rejected=rejected,
            defects=len(my_fails), multi=sum(1 for c in mine if c["fail_count"] >= 2),
            turn=round(sum(turns) / len(turns), 1) if turns else None,
            detailed=sum(1 for r in my_fails if len((r["text"] or "").strip()) >= 30),
            atts=sum(1 for a in atts if a["uploaded_by"] == m["id"]), idle=idle))
    return out


# ---------------------------------------------------------------- workbook
def build(rows, cases, members, source_note, path):
    wb = Workbook()
    F = "Arial"
    hdr_fill = PatternFill("solid", fgColor="1F3864")
    sub_fill = PatternFill("solid", fgColor="D9E2F3")
    thin = Side(style="thin", color="BFBFBF")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    blue = Font(name=F, color="0000FF")

    # ---- Settings
    st = wb.active
    st.title = "Settings"
    st["A1"] = "Score settings (edit the blue cells; the Scorecard recalculates)"
    st["A1"].font = Font(name=F, bold=True, size=12)
    settings = [
        ("Weight: completion rate", 30), ("Weight: retest turnaround", 15),
        ("Weight: fail remarks with detail", 15), ("Weight: evidence attached", 5),
        ("Weight: no idle cases", 5),
        ("Turnaround full marks at or under (hours)", 24), ("Turnaround zero marks at or over (hours)", 72),
        ("Rating 'Strong' at score of", 80), ("Rating 'Meets expectations' at score of", 60),
        ("Weight: failure accuracy (failures NOT rejected by developers)", 30)]
    for i, (k, v) in enumerate(settings, start=3):
        st.cell(i, 1, k).font = Font(name=F)
        c = st.cell(i, 2, v)
        c.font = blue
        c.border = box
    st["A14"] = "Notes"
    st["A14"].font = Font(name=F, bold=True)
    notes = [
        "Completion rate = cases the tester passed (Pending Approval, Passed or Deployed) ÷ cases assigned to the tester.",
        "Retest turnaround = average hours from a developer's 'Fixed' to the tester's next Pass/Fail on that case.",
        "Fail remarks with detail = share of the tester's Fail remarks that are 30+ characters (a reproducible description).",
        "Evidence attached = file attachments uploaded ÷ defects raised (capped at 100%).",
        "No idle cases = share of the tester's open cases touched in the last 7 days.",
        "Failure accuracy = 1 - (failures the developer rejected as 'not a failure' ÷ failures raised). A rejected failure is taken off the case's fail count (Failed 3 becomes Failed 2).",
        "A rejection is the developer's view. A tester who disagrees can fail the case again; check those cases before judging.",
        "Defects raised is shown for context but NOT scored: it depends on code quality and on which cases were assigned.",
        "If a measure has no data (e.g. no retests yet) it is left out and the other weights are rescaled.",
        "The score is a guide for discussion, not a verdict. Read it with the manager's own knowledge of case difficulty and volume.",
    ]
    for i, n in enumerate(notes, start=15):
        st.cell(i, 1, n).font = Font(name=F)
    st.column_dimensions["A"].width = 95
    st.column_dimensions["B"].width = 10

    # ---- Scorecard
    ws = wb.create_sheet("Scorecard", 0)
    ws["A1"] = "Tester Performance Report"
    ws["A1"].font = Font(name=F, bold=True, size=16)
    ws["A2"] = f"{source_note}  |  Generated {NOW.astimezone().strftime('%d %b %Y, %H:%M')}"
    ws["A2"].font = Font(name=F, italic=True, color="595959")
    heads = ["Tester", "Role", "Cases assigned", "Passed / Deployed", "In progress", "Not run", "Blocked",
             "With developer (Failed / Clarification)", "Awaiting retest", "Completion rate", "Defects raised",
             "Cases failed 2+ times", "Avg retest turnaround (hrs)", "Fail remarks with detail",
             "Attachments uploaded", "Idle open cases (7+ days)",
             "Failures rejected by developer", "Failure accuracy",
             "Completion pts", "Turnaround pts", "Remark pts", "Evidence pts", "Idle pts", "Accuracy pts",
             "Overall score (0-100)", "Rating", "Reporting to"]
    HR = 4
    cap = lambda t: " ".join(w[:1].upper() + w[1:] for w in t.split(" "))      # Init Cap every word
    for j, h in enumerate(heads, start=1):
        c = ws.cell(HR, j, cap(h))
        c.font = Font(name=F, bold=True, color="FFFFFF")
        c.fill = hdr_fill if j <= 18 else PatternFill("solid", fgColor="7F7F7F")
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        c.border = box
    ws.row_dimensions[HR].height = 48
    for i, r in enumerate(rows, start=HR + 1):
        vals = [r["name"], r["role"], r["assigned"], r["done"], r["inprog"], r["notrun"], r["blocked"],
                r["withdev"], r["retest"], f"=IFERROR(D{i}/C{i},0)", r["defects"], r["multi"],
                r["turn"], f"=IF(K{i}=0,\"\",{r['detailed']}/K{i})", r["atts"], r["idle"],
                r["rejected"], f"=IF(K{i}=0,\"\",MAX(0,1-Q{i}/K{i}))"]
        for j, v in enumerate(vals, start=1):
            ws.cell(i, j, v)
        # score components (0-100, blank when no data)
        ws[f"S{i}"] = f"=J{i}*100"
        ws[f"T{i}"] = (f'=IF(M{i}="","",MAX(0,MIN(100,(Settings!$B$9-M{i})/(Settings!$B$9-Settings!$B$8)*100)))')
        ws[f"U{i}"] = f'=IF(N{i}="","",N{i}*100)'
        ws[f"V{i}"] = f'=IF(K{i}=0,"",MIN(1,O{i}/K{i})*100)'
        ws[f"W{i}"] = f'=IF((E{i}+F{i}+G{i}+I{i})=0,"",(1-P{i}/(E{i}+F{i}+G{i}+I{i}))*100)'
        ws[f"X{i}"] = f'=IF(R{i}="","",R{i}*100)'
        comps = [("S", "$B$3"), ("T", "$B$4"), ("U", "$B$5"), ("V", "$B$6"), ("W", "$B$7"), ("X", "$B$12")]
        num = "+".join(f"IF(ISNUMBER({c}{i}),{c}{i}*Settings!{w},0)" for c, w in comps)
        den = "+".join(f"IF(ISNUMBER({c}{i}),Settings!{w},0)" for c, w in comps)
        ws[f"Y{i}"] = f"=IFERROR(({num})/({den}),\"\")"
        ws[f"Z{i}"] = (f'=IF(Y{i}="","No data",IF(Y{i}>=Settings!$B$10,"Strong",'
                       f'IF(Y{i}>=Settings!$B$11,"Meets expectations","Needs improvement")))')
        ws[f"AA{i}"] = r["boss"] or "Not set"
        for j in range(1, 28):
            c = ws.cell(i, j)
            c.font = Font(name=F, bold=(j in (25, 26)))
            c.border = box
            c.alignment = Alignment(horizontal="left" if j <= 2 else "center", vertical="center")
        for col in "JNR":
            ws[f"{col}{i}"].number_format = "0%"
        for col in "STUVWXY":
            ws[f"{col}{i}"].number_format = "0"
        ws[f"M{i}"].number_format = "0.0"
    last = HR + len(rows)
    for col, w in zip(["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z","AA"], [14, 20] + [11] * 16 + [10] * 6 + [13, 22, 18]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = ws.cell(HR + 1, 3)
    green, amber, red = ("C6EFCE", "006100"), ("FFEB9C", "9C5700"), ("FFC7CE", "9C0006")
    rng = f"Z{HR+1}:Z{last}"
    for text, (bg, fg) in (("Strong", green), ("Meets expectations", amber), ("Needs improvement", red)):
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{text}"'],
                                                      fill=PatternFill("solid", bgColor=bg), font=Font(name=F, color=fg)))
    n = last + 2
    ws.cell(n, 1, "Team total").font = Font(name=F, bold=True)
    for col in "CDEFGHIKLOPQ":
        c = ws[f"{col}{n}"]
        c.value = f"=SUM({col}{HR+1}:{col}{last})"
        c.font = Font(name=F, bold=True)
        c.alignment = Alignment(horizontal="center")
        c.fill = sub_fill
    ws[f"J{n}"] = f"=IFERROR(D{n}/C{n},0)"
    ws[f"J{n}"].number_format = "0%"
    ws[f"J{n}"].font = Font(name=F, bold=True)
    ws[f"J{n}"].alignment = Alignment(horizontal="center")
    ws[f"J{n}"].fill = sub_fill
    ws.cell(n + 2, 1, "Column guide: grey 'pts' columns are the score components (0-100). Weights and thresholds are on the Settings sheet.").font = Font(name=F, italic=True, color="595959")
    if len(rows) and max(r["assigned"] for r in rows) < 10:
        ws.cell(n + 3, 1, "Caution: fewer than 10 cases per tester - too little data for a fair comparison.").font = Font(name=F, bold=True, color="C00000")

    # ---- Case detail
    cd = wb.create_sheet("Case detail")
    names = {m["id"]: m["name"] for m in members}
    h2 = ["Test ID", "Description", "Screen", "Priority", "Tester", "Developer", "Status", "Fail Count", "Last Updated", "Days Since Update"]
    for j, h in enumerate(h2, start=1):
        c = cd.cell(1, j, h)
        c.font = Font(name=F, bold=True, color="FFFFFF")
        c.fill = hdr_fill
        c.alignment = Alignment(wrap_text=True, horizontal="center")
    for i, c in enumerate(sorted(cases, key=lambda x: x["id"]), start=2):
        v = [f"TC-{100 + c['id']}", c["title"], c["screen"], c["priority"], names.get(c["tester_id"], "Unassigned"),
             names.get(c["developer_id"], "Unassigned"), c["status"], c["fail_count"],
             c["updated_at"].astimezone().strftime("%d/%m/%Y"), (NOW - c["updated_at"]).days]
        for j, x in enumerate(v, start=1):
            cell = cd.cell(i, j, x)
            cell.font = Font(name=F)
    for col, w in zip("ABCDEFGHIJ", [10, 36, 24, 10, 14, 14, 14, 10, 14, 12]):
        cd.column_dimensions[col].width = w
    cd.freeze_panes = "A2"
    wb.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--include-inactive", action="store_true", help="also report people marked inactive")
    ap.add_argument("--out", default="tester_performance_report.xlsx")
    a = ap.parse_args()
    global INCLUDE_INACTIVE
    INCLUDE_INACTIVE = a.include_inactive
    since = datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=timezone.utc) if a.since else None
    if a.sample:
        data, note = load_sample(), "SAMPLE DATA ONLY (the 7 demo cases in schema.sql) - not real performance"
    else:
        dsn = a.dsn
        if not dsn:  # fall back to the app's own setting (config.py next to this script)
            try:
                from config import DSN as dsn
            except ImportError:
                ap.error("put this file in the test-tracker folder (next to config.py), or give --dsn")
        data, note = load_live(dsn, since), "Live tracker data" + (f", activity since {a.since}" if a.since else "")
    members, cases, remarks, atts = data
    build(compute(members, cases, remarks, atts), cases, members, note, a.out)
    print("saved", a.out)


if __name__ == "__main__":
    main()
