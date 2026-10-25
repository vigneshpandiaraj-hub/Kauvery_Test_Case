-- Run once on an EXISTING database to add follow-up cases (a new case that points to an older one):
--   psql -U postgres -h 127.0.0.1 -p 5433 -d testtracker -f migration_followup.sql
ALTER TABLE cases ADD COLUMN IF NOT EXISTS ref_case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL;
