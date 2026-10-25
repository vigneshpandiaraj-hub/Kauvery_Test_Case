-- Run once on an EXISTING database (keeps your data). Adds: Support role, developer-created cases, duplicate status.
--   psql -U postgres -h 127.0.0.1 -p 5433 -d testtracker -f migration_support_developer_duplicate.sql
-- (It includes everything in migration_followup.sql and migration_cancel.sql, so those need not be run first.)
ALTER TABLE cases ADD COLUMN IF NOT EXISTS ref_case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS hold_prev_status TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS created_by  INTEGER REFERENCES members(id) ON DELETE SET NULL;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS dup_of_id   INTEGER REFERENCES cases(id) ON DELETE SET NULL;
ALTER TABLE members DROP CONSTRAINT IF EXISTS members_role_check;
ALTER TABLE members ADD CONSTRAINT members_role_check
  CHECK (role IN ('Test Lead','QA Engineer','Automation Engineer','Developer','Promotion','Support','Viewer'));
ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_status_check;
ALTER TABLE cases ADD CONSTRAINT cases_status_check
  CHECK (status IN ('Not run','In progress','Failed','Fixed','Passed','Blocked','Deploy Failed','Deployed','Cancelled','Duplicate','On Hold','Returned'));
