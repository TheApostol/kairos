-- Fixes a misleading display bug: `scraper_jobs.sources` defaulted to
-- '["google_places"]' (set in supabase_migration_scraper_sources.sql, for
-- backward-compat with pre-multi-source scraper rows). Enrichment jobs never
-- set `sources` themselves, so every enrichment job silently inherited that
-- default and showed "Fuentes: google_places" in the job history UI even
-- though enrichment never touches Google Places.
--
-- Scraper jobs always set `sources` explicitly on insert, so the default is
-- only ever observed on enrichment rows (or other rows that don't set it) —
-- safe to change to an empty array, and to backfill existing enrichment rows.

ALTER TABLE scraper_jobs
  ALTER COLUMN sources SET DEFAULT '[]'::jsonb;

UPDATE scraper_jobs
SET sources = '[]'::jsonb
WHERE job_type = 'enrichment' OR queries = '["enrichment"]'::jsonb;
