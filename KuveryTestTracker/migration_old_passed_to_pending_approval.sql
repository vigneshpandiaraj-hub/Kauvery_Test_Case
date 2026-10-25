-- OPTIONAL, run once: cases that were 'Passed' before the approval step existed are treated as approved.
-- This sends them back to 'Pending Approval' so the Team Leader can approve them first.
--   python run_sql.py migration_old_passed_to_pending_approval.sql
UPDATE cases SET status = 'Pending Approval', updated_at = now()
WHERE status = 'Passed'
  AND NOT EXISTS (SELECT 1 FROM remarks r WHERE r.case_id = cases.id AND r.action = 'approve');
