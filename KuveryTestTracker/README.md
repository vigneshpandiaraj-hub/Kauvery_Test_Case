# Test case tracker

Flask + PostgreSQL backend, plain HTML/JavaScript frontend, with sign-in and a menu per role.

## Run it
```powershell
psql -U postgres -h 127.0.0.1 -p 5433 -d testtracker -f schema.sql   # tables + sample data (drops old tables first)
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py                                                          # open http://127.0.0.1:5000
```
The connection string is the `DSN` line at the top of `app.py` (or set `DATABASE_URL`).
Before real use, set a private `SECRET_KEY` environment variable and serve the app over HTTPS.

## Files
| File | What is in it |
|---|---|
| `app.py` | Starts the app and registers the route files |
| `config.py` | Database address, secret key, roles, statuses, default password |
| `db.py` | Database connection and the `q()` query helper |
| `helpers.py` | Sign-in checks, who can see / do what on a case, shared queries |
| `routes/auth.py` | Home page, sign in / out, change own password |
| `routes/members.py` | Team (Test Lead) and the assign drop-down names |
| `routes/masters.py` | Branches and modules |
| `routes/cases.py` | Cases, the pass / fail workflow, remarks |
| `routes/files.py` | File attachments on cases: upload, download, delete |
| `routes/reports.py` | Report and CSV download |
| `static/index.html` | The whole front end (responsive for phone and tablet) |

To add a new area, create `routes/<name>.py` with a `bp = Blueprint(...)` and add it to the list in `create_app()` in `app.py`.

## Sign in
Sample users (username = lowercase name): taylor (Support), alex (Test Lead), sam and riley (QA Engineer), jordan (Automation Engineer), priya and chen (Developer), morgan (Viewer).
Everyone starts with the password `pass123`. Change it under **Profile**. A Test Lead can reset anyone's password under **Team**.

## Menus
| Role | Menu |
|---|---|
| Test Lead | All cases, Add case, Test report, Team, Profile |
| QA / Automation Engineer | My test cases, Add case, My report, Profile |
| Developer | My fixes, Add case, My report, Profile |
| Viewer | All cases, Test Report, Profile |
| Team Leader | Pending approval, My Report, Notifications, Profile |
| Support | Deployed cases (raise a follow-up case), My report, Profile |

## Who can see what (enforced in the API)
- Testers see only cases where they are the tester. Developers see only cases assigned to them. The report, the CSV download and the case history follow the same rule.
- Only the Test Lead sees the full team list. Testers get just the developers' names to pick from when failing a case.
- Test Lead and Viewer see all cases. The Viewer can't change anything.
- To let developers add cases too, add `"Developer"` to `CASE_CREATORS` in `app.py`.

## File attachments
Open a case and use **Attachments** to add images, PDFs, Word/Excel files, logs, zips and so on (limit 20 MB per upload, set by `MAX_UPLOAD_MB` in `config.py`).
- **Upload:** Test Lead (any case) and QA / Automation Engineers (cases assigned to them) only.
- **Download:** everyone who can see the case (Developer, Promotion, Viewer too).
- **Delete:** Test Lead, or the person who uploaded the file.
- Files are saved in the `uploads/` folder next to `app.py` (change with the `UPLOAD_DIR` environment variable). Back this folder up together with the database.
- Program / script / web-page types (`.exe`, `.js`, `.html`, `.svg`, ...) are refused; see `BLOCKED_EXTENSIONS` in `config.py`.
- **Existing database?** Run `psql ... -f migration_attachments.sql` once instead of `schema.sql`, which wipes your data.

## Follow-up cases (missed logic found after deployment)
Only the **Support** team raises follow-ups: open a **Deployed** case and press **Create follow-up case**. (The Test Lead, testers and developers do not get this button; the Test Lead also cannot mark deployed or fail a deployment, those belong to the promotion team.) On a Deployed case the **Open** button is greyed out for testers and developers. The Add case page opens with screen, module, branch, priority and people filled in, and the new case keeps the old case number as its reference.
- The new case shows "Follow-up of TC-xxx"; the old case lists its follow-up cases and gets a note in its remarks.
- The report and the CSV have a "Follow-up of" column.
- Testers and developers still only see their own cases; a reference to a case you cannot see shows as a plain number.
- **Existing database?** Run `psql ... -f migration_followup.sql` once (keeps your data). `schema.sql` wipes data.

## Cancel a test (instead of deleting)
The Test Lead no longer deletes cases from the screen. In a case, write a remark and press **Cancel test**: the case becomes **Cancelled**, stays in the history and report, and nobody can act on it any more. Cancelled cases are not counted in `tester_report.py`.
- **Existing database?** Run `psql ... -f migration_cancel.sql` once.
- A case that already has a follow-up case has its **Open** button greyed out in the list.

