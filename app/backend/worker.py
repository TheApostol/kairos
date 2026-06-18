"""Background worker for scraper/enrichment jobs.

Runs as its own process (a separate Render service, or `python worker.py`
locally) so that restarting/redeploying the web process no longer kills a
job mid-run — the web process (routers/scraper.py's /start and /enrich) only
ever inserts a `pending` row into `scraper_jobs`; this process polls for
pending rows, claims one at a time, and runs it to completion.
"""

import logging
import time
from datetime import datetime, timezone

from routers.scraper import _run_scraper_job, _run_enrichment_job
from services.supabase_client import db
from sources import DEFAULT_SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("worker")

POLL_INTERVAL_SECONDS = 5


def _recover_orphaned_jobs() -> None:
    """On startup, requeue jobs left 'running' by a worker process that died
    or was redeployed mid-job — safe to just retry: scraper inserts dedupe
    against existing leads, and enrichment skips fields already filled in."""
    orphaned = db.raw_select("scraper_jobs", {"select": "id", "status": "eq.running", "limit": 50})
    for job in orphaned:
        try:
            db.update("scraper_jobs", job["id"], {"status": "pending", "started_at": None})
        except Exception:
            logger.exception("Failed to requeue orphaned job %s", job["id"])


def _claim_next_pending_job() -> dict | None:
    pending = db.raw_select("scraper_jobs", {
        "select": "*",
        "status": "eq.pending",
        "order": "created_at.asc",
        "limit": 1,
    })
    if not pending:
        return None

    job = pending[0]
    claimed = db.update_returning(
        "scraper_jobs", job["id"],
        {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()},
        extra_filters={"status": "eq.pending"},
    )
    return job if claimed else None


def _run_job(job: dict) -> None:
    job_id = str(job["id"])
    org_id = job.get("organization_id")
    params = job.get("params") or {}
    job_type = job.get("job_type") or ("enrichment" if job.get("queries") == ["enrichment"] else "scraper")

    logger.info("Running job %s (%s)", job_id, job_type)
    try:
        if job_type == "enrichment":
            _run_enrichment_job(job_id, params.get("lead_ids"), org_id)
        else:
            from config import settings

            _run_scraper_job(
                job_id,
                job.get("sources") or DEFAULT_SOURCES,
                job.get("queries") or [],
                settings.GOOGLE_API_KEY,
                params.get("max_per_query", 60),
                params.get("tipo_cliente", "lead"),
                params.get("source_options"),
                org_id,
            )
    except Exception:
        # _run_scraper_job/_run_enrichment_job already persist failures to
        # the job row themselves; this is a last-resort net for anything
        # that escapes that (e.g. a bug in the dispatcher itself).
        logger.exception("Job %s crashed outside its own error handling", job_id)


def main() -> None:
    logger.info("Worker started, polling scraper_jobs every %ss", POLL_INTERVAL_SECONDS)
    _recover_orphaned_jobs()
    while True:
        try:
            job = _claim_next_pending_job()
        except Exception:
            logger.exception("Error polling for pending jobs")
            job = None

        if job:
            _run_job(job)
            continue  # check for another pending job immediately

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
