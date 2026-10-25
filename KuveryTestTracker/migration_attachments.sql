-- Run this once on an EXISTING database to add file uploads without losing data:
--   psql -U postgres -h 127.0.0.1 -p 5433 -d testtracker -f migration_attachments.sql
CREATE TABLE IF NOT EXISTS attachments (
  id            SERIAL PRIMARY KEY,
  case_id       INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  uploaded_by   INTEGER REFERENCES members(id) ON DELETE SET NULL,
  uploader_name TEXT NOT NULL,
  original_name TEXT NOT NULL,
  stored_name   TEXT NOT NULL UNIQUE,
  mime_type     TEXT,
  size_bytes    BIGINT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS attachments_case_id_idx ON attachments (case_id, id);
