-- Run once on an EXISTING database (keeps your data) to add the 'Returned' status
-- (developer says "not a failure" and sends the case back to the tester):
--   python run_sql.py migration_returned.sql
ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_status_check;
ALTER TABLE cases ADD CONSTRAINT cases_status_check
  CHECK (status IN ('Not run','In progress','Failed','Fixed','Passed','Blocked','Deploy Failed','Deployed','Cancelled','Duplicate','On Hold','Returned'));
