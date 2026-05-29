import httpx
from typing import Any, Optional
from config import settings


class SupabaseClient:
    def __init__(self):
        self.base_url = settings.SUPABASE_URL.rstrip("/")
        self.headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _rest_url(self, table: str) -> str:
        return f"{self.base_url}/rest/v1/{table}"

    def select(
        self,
        table: str,
        filters: Optional[dict] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        select_cols: str = "*",
    ) -> list:
        params: dict[str, Any] = {"select": select_cols}

        if filters:
            for key, value in filters.items():
                params[key] = value

        if order:
            params["order"] = order

        if limit is not None:
            params["limit"] = limit

        if offset is not None:
            params["offset"] = offset

        headers = dict(self.headers)
        if limit and limit > 1000:
            headers["Range-Unit"] = "items"
            headers["Range"] = f"0-{limit - 1}"

        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self._rest_url(table),
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    def insert(self, table: str, data: dict) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                self._rest_url(table),
                headers=self.headers,
                json=data,
            )
            resp.raise_for_status()
            result = resp.json()
            if isinstance(result, list) and result:
                return result[0]
            return result

    def update(self, table: str, id: Any, data: dict) -> dict:
        params = {"id": f"eq.{id}"}
        update_headers = {**self.headers, "Prefer": "return=minimal"}
        with httpx.Client(timeout=30) as client:
            resp = client.patch(
                self._rest_url(table),
                headers=update_headers,
                params=params,
                json=data,
            )
            if not resp.is_success:
                raise Exception(f"Supabase PATCH error {resp.status_code}: {resp.text}")
            return {}

    def delete(self, table: str, id: Any) -> None:
        params = {"id": f"eq.{id}"}
        with httpx.Client(timeout=30) as client:
            resp = client.delete(
                self._rest_url(table),
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()

    def count(self, table: str, filters: Optional[dict] = None) -> int:
        params: dict[str, Any] = {"select": "id"}
        if filters:
            for key, value in filters.items():
                params[key] = value

        headers = dict(self.headers)
        headers["Prefer"] = "count=exact"
        headers["Range-Unit"] = "items"

        with httpx.Client(timeout=30) as client:
            resp = client.head(
                self._rest_url(table),
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            content_range = resp.headers.get("content-range", "0/0")
            if "/" in content_range:
                total_str = content_range.split("/")[1]
                if total_str == "*":
                    return 0
                return int(total_str)
            return 0

    def select_all(
        self,
        table: str,
        filters: Optional[dict] = None,
        select_cols: str = "*",
        batch: int = 1000,
    ) -> list:
        """Fetch all rows by paginating in batches."""
        results = []
        offset = 0
        while True:
            page = self.select(table, filters=filters, select_cols=select_cols,
                               limit=batch, offset=offset)
            results.extend(page)
            if len(page) < batch:
                break
            offset += batch
        return results

    def raw_select(
        self,
        table: str,
        params: dict,
    ) -> list:
        """Low-level select with raw params dict for complex filters."""
        headers = dict(self.headers)
        limit = params.get("limit")
        if limit and int(limit) > 1000:
            headers["Range-Unit"] = "items"
            headers["Range"] = f"0-{int(limit) - 1}"

        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self._rest_url(table),
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()


db = SupabaseClient()
