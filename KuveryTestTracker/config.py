"""Settings and constants shared by the whole app."""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-before-real-use")
DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:log@127.0.0.1:5433/testtracker")
DEFAULT_PASSWORD = "pass123"

ROLES = {"Admin", "Test Lead", "QA Engineer", "Automation Engineer", "Developer", "Promotion", "Support", "Team Leader", "Viewer"}
TESTERS = ("QA Engineer", "Automation Engineer")
TESTER_ASSIGNABLE = TESTERS + ("Test Lead",)      # the Test Lead may also assign cases to themselves
# Once a case is approved it belongs to the deployment team: no other role can change it any more.
LOCKED_STATUSES = ("Passed", "Deploy Failed", "Deployed")
# Roles that get the "Add case" menu. Add "Developer" here to let developers add cases too.
# Developers can add cases (the Test Lead picks the tester). Support can only add follow-up cases to deployed cases.
CASE_CREATORS = ("Test Lead", "QA Engineer", "Automation Engineer", "Developer", "Support")
PRIORITIES = {"High", "Medium", "Low"}
NEW_STATUS = {"start": "In progress", "pass": "Pending Approval", "approve": "Passed", "clarify": "Clarification", "fail": "Failed", "fix": "Fixed",
              "block": "Blocked", "deploy": "Deployed", "cancel": "Cancelled", "duplicate": "Duplicate", "hold": "On Hold", "reject": "Returned",
              "deploy_fail": "Deploy Failed", "deploy_fix": "Passed"}

# ---- file attachments on cases ----
# Only these roles may upload (a tester only on cases assigned to them). Everyone who can see a case may download.
UPLOADERS = ("Test Lead",) + TESTERS
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))
MAX_UPLOAD_MB = 20          # total size of one upload request
# Anything is allowed except programs / scripts / web pages that could be harmful if opened.
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".ps1", ".vbs", ".js", ".jar",
                      ".sh", ".dll", ".apk", ".html", ".htm", ".svg", ".php", ".py"}

# ---- email notifications (optional, free with a Gmail account + App Password) ----
# Leave SMTP_HOST empty to switch email off. See README for the setup steps.
SMTP_HOST = os.environ.get("SMTP_HOST", "")                 # e.g. smtp.gmail.com
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")                 # your full Gmail address
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")         # a Google App Password, not your normal password
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER
SMTP_TLS = os.environ.get("SMTP_TLS", "1") != "0"
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:5000")  # link put at the bottom of each email
