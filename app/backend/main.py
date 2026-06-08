import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import leads, scraper, campaigns, orders, products

logger = logging.getLogger("kairos.autosync")

SHEET_SYNC_INTERVAL = 10 * 60  # seconds


async def _sheet_autosync_loop():
    """Background task: sync catalog from Google Sheet every SHEET_SYNC_INTERVAL seconds."""
    await asyncio.sleep(30)  # let server finish starting up
    while True:
        try:
            sheet_id = products._get_sheet_id()
            if sheet_id:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, products._run_sheet_sync, sheet_id
                )
                logger.info("Sheet auto-sync: %s", result)
        except Exception as exc:
            logger.warning("Sheet auto-sync error: %s", exc)
        await asyncio.sleep(SHEET_SYNC_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_sheet_autosync_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Kairos CRM API",
    description="Backend API for Kairos CRM",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router)
app.include_router(scraper.router)
app.include_router(campaigns.router)
app.include_router(orders.router)
app.include_router(products.router)


@app.get("/")
def root():
    return {"status": "ok", "app": "Kairos CRM API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
