import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import leads, scraper, campaigns, orders, products, organizations, public, platform
import worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scraper/enrichment jobs run on a background thread inside this same
    # process (see worker.py) instead of as a FastAPI BackgroundTask tied to
    # one request — a dedicated Render Background Worker service isn't free,
    # so job processing stays on this (free) web service instance. On a
    # deploy/restart, the new process's startup just requeues whatever job
    # was left "running" and the loop resumes it, instead of losing it.
    threading.Thread(target=worker.main, daemon=True).start()
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
app.include_router(public.tracking_router)
app.include_router(platform.router)


@app.get("/")
def root():
    return {"status": "ok", "app": "Kairos CRM API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
