-- Adds a `details` jsonb column to `scraper_jobs` so each scraper/enrichment
-- run can store a structured breakdown (per-source found/new counts for
-- scraper jobs; per-field counts for enrichment jobs) for the end-of-run
-- report shown in the frontend. Additive and backward-compatible: existing
-- rows default to an empty object.

ALTER TABLE scraper_jobs
  ADD COLUMN IF NOT EXISTS details jsonb DEFAULT '{}'::jsonb;