## Support, developer-created cases and duplicates
- **Support** (new role, sample user `taylor`): sees the deployed cases and the follow-ups they raised. Open a deployed case and press **Create follow-up case**. Support cannot add ordinary cases. The tester and developer are left empty for the Test Lead to choose.
- **Developer** now has an **Add case** menu. The case is assigned to that developer, no tester is set, and the Test Lead picks the tester in **All cases**.
- **Duplicates:** when adding a case, anyone can fill **Possible duplicate of** (a case number such as TC-105). The case's tester decides: **Mark as duplicate** (status Duplicate, closed, with a remark) or **Not a duplicate** (flag removed, testing carries on). A tester can also use **Mark as duplicate** on their own and type the case number.
- Cancelled and Duplicate cases are not counted in `tester_report.py`. The report and CSV have a **Duplicate of** column.
- **Existing database?** Run `psql ... -f migration_support_developer_duplicate.sql` once. It includes the earlier follow-up and cancel migrations.

## Hold and cancel (Test Lead only)
- The tester's **Block** button is removed. The Test Lead uses **Cancel test** instead: the case becomes **Cancelled** and stays on record. (Old cases already marked Blocked can still be started.)
- **Put on hold** (Test Lead, with a remark) freezes a case: status **On Hold**, nobody else can act on it. **Resume testing** (Test Lead) puts it back to the status it had before, with its fail counts intact.
- **Existing database?** Run `psql ... -f migration_hold.sql` once (or the combined `migration_support_developer_duplicate.sql`).

## Notifications and colours
- Everyone has a **Notifications** menu with a red unread count (also shown in the browser tab title). It refreshes every 30 seconds. Click a notification to mark it read and open the case.
- Who is told: a failed case goes to its developer; a fixed case to its tester; a passed case to the promotion team; a deployed case to the tester, developer and Test Lead; hold, resume and cancel to the tester and developer; a case added by a developer or Support, and a new tester or developer assignment, to the Test Lead or the person assigned; a possible duplicate to the tester. You are never notified of your own action.
- Each notification has a colour: red needs fixing, purple fixed / retest, green passed, teal deployed, amber hold or cancel, blue assigned.
- In a case, **remarks are coloured by role**: Test Lead green, tester blue, developer orange, promotion teal, support amber (a key is shown above the remarks).
- There is no email or SMS; notifications are inside the app.
- **Existing database?** Run `psql ... -f migration_notifications.sql` once.

## Developer says "not a failure"
When a case is **Failed n**, its developer can press **Not a failure, send back to tester** (remark required). The fail count goes down by one (Failed 3 becomes Failed 2), the status becomes **Returned to tester**, and the tester is notified. The tester then passes it, or fails it again if they disagree (Failed 3 again).
- Every rejection is kept in the remarks and counted per tester in `tester_report.py` ("Failures rejected by developer" and "Failure accuracy"). Accuracy has a 30% weight in the score (weights are editable on the Settings sheet).
- **Existing database?** Run `python run_sql.py migration_returned.sql` once.

## Clarification, approval and locking
- **Clarification:** a tester can press **I need clarification** (remark and developer required). Status becomes **Clarification** and the developer is notified. The developer presses **Clarified, send back to tester**, and the case returns to the status it had before.
- **Approval:** when a tester presses **Pass**, the case becomes **Pending Approval** and goes to the **Team Leader** (new role, sample user `casey`). Only the Team Leader can **Approve for deployment**; then it goes to the deployment (Promotion) team. Cases that were already Passed before this update count as approved.
- **Locking:** once approved (and while deploying or deployed) nobody can change the case: no hold, cancel, reassign or file changes. Only the deployment team acts, and the developer if a deployment fails.
- **Test Lead as tester:** the Test Lead now appears in the Tester drop-down and can assign cases to themselves.

## Email notifications (free)
Every in-app notification can also be emailed. It is free with a Gmail account:
1. Google Account > Security > turn on 2-Step Verification, then create an **App password** (16 characters).
2. In **Team**, type each person's email address.
3. Before starting the app, in PowerShell:
```powershell
$env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_USER="you@gmail.com"; $env:SMTP_PASSWORD="your-16-character-app-password"
$env:APP_URL="http://127.0.0.1:5000"; python app.py
```
Leave `SMTP_HOST` unset and email stays off. Gmail allows about 500 emails a day. People with no email address just get the in-app notification. A mail problem never stops a test action.

