"""Small Supabase HTTP transport shared by the backend services."""

from urllib.parse import urlsplit

import httpx


class SupabaseError(RuntimeError):
    def __init__(self, operation: str, status: int | None = None, code: str | None = None):
        self.status = status
        self.code = code
        detail = f"HTTP {status}" if status is not None else "connection failed"
        super().__init__(f"Supabase {operation} failed ({detail}).")


def require_publishable_key(key: str) -> None:
    if not key.startswith("sb_publishable_"):
        raise ValueError("A Supabase publishable key is required for user access.")


class SupabaseAPI:
    """An explicitly scoped connection. Tokens and response bodies stay out of errors."""

    def __init__(self, url: str, key: str, access_token: str | None = None):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.path.rstrip("/") or parsed.query or parsed.fragment):
            raise ValueError("Use the HTTPS project URL from Supabase.")
        headers = {"apikey": key}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        self._client = httpx.Client(base_url=url.rstrip("/"), headers=headers, timeout=20)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._client.close()

    def request(self, method: str, path: str, *, operation: str, **kwargs):
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.RequestError:
            raise SupabaseError(operation) from None
        if not response.is_success:
            try:
                body = response.json()
                code = (body.get("error_code") or body.get("code")) if isinstance(body, dict) else None
            except ValueError:
                code = None
            raise SupabaseError(operation, response.status_code, code)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise SupabaseError(operation, response.status_code) from None

    def select(self, table: str, columns: str, *, order: str, **filters) -> list[dict]:
        rows = []
        page_size = 100
        while True:
            page = self.request("GET", f"/rest/v1/{table}", operation=f"read {table}", params={
                "select": columns, "order": order, "limit": page_size, "offset": len(rows), **filters,
            })
            rows.extend(page)
            if len(page) < page_size:
                return rows
