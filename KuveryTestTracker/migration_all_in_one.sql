-- ONE migration that brings any older database up to date (keeps all data, safe to run more than once):
--   python run_sql.py migration_all_in_one.sql
ALTER TABLE cases   ADD COLUMN IF NOT EXISTS ref_case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL;
ALTER TABLE cases   ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES members(id) ON DELETE SET NULL;
ALTER TABLE cases   ADD COLUMN IF NOT EXISTS dup_of_id INTEGER REFERENCES cases(id) ON DELETE SET NULL;
ALTER TABLE cases   ADD COLUMN IF NOT EXISTS hold_prev_status TEXT;
ALTER TABLE cases   ADD COLUMN IF NOT EXISTS clarify_prev_status TEXT;
ALTER TABLE cases   ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE members ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE members ADD COLUMN IF NOT EXISTS reports_to INTEGER;
ALTER TABLE members  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE branches ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE modules  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE members DROP CONSTRAINT IF EXISTS members_reports_to_fk;
ALTER TABLE members ADD CONSTRAINT members_reports_to_fk FOREIGN KEY (reports_to) REFERENCES members(id) ON DELETE SET NULL;
ALTER TABLE members DROP CONSTRAINT IF EXISTS members_role_check;
ALTER TABLE members ADD CONSTRAINT members_role_check
  CHECK (role IN ('Admin','Test Lead','QA Engineer','Automation Engineer','Developer','Promotion','Support','Team Leader','Viewer'));
ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_status_check;
ALTER TABLE cases ADD CONSTRAINT cases_status_check
  CHECK (status IN ('Not run','In progress','Failed','Fixed','Passed','Blocked','Deploy Failed','Deployed','Cancelled','Duplicate','On Hold','Returned','Pending Approval','Clarification'));
CREATE TABLE IF NOT EXISTS notifications (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  case_id    INTEGER REFERENCES cases(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL DEFAULT 'info',
  message    TEXT NOT NULL,
  is_read    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications (user_id, is_read, id);
-- Note: cases that were 'Passed' before this version stay 'Passed' (= approved, with the deployment team).