## Update buttons and Active flags
- **Team** and **Masters** (branches, modules, reporting) no longer save on every keystroke. Change the row, then press **Update**; a "Saved." message confirms it.
- Every person, branch and module has an **Active** tick. Inactive items disappear from all drop-downs (assign tester / developer, branch, module, reporting person). Inactive people cannot sign in and get no notifications or emails; their old cases and remarks stay as they were.
- You cannot deactivate yourself or the last active Test Lead.
- The tester performance report lists active people only (add `--include-inactive` to include the others). The in-app Test Report still lists every case, including ones handled by people who are now inactive, so history is never lost.
- **Existing database?** `python run_sql.py migration_all_in_one.sql` adds the Active columns (everyone starts as active).

## Reporting person
Under **Masters > Reporting** the Test Lead chooses a reporting person for every user (loops such as A to B to A are refused). It is shown in **Team** and as a **Reporting To** column in the tester performance report.
- Cases that were Passed before the approval step existed count as approved. To send them to the Team Leader first, run `python run_sql.py migration_old_passed_to_pending_approval.sql` once. Add a user with role **Team Leader** under **Team** if you don't have one (`casey` exists only in a fresh `schema.sql`).

## Helper scripts
- `python run_sql.py migration_all_in_one.sql` - brings an older database up to date (run this one; it replaces the separate migration files).
- `python reset_passwords.py [username]` - sets the password back to `pass123` for everyone, or one user.

## Workflow
1. Tester (or Test Lead) adds a case and a developer is assigned.
2. Tester: Start testing, then Pass, or Fail with a remark. Status becomes `Failed 1` and the case is with the developer.
3. Developer: Fixed, send for retest, with a remark. Status becomes `Fixed` and the case is back with the tester.
4. Tester retests: Pass, or Fail again (`Failed 2`, `Failed 3`, ...) until it passes.

## API
| Method | Path | Who |
|---|---|---|
| POST | /api/login, /api/logout | anyone |
| GET | /api/me | signed in |
| POST | /api/me/password | signed in |
| GET | /api/cases, /api/cases/:id/remarks, /api/report, /api/report.csv, /api/people | signed in (results limited to your own cases) |
| POST | /api/cases (optional `ref_case_id` for a follow-up) | Test Lead, QA, Automation |
| GET | /api/cases/:id/files, /api/files/:id/download | signed in, if you can see the case |
| POST | /api/cases/:id/files | Test Lead, assigned QA / Automation |
| DELETE | /api/files/:id | Test Lead, or the uploader |
| POST | /api/cases/:id/transition | assigned tester, assigned developer, Test Lead |
| GET/POST/PATCH/DELETE | /api/members | Test Lead |
| PATCH/DELETE | /api/cases/:id | Test Lead |


## Admin role, team leaders per developer, email check (v10)
Run once on your existing database, then restart the app:
```
python run_sql.py migration_admin.sql
python app.py
```
- **Admin** (new role, sample user `admin`, password `pass123`): the only role that sees **Team** and **Masters** (people, roles, emails, branches, modules, team leaders). Sees all cases and the report, read only. The Test Lead no longer has Team or Masters. There must always be at least one active Admin.
- **Team leader per member:** under **Masters > Team Leaders** (also shown in **Team**) the Admin tags a Team Leader to each person. When a tester passes a case, only the team leader of that case's developer gets the approval request and can approve it (if the developer has no team leader set, any Team Leader can). Sample: `casey` leads `priya`, `jamie` leads `chen`.
- **Email check:** the app prints `Email is ON/OFF` at start-up. In **Team > Email notifications** the Admin can send a test email and see the real error. Email stays off until `SMTP_HOST`, `SMTP_USER` and `SMTP_PASSWORD` are set in the same window that runs `python app.py`.

## Date filter, paging and report times (v11)
Run once on your existing database, then restart the app:
```
python run_sql.py migration_dates_paging.sql
```
- **From / To date filter** on the cases page and on the report (both days included). It filters on the date the case was created (new column `cases.created_at`; old cases use their first remark date). The status counts and pass rate show the totals for the chosen dates.
- **Paging:** cases and the report load one page at a time (10 / 25 / 50 / 100 / 200 per page, newest first), so 10,000+ cases stay fast. Use First / Previous / Next / Last or type a page number. **Download CSV** still gives every matching case, not just one page.
- **Report:** *Developer Fixed Date* and *Deployment Date* now show date **and time** (dd/mm/yyyy hh:mm, in the database server's time zone). Deployment time comes from the moment Promotion pressed Mark deployed.
