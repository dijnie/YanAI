from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from services.storage.base import StorageBackend

# Logical dataset keys stored as JSON blobs in the key-value table.
_ACCOUNTS_KEY = "accounts"
_AUTH_KEYS_KEY = "auth_keys"
_USERS_KEY = "users"
_SESSIONS_KEY = "sessions"
_REDEEM_CODES_KEY = "redeem_codes"
_CHANNELS_KEY = "channels"
_PROMPT_LIBRARY_KEY = "prompt_library"
_IMAGE_RECORDS_KEY = "image_records"

_ALL_KEYS = (
    _ACCOUNTS_KEY,
    _AUTH_KEYS_KEY,
    _USERS_KEY,
    _SESSIONS_KEY,
    _REDEEM_CODES_KEY,
    _CHANNELS_KEY,
    _PROMPT_LIBRARY_KEY,
    _IMAGE_RECORDS_KEY,
)


class D1StorageError(RuntimeError):
    """Raised when the Cloudflare D1 HTTP API returns an error."""


class D1StorageBackend(StorageBackend):
    """Cloudflare D1 storage backend.

    Cloudflare D1 is only reachable over its HTTP REST API (there is no
    SQLAlchemy/DBAPI driver), so this backend talks to the
    ``/d1/database/{id}/query`` endpoint directly. Each logical dataset
    (accounts, auth_keys, users, ...) is persisted as a single JSON-encoded
    list in a key-value table, mirroring the shape the rest of the app expects.
    """

    def __init__(
        self,
        account_id: str,
        database_id: str,
        api_token: str,
        table_name: str = "storage_kv",
        api_base: str = "https://api.cloudflare.com/client/v4",
        timeout: float = 30.0,
    ) -> None:
        if not account_id:
            raise ValueError("D1_ACCOUNT_ID is required for the d1 storage backend.")
        if not database_id:
            raise ValueError("D1_DATABASE_ID is required for the d1 storage backend.")
        if not api_token:
            raise ValueError("D1_API_TOKEN is required for the d1 storage backend.")

        self.account_id = account_id
        self.database_id = database_id
        self.api_token = api_token
        self.table_name = _safe_identifier(table_name)
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self._endpoint = (
            f"{self.api_base}/accounts/{self.account_id}"
            f"/d1/database/{self.database_id}/query"
        )

        self._ensure_table()

    # ------------------------------------------------------------------
    # HTTP / SQL plumbing
    # ------------------------------------------------------------------
    def _query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Run a single SQL statement against D1 and return the result rows."""
        body = json.dumps({"sql": sql, "params": params or []}).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise D1StorageError(
                f"D1 query failed (HTTP {exc.code}): {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise D1StorageError(f"D1 query request failed: {exc.reason}") from exc

        if not payload.get("success", False):
            raise D1StorageError(f"D1 query returned errors: {payload.get('errors')}")

        result = payload.get("result") or []
        if not result:
            return []
        # D1 returns a list of statement results; we only ever send one statement.
        return result[0].get("results") or []

    def _ensure_table(self) -> None:
        self._query(
            f"CREATE TABLE IF NOT EXISTS {self.table_name} "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )

    def _load_list(self, key: str) -> list[dict[str, Any]]:
        rows = self._query(
            f"SELECT value FROM {self.table_name} WHERE key = ?",
            [key],
        )
        if not rows:
            return []
        raw = rows[0].get("value")
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        return data if isinstance(data, list) else []

    def _save_list(self, key: str, items: list[dict[str, Any]]) -> None:
        value = json.dumps(items, ensure_ascii=False)
        self._query(
            f"INSERT INTO {self.table_name} (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [key, value],
        )

    # ------------------------------------------------------------------
    # StorageBackend interface
    # ------------------------------------------------------------------
    def load_accounts(self) -> list[dict[str, Any]]:
        return self._load_list(_ACCOUNTS_KEY)

    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        self._save_list(_ACCOUNTS_KEY, accounts)

    def load_auth_keys(self) -> list[dict[str, Any]]:
        return self._load_list(_AUTH_KEYS_KEY)

    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        self._save_list(_AUTH_KEYS_KEY, auth_keys)

    def load_users(self) -> list[dict[str, Any]]:
        return self._load_list(_USERS_KEY)

    def save_users(self, users: list[dict[str, Any]]) -> None:
        self._save_list(_USERS_KEY, users)

    def load_sessions(self) -> list[dict[str, Any]]:
        return self._load_list(_SESSIONS_KEY)

    def save_sessions(self, sessions: list[dict[str, Any]]) -> None:
        self._save_list(_SESSIONS_KEY, sessions)

    def load_redeem_codes(self) -> list[dict[str, Any]]:
        return self._load_list(_REDEEM_CODES_KEY)

    def save_redeem_codes(self, redeem_codes: list[dict[str, Any]]) -> None:
        self._save_list(_REDEEM_CODES_KEY, redeem_codes)

    def load_channels(self) -> list[dict[str, Any]]:
        return self._load_list(_CHANNELS_KEY)

    def save_channels(self, channels: list[dict[str, Any]]) -> None:
        self._save_list(_CHANNELS_KEY, channels)

    def load_prompt_library(self) -> list[dict[str, Any]]:
        return self._load_list(_PROMPT_LIBRARY_KEY)

    def save_prompt_library(self, prompts: list[dict[str, Any]]) -> None:
        self._save_list(_PROMPT_LIBRARY_KEY, prompts)

    def load_image_records(self) -> list[dict[str, Any]]:
        return self._load_list(_IMAGE_RECORDS_KEY)

    def save_image_records(self, image_records: list[dict[str, Any]]) -> None:
        self._save_list(_IMAGE_RECORDS_KEY, image_records)

    def health_check(self) -> dict[str, Any]:
        try:
            self._query(f"SELECT 1 FROM {self.table_name} LIMIT 1")
            return {
                "status": "healthy",
                "backend": "d1",
                "database_id": self.database_id,
                "table": self.table_name,
            }
        except Exception as exc:  # noqa: BLE001 - surfaced as health status
            return {
                "status": "unhealthy",
                "backend": "d1",
                "error": str(exc),
            }

    def get_backend_info(self) -> dict[str, Any]:
        return {
            "type": "d1",
            "description": "Cloudflare D1 (HTTP API) key-value storage",
            "account_id": self.account_id,
            "database_id": self.database_id,
            "table": self.table_name,
            "api_base": self.api_base,
            "datasets": list(_ALL_KEYS),
        }


def _safe_identifier(name: str) -> str:
    """Validate a SQL identifier (table name) since it cannot be parameterised."""
    candidate = (name or "").strip()
    if not candidate or not all(c.isalnum() or c == "_" for c in candidate):
        raise ValueError(
            f"Invalid D1 table name: {name!r}. Use only letters, digits and underscores."
        )
    return candidate
