-- Run once on an EXISTING database (keeps your data) to add the 'On Hold' status.
-- Not needed if you run migration_support_developer_duplicate.sql after this version.
--   psql -U postgres -h 127.0.0.1 -p 5433 -d testtracker -f migration_hold.sql
ALTER TABLE cases ADD COLUMN IF NOT EXISTS hold_prev_status TEXT;
ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_status_check;
ALTER TABLE cases ADD CONSTRAINT cases_status_check
  CHECK (status IN ('Not run','In progress','Failed','Fixed','Passed','Blocked','Deploy Failed','Deployed','Cancelled','Duplicate','On Hold'));
