from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import leads, scraper, campaigns, orders, products, organizations, public


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: fail any jobs that were interrupted by a previous server restart
    try:
        from services.supabase_client import db
        from datetime import datetime, timezone
        db.raw_select  # ensure client is warm
        interrupted = db.raw_select("scraper_jobs", {
            "select": "id",
            "status": "in.(running,pending)",
            "limit": 50,
        })
        now = datetime.now(timezone.utc).isoformat()
        for job in interrupted:
            try:
                db.update("scraper_jobs", job["id"], {
                    "status": "failed",
                    "error_msg": "Job interrupted (server restart)",
                    "completed_at": now,
                })
            except Exception:
                pass
    except Exception:
        pass
    yield

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


@app.get("/")
def root():
    return {"status": "ok", "app": "Kairos CRM API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
