import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import leads, scraper, campaigns, orders, products, organizations, public, platform
from services.auth import list_organizations_with_sheet
from services.supabase_client import db, ScopedSupabaseClient
import worker

logger = logging.getLogger("kairos.sheet_autosync")

SHEET_SYNC_INTERVAL = 10 * 60  # seconds


async def _sheet_autosync_loop():
    """Background task: for every org with a connected Google Sheet, sync its
    catalog from that sheet every SHEET_SYNC_INTERVAL seconds. Runs across all
    tenants, so it lives here instead of inside routers/products.py (which is
    scoped to a single org per request via ScopedSupabaseClient)."""
    await asyncio.sleep(30)  # let the server finish starting up
    while True:
        try:
            orgs = await asyncio.get_event_loop().run_in_executor(None, list_organizations_with_sheet)
            for org in orgs:
                org_id = org["id"]
                sheet_id = org.get("google_sheet_id")
                if not sheet_id:
                    continue
                try:
                    scoped_db = ScopedSupabaseClient(db, org_id)
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, products._run_sheet_sync, scoped_db, org_id, sheet_id
                    )
                    logger.info("Sheet auto-sync for org %s: %s", org_id, result)
                except Exception:
                    logger.exception("Sheet auto-sync failed for org %s", org_id)
        except Exception:
            logger.exception("Sheet auto-sync loop error")
        await asyncio.sleep(SHEET_SYNC_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scraper/enrichment jobs run on a background thread inside this same
    # process (see worker.py) instead of as a FastAPI BackgroundTask tied to
    # one request — a dedicated Render Background Worker service isn't free,
    # so job processing stays on this (free) web service instance. On a
    # deploy/restart, the new process's startup just requeues whatever job
    # was left "running" and the loop resumes it, instead of losing it.
    threading.Thread(target=worker.main, daemon=True).start()
    sheet_sync_task = asyncio.create_task(_sheet_autosync_loop())
    yield
    sheet_sync_task.cancel()

app = FastAPI(
    title="Kairos CRM API",
    description="Backend API for Kairos CRM",
    version="1.0.0",
    lifespan=lifespan,
)

# The production frontend is always allowed, even if ALLOWED_ORIGINS isn't
# configured (or is misconfigured) on the host.
_PROD_FRONTEND_ORIGIN = "https://kairos.polkorp.com"
_configured_origins = {o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()}
_configured_origins.add(_PROD_FRONTEND_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_configured_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router)
app.include_router(scraper.router)
app.include_router(campaigns.router)
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(organizations.router)
app.include_router(public.router)
app.include_router(public.tracking_router)
app.include_router(platform.router)


@app.get("/")
def root():
    return {"status": "ok", "app": "Kairos CRM API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
