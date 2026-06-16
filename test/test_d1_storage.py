from __future__ import annotations

import json
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from services.storage.d1_storage import D1StorageBackend, D1StorageError, _safe_identifier
from services.storage.factory import create_storage_backend


def _d1_response(results: list[dict] | None = None, *, success: bool = True, errors=None):
    """Build a fake Cloudflare D1 query API JSON response body."""
    payload = {
        "success": success,
        "errors": errors or [],
        "messages": [],
        "result": [{"results": results or [], "success": success, "meta": {}}],
    }
    return json.dumps(payload).encode("utf-8")


class _FakeHTTPResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


class D1FactoryWiringTest(unittest.TestCase):
    def test_create_d1_backend_passes_env_vars(self) -> None:
        env = {
            "STORAGE_BACKEND": "d1",
            "D1_ACCOUNT_ID": "acct-123",
            "D1_DATABASE_ID": "db-456",
            "D1_API_TOKEN": "token-789",
            "D1_TABLE_NAME": "kv_table",
            "D1_API_BASE": "https://example.test/v4",
        }

        with mock.patch.dict("os.environ", env, clear=True), mock.patch(
            "services.storage.factory.D1StorageBackend"
        ) as backend_cls:
            create_storage_backend(Path("data"))

        backend_cls.assert_called_once_with(
            account_id="acct-123",
            database_id="db-456",
            api_token="token-789",
            table_name="kv_table",
            api_base="https://example.test/v4",
        )

    def test_cloudflare_alias_uses_d1_backend(self) -> None:
        env = {
            "STORAGE_BACKEND": "cloudflare",
            "D1_ACCOUNT_ID": "acct",
            "D1_DATABASE_ID": "db",
            "D1_API_TOKEN": "token",
        }

        with mock.patch.dict("os.environ", env, clear=True), mock.patch(
            "services.storage.factory.D1StorageBackend"
        ) as backend_cls:
            create_storage_backend(Path("data"))

        backend_cls.assert_called_once()
        kwargs = backend_cls.call_args.kwargs
        self.assertEqual(kwargs["table_name"], "storage_kv")
        self.assertEqual(kwargs["api_base"], "https://api.cloudflare.com/client/v4")

    def test_missing_required_config_raises(self) -> None:
        env = {"STORAGE_BACKEND": "d1", "D1_ACCOUNT_ID": "acct"}

        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(ValueError) as ctx:
                create_storage_backend(Path("data"))

        message = str(ctx.exception)
        self.assertIn("D1_DATABASE_ID", message)
        self.assertIn("D1_API_TOKEN", message)
        self.assertNotIn("D1_ACCOUNT_ID", message)


class D1StorageBackendTest(unittest.TestCase):
    def test_init_creates_table(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            D1StorageBackend("acct", "db", "token")

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertIn("CREATE TABLE IF NOT EXISTS storage_kv", body["sql"])
        self.assertEqual(
            request.headers["Authorization"], "Bearer token"
        )
        self.assertEqual(
            request.full_url,
            "https://api.cloudflare.com/client/v4/accounts/acct/d1/database/db/query",
        )

    def test_save_and_load_round_trip(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            backend = D1StorageBackend("acct", "db", "token")

            accounts = [{"access_token": "t", "user_id": "u"}]
            backend.save_accounts(accounts)
            save_body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
            self.assertIn("INSERT INTO storage_kv", save_body["sql"])
            self.assertIn("ON CONFLICT(key) DO UPDATE", save_body["sql"])
            self.assertEqual(save_body["params"][0], "accounts")
            self.assertEqual(json.loads(save_body["params"][1]), accounts)

            urlopen.return_value = _FakeHTTPResponse(
                _d1_response([{"value": json.dumps(accounts)}])
            )
            loaded = backend.load_accounts()
            self.assertEqual(loaded, accounts)
            load_body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
            self.assertIn("SELECT value FROM storage_kv WHERE key = ?", load_body["sql"])
            self.assertEqual(load_body["params"], ["accounts"])

    def test_load_returns_empty_when_no_row(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            backend = D1StorageBackend("acct", "db", "token")
            self.assertEqual(backend.load_channels(), [])

    def test_load_returns_empty_on_corrupt_json(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            backend = D1StorageBackend("acct", "db", "token")
            urlopen.return_value = _FakeHTTPResponse(
                _d1_response([{"value": "{not valid json"}])
            )
            self.assertEqual(backend.load_users(), [])

    def test_api_error_payload_raises(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            backend = D1StorageBackend("acct", "db", "token")
            urlopen.return_value = _FakeHTTPResponse(
                _d1_response(success=False, errors=[{"code": 7400, "message": "boom"}])
            )
            with self.assertRaises(D1StorageError):
                backend.load_accounts()

    def test_http_error_raises_d1_error(self) -> None:
        import urllib.error

        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            backend = D1StorageBackend("acct", "db", "token")
            urlopen.side_effect = urllib.error.HTTPError(
                "url", 403, "Forbidden", {}, BytesIO(b'{"error":"no"}')
            )
            with self.assertRaises(D1StorageError) as ctx:
                backend.save_users([])
            self.assertIn("403", str(ctx.exception))

    def test_health_check_healthy_and_unhealthy(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            backend = D1StorageBackend("acct", "db", "token")

            urlopen.return_value = _FakeHTTPResponse(_d1_response([{"1": 1}]))
            healthy = backend.health_check()
            self.assertEqual(healthy["status"], "healthy")
            self.assertEqual(healthy["backend"], "d1")

            urlopen.return_value = _FakeHTTPResponse(_d1_response(success=False))
            unhealthy = backend.health_check()
            self.assertEqual(unhealthy["status"], "unhealthy")
            self.assertIn("error", unhealthy)

    def test_get_backend_info(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = _FakeHTTPResponse(_d1_response())
            backend = D1StorageBackend("acct", "db", "token", table_name="kv")
            info = backend.get_backend_info()
            self.assertEqual(info["type"], "d1")
            self.assertEqual(info["table"], "kv")
            self.assertIn("accounts", info["datasets"])

    def test_missing_credentials_raise_value_error(self) -> None:
        with self.assertRaises(ValueError):
            D1StorageBackend("", "db", "token")
        with self.assertRaises(ValueError):
            D1StorageBackend("acct", "", "token")
        with self.assertRaises(ValueError):
            D1StorageBackend("acct", "db", "")

    def test_unsafe_table_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _safe_identifier("kv; DROP TABLE kv")
        self.assertEqual(_safe_identifier(" storage_kv "), "storage_kv")


if __name__ == "__main__":
    unittest.main()
