-- Adds the Admin role (Team and Masters screens) on an existing database. Keeps all data, safe to run twice:
--   python run_sql.py migration_admin.sql
-- Then start the app once: the new 'admin' user gets the default password pass123 (change it under Profile).
ALTER TABLE members DROP CONSTRAINT IF EXISTS members_role_check;
ALTER TABLE members ADD CONSTRAINT members_role_check
  CHECK (role IN ('Admin','Test Lead','QA Engineer','Automation Engineer','Developer','Promotion','Support','Team Leader','Viewer'));
INSERT INTO members (name, username, role)
  SELECT 'Admin', 'admin', 'Admin' WHERE NOT EXISTS (SELECT 1 FROM members WHERE username = 'admin');
-- A developer's team leader must be a Team Leader (the leader who approves that developer's cases).
-- Clear any developer link that points to someone else, so those cases are not stuck; choose the leader again under Masters.
UPDATE members m SET reports_to = NULL
  WHERE m.role = 'Developer' AND m.reports_to IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM members l WHERE l.id = m.reports_to AND l.role = 'Team Leader');
