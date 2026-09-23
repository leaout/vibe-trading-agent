# coding: utf-8
import unittest

from fastapi.testclient import TestClient

from trading_v2.api import create_app
from trading_v2.config import AppSettings


class TradingV2AuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = AppSettings(
            database_url="sqlite:///:memory:", auth_enabled=True, _env_file=None,
        )

    def test_first_user_registration_and_cookie_protection(self) -> None:
        with TestClient(create_app(settings=self.settings)) as client:
            before = client.get("/api/v2/auth/me")
            blocked = client.get("/api/v2/sessions")
            registered = client.post("/api/v2/auth/register", json={
                "username": "alice", "password": "correct-horse-battery",
            })
            me = client.get("/api/v2/auth/me")
            sessions = client.get("/api/v2/sessions")
            duplicate = client.post("/api/v2/auth/register", json={
                "username": "bob", "password": "another-password",
            })
            logout = client.post("/api/v2/auth/logout")
            after = client.get("/api/v2/sessions")

            self.assertEqual(before.status_code, 200)
            self.assertFalse(before.json()["authenticated"])
            self.assertEqual(blocked.status_code, 401)
            self.assertEqual(registered.status_code, 201)
            self.assertEqual(registered.json()["username"], "alice")
            self.assertTrue(me.json()["authenticated"])
            self.assertEqual(sessions.status_code, 200)
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(logout.status_code, 204)
            self.assertEqual(after.status_code, 401)

    def test_invalid_login_is_rejected(self) -> None:
        with TestClient(create_app(settings=self.settings)) as client:
            client.post("/api/v2/auth/register", json={
                "username": "alice", "password": "correct-horse-battery",
            })
            client.post("/api/v2/auth/logout")
            invalid = client.post("/api/v2/auth/login", json={
                "username": "alice", "password": "wrong-password",
            })
            self.assertEqual(invalid.status_code, 401)


if __name__ == "__main__":
    unittest.main()
