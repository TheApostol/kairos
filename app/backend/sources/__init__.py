"""Registry of lead-discovery sources.

Each source module exposes an `iter_leads(...)` generator yielding dicts
shaped by `services.scraping_utils.make_lead_record`. Modules register
themselves via `@register_source("id")` so `routers/scraper.py` can iterate
the requested sources generically.
"""

from typing import Callable

SOURCE_REGISTRY: dict[str, Callable] = {}


def register_source(source_id: str):
    def decorator(fn: Callable) -> Callable:
        SOURCE_REGISTRY[source_id] = fn
        return fn
    return decorator


# Import each source module so its @register_source decorator runs.
from . import google_places  # noqa: E402,F401
from . import green_life  # noqa: E402,F401
from . import datos_gob  # noqa: E402,F401
from . import overpass  # noqa: E402,F401
from . import paginas_amarillas  # noqa: E402,F401
from . import ecored  # noqa: E402,F401

DEFAULT_SOURCES = ["green_life", "overpass", "datos_gob"]
