-- Adds a `sources` column to `scraper_jobs` so each scraper run records
-- which lead-discovery sources (google_places, green_life, overpass,
-- datos_gob, paginas_amarillas, ecored, ...) it covered. Additive and
-- backward-compatible: existing rows get the previous default behavior
-- (google_places only).

ALTER TABLE scraper_jobs
  ADD COLUMN IF NOT EXISTS sources jsonb DEFAULT '["google_places"]';
