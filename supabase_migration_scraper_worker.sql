-- Adds the columns `scraper_jobs` needs to run as parameterized, queueable
-- jobs picked up by a separate worker process, instead of being executed
-- in-process via FastAPI BackgroundTasks (which die whenever the web
-- process restarts/redeploys mid-job — the actual cause of the
-- "Interrumpido por un reinicio del servidor" failures).
--
-- `job_type` replaces the old `queries == ["enrichment"]` inference hack.
-- `params` persists the per-job arguments (tipo_cliente, max_per_query,
-- source_options, lead_ids) that used to live only as in-memory function
-- arguments, so a worker process — which has no access to the original
-- request — can reconstruct what to run.

ALTER TABLE scraper_jobs ADD COLUMN IF NOT EXISTS job_type text DEFAULT 'scraper';
ALTER TABLE scraper_jobs ADD COLUMN IF NOT EXISTS params jsonb DEFAULT '{}'::jsonb;

UPDATE scraper_jobs SET job_type = 'enrichment' WHERE queries = '["enrichment"]'::jsonb;
