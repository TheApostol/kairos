"""datos.jus.gob.ar "Registro Nacional de Sociedades" source.

Free CKAN API, no key required — national company registry (razón social +
fiscal address + activity code). Carries **no contact info**, so these are
pure seed leads for the enrichment pass (which discovers a website and
scrapes it for email/phone/instagram).
"""

import csv
import io
import re
import tempfile
import zipfile
from typing import Iterator, Optional

from constants.scraper_targets import RNS_RELEVANT_CLAE_PREFIXES, RNS_RELEVANT_KEYWORDS
from services.scraping_utils import RateLimiter, fetch_with_retries, make_lead_record
from . import register_source

CKAN_BASE = "https://datos.jus.gob.ar"
PACKAGE_ID = "ee83de85-4305-4c53-9a9f-fd3d15e42c36"

_rate_limiter = RateLimiter(min_interval=1.0)

# Small, fast, no-key resource — safe default. Annual ZIPs are much larger
# and only fetched when `use_full_dataset=True` is explicitly requested.
_MUESTREO_RESOURCE_NAME = "Registro Nacional de Sociedades - Muestreo"


def _find_resource_url(name_substr: str) -> Optional[tuple[str, str]]:
    """Returns (resource_url, format) for the first resource whose name
    contains `name_substr`, or None."""
    resp = fetch_with_retries(
        f"{CKAN_BASE}/api/3/action/package_show",
        rate_limiter=_rate_limiter,
        params={"id": PACKAGE_ID},
        timeout=30,
    )
    if resp is None or resp.status_code != 200:
        return None
    try:
        result = resp.json().get("result", {})
    except Exception:
        return None

    for res in result.get("resources", []):
        if name_substr.lower() in (res.get("name") or "").lower():
            return res.get("url"), (res.get("format") or "").upper()
    return None


def _is_relevant(row: dict) -> bool:
    codigo = (row.get("actividad_codigo") or "").strip()
    if codigo and any(codigo.startswith(prefix) for prefix in RNS_RELEVANT_CLAE_PREFIXES):
        return True

    haystack = f"{row.get('razon_social', '')} {row.get('actividad_descripcion', '')}".lower()
    return any(kw in haystack for kw in RNS_RELEVANT_KEYWORDS)


def _make_record_from_row(row: dict, tipo_cliente: str) -> dict:
    direccion = " ".join(
        filter(None, [row.get("dom_fiscal_calle", "").strip(), row.get("dom_fiscal_numero", "").strip()])
    )
    cuit = row.get("cuit", "").strip()
    actividad = row.get("actividad_descripcion", "").strip()
    codigo = row.get("actividad_codigo", "").strip()
    observaciones_parts = []
    if cuit:
        observaciones_parts.append(f"CUIT: {cuit}")
    if codigo or actividad:
        observaciones_parts.append(f"CLAE: {codigo} {actividad}".strip())

    return make_lead_record(
        empresa=row.get("razon_social", "").strip(),
        rubro=actividad or "Registro Nacional de Sociedades",
        direccion=direccion,
        ciudad=row.get("dom_fiscal_localidad", "").strip(),
        provincia=row.get("dom_fiscal_provincia", "").strip().title(),
        observaciones=" | ".join(observaciones_parts),
        fuente="datos.gob.ar - Registro Nacional de Sociedades",
        tipo_cliente=tipo_cliente,
    )


def _iter_plain_csv_rows(resource_url: str) -> Iterator[dict]:
    resp = fetch_with_retries(resource_url, rate_limiter=_rate_limiter, timeout=60)
    if resp is None or resp.status_code != 200:
        return
    text = resp.content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        yield row


def _iter_zip_csv_rows(resource_url: str) -> Iterator[dict]:
    """Downloads a full annual ZIP to a temp file and streams its CSV.

    Best-effort: these ZIPs can be large, so this path is opt-in
    (`use_full_dataset=True`) rather than the default.
    """
    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        with fetch_with_retries(
            resource_url, rate_limiter=_rate_limiter, timeout=300
        ) and httpx_stream_to_file(resource_url, tmp.name):
            pass

        with zipfile.ZipFile(tmp.name) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                return
            with zf.open(csv_names[0]) as f:
                wrapper = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                reader = csv.DictReader(wrapper)
                for row in reader:
                    yield row


def httpx_stream_to_file(url: str, path: str):
    """Context manager-ish helper: streams `url` to `path` on disk."""
    import httpx
    from services.scraping_utils import DEFAULT_HEADERS

    class _Ctx:
        def __enter__(self):
            with httpx.Client(timeout=300, follow_redirects=True) as client:
                with client.stream("GET", url, headers=DEFAULT_HEADERS) as resp:
                    with open(path, "wb") as f:
                        for chunk in resp.iter_bytes(chunk_size=1 << 16):
                            f.write(chunk)
            return self

        def __exit__(self, *exc):
            return False

    return _Ctx()


@register_source("datos_gob")
def iter_leads(
    *,
    max_records: int = 500,
    use_full_dataset: bool = False,
    tipo_cliente: str = "lead",
    **_kwargs,
) -> Iterator[dict]:
    """Yields relevant company records from the Registro Nacional de
    Sociedades. Defaults to the small "muestreo" sample resource; pass
    `use_full_dataset=True` to download the latest annual ZIP instead
    (much larger, slower)."""
    count = 0

    if use_full_dataset:
        found = _find_resource_url("Registro Nacional de Sociedades - 2026")
        if not found:
            return
        resource_url, fmt = found
        rows: Iterator[dict] = _iter_zip_csv_rows(resource_url) if fmt == "ZIP" else _iter_plain_csv_rows(resource_url)
    else:
        found = _find_resource_url(_MUESTREO_RESOURCE_NAME)
        if not found:
            return
        resource_url, _fmt = found
        rows = _iter_plain_csv_rows(resource_url)

    for row in rows:
        if count >= max_records:
            return
        if not row.get("razon_social"):
            continue
        if not _is_relevant(row):
            continue
        count += 1
        yield _make_record_from_row(row, tipo_cliente)
