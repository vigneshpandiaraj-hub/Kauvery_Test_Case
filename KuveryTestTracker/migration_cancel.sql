-- Run once on an EXISTING database to allow the new 'Cancelled' status (keeps your data):
--   psql -U postgres -h 127.0.0.1 -p 5433 -d testtracker -f migration_cancel.sql
ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_status_check;
ALTER TABLE cases ADD CONSTRAINT cases_status_check
  CHECK (status IN ('Not run','In progress','Failed','Fixed','Passed','Blocked','Deploy Failed','Deployed','Cancelled'));
