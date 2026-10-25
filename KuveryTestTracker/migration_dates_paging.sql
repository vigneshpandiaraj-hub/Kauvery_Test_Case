-- Adds the case created date (for the From / To filter) and indexes for big lists. Keeps all data, safe to run twice:
--   python run_sql.py migration_dates_paging.sql
ALTER TABLE cases ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
-- old cases: use the time of their first remark, else their last update
UPDATE cases c SET created_at = COALESCE((SELECT MIN(r.created_at) FROM remarks r WHERE r.case_id = c.id), c.updated_at)
  WHERE c.created_at IS NULL;
ALTER TABLE cases ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE cases ALTER COLUMN created_at SET NOT NULL;
CREATE INDEX IF NOT EXISTS cases_created_at_idx ON cases (created_at);
CREATE INDEX IF NOT EXISTS cases_status_idx ON cases (status);
CREATE INDEX IF NOT EXISTS remarks_case_action_idx ON remarks (case_id, action);
