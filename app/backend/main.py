from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import leads, scraper, campaigns, orders, products, organizations, public

# Scraper/enrichment jobs run in the separate worker process (worker.py),
# not in this web process — so a web restart/redeploy no longer interrupts
# them, and this process has nothing to recover on startup. The worker
# requeues its own orphaned 'running' jobs on its own startup instead.
app = FastAPI(
    title="Kairos CRM API",
    description="Backend API for Kairos CRM",
    version="1.0.0",
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
