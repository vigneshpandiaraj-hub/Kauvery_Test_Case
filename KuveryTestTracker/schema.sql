-- WARNING: this resets the tables. Remove the DROP line if you want to keep existing data.
DROP TABLE IF EXISTS notifications, attachments, remarks, cases, branches, modules, members CASCADE;

CREATE TABLE members (
  id            SERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT,          -- filled in by app.py on first start (default password: pass123)
  email         TEXT,          -- optional: used for email notifications
  active        BOOLEAN NOT NULL DEFAULT TRUE,   -- inactive people cannot sign in and are not offered in lists
  reports_to    INTEGER,       -- reporting person (filled in under Masters)
  role          TEXT NOT NULL CHECK (role IN ('Admin','Test Lead','QA Engineer','Automation Engineer','Developer','Promotion','Support','Team Leader','Viewer'))
);

ALTER TABLE members ADD CONSTRAINT members_reports_to_fk FOREIGN KEY (reports_to) REFERENCES members(id) ON DELETE SET NULL;

CREATE TABLE branches (
  id   SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE modules (
  id          SERIAL PRIMARY KEY,
  description TEXT NOT NULL UNIQUE,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE cases (
  id           SERIAL PRIMARY KEY,
  title        TEXT NOT NULL,
  screen       TEXT NOT NULL,
  priority     TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('High','Medium','Low')),
  tester_id    INTEGER REFERENCES members(id) ON DELETE SET NULL,
  developer_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
  branch_id    INTEGER REFERENCES branches(id) ON DELETE SET NULL,
  module_id    INTEGER REFERENCES modules(id) ON DELETE SET NULL,
  status       TEXT NOT NULL DEFAULT 'Not run'
               CHECK (status IN ('Not run','In progress','Failed','Fixed','Passed','Blocked','Deploy Failed','Deployed','Cancelled','Duplicate','On Hold','Returned','Pending Approval','Clarification')),
  fail_count   INTEGER NOT NULL DEFAULT 0,
  deploy_fail_count INTEGER NOT NULL DEFAULT 0,
  ref_case_id  INTEGER REFERENCES cases(id) ON DELETE SET NULL,   -- follow-up of this earlier case
  hold_prev_status TEXT,
  clarify_prev_status TEXT,                                       -- status to return to when the developer clarifies                                          -- status to return to when the Test Lead resumes a held case
  created_by   INTEGER REFERENCES members(id) ON DELETE SET NULL,
  dup_of_id    INTEGER REFERENCES cases(id) ON DELETE SET NULL,   -- suspected / confirmed duplicate of this case
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),                -- used by the From / To date filter
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON cases (created_at);
CREATE INDEX ON cases (status);

CREATE TABLE remarks (
  id          SERIAL PRIMARY KEY,
  case_id     INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  author_id   INTEGER REFERENCES members(id) ON DELETE SET NULL,
  author_name TEXT NOT NULL,
  author_role TEXT NOT NULL,
  action      TEXT NOT NULL,
  round       INTEGER NOT NULL DEFAULT 0,
  text        TEXT NOT NULL DEFAULT '',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON remarks (case_id, id);

CREATE TABLE attachments (
  id            SERIAL PRIMARY KEY,
  case_id       INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  uploaded_by   INTEGER REFERENCES members(id) ON DELETE SET NULL,
  uploader_name TEXT NOT NULL,
  original_name TEXT NOT NULL,          -- name shown to people
  stored_name   TEXT NOT NULL UNIQUE,   -- random name on disk (uploads/ folder)
  mime_type     TEXT,
  size_bytes    BIGINT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON attachments (case_id, id);

CREATE TABLE notifications (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  case_id    INTEGER REFERENCES cases(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL DEFAULT 'info',     -- colour on screen: fail, fix, pass, deploy, hold, assign, info
  message    TEXT NOT NULL,
  is_read    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON notifications (user_id, is_read, id);

INSERT INTO members (name, username, role) VALUES
  ('Alex','alex','Test Lead'),('Sam','sam','QA Engineer'),('Jordan','jordan','Automation Engineer'),
  ('Riley','riley','QA Engineer'),('Priya','priya','Developer'),('Chen','chen','Developer'),
  ('Dana','dana','Promotion'),('Morgan','morgan','Viewer'),('Taylor','taylor','Support'),('Casey','casey','Team Leader'),
  ('Admin','admin','Admin'),('Jamie','jamie','Team Leader');

-- each developer has their own team leader (the leader who approves that developer's cases)
UPDATE members SET reports_to = (SELECT id FROM members WHERE username='casey') WHERE username = 'priya';
UPDATE members SET reports_to = (SELECT id FROM members WHERE username='jamie') WHERE username = 'chen';

INSERT INTO branches (name) VALUES ('Head Office'),('North Branch'),('South Branch');
INSERT INTO modules (description) VALUES ('Purchase'),('Sales'),('Inventory'),('Accounts'),('HR');

INSERT INTO cases (title, screen, priority, tester_id, developer_id, branch_id, module_id, status, fail_count) VALUES
  ('Log in with valid credentials','Login Screen','High',2,5,1,4,'Passed',0),
  ('Reject wrong password','Login Screen','High',2,5,1,4,'Passed',0),
  ('Reset password by email','Forgot Password Screen','Medium',4,5,1,4,'Failed',1),
  ('Add item to cart','Cart Screen','High',3,6,1,2,'In progress',0),
  ('Apply discount code','Cart Screen','Medium',4,6,2,2,'Fixed',2),
  ('Pay with saved card','Payment Screen','High',3,6,2,2,'Not run',0),
  ('Export report as CSV','Reports Screen','Low',NULL,NULL,3,3,'Not run',0);

INSERT INTO remarks (case_id, author_id, author_name, author_role, action, round, text, created_at) VALUES
  (3,4,'Riley','QA Engineer','fail',1,'Reset email is never sent. No error shown on screen.', now() - interval '2 hours'),
  (5,4,'Riley','QA Engineer','fail',1,'Code SAVE10 gives no discount on the cart total.', now() - interval '3 days'),
  (5,6,'Chen','Developer','fix',1,'Discount was applied before tax. Now applied to the subtotal.', now() - interval '2 days'),
  (5,4,'Riley','QA Engineer','fail',2,'Works for one item, but fails when the cart has two or more.', now() - interval '1 day'),
  (5,6,'Chen','Developer','fix',2,'Fixed the loop that only discounted the first line item.', now() - interval '3 hours');
