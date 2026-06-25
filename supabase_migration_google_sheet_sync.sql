-- Adds per-organization Google Sheets catalog sync: each org can connect its
-- own sheet (stored on organizations instead of a global env var, since the
-- app is multi-tenant), and we track the last auto-sync result so the
-- background loop and the UI can both report status. Additive/nullable
-- default — backward compatible with existing rows.

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS google_sheet_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS google_sheet_last_sync timestamptz;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS google_sheet_last_result jsonb;
