from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import (
    AuthenticationError,
    AuthRepository,
    AuthService,
    PasswordHasher,
    Role,
    TokenService,
)
from backend.app.config import Settings
from backend.app.main import app
from backend.app.security import RateLimiter
from backend.tests.api_auth import authenticate


SECRET = "test-token-secret-at-least-thirty-two-characters"


def test_password_is_salted_hashed_and_not_stored_as_plaintext(tmp_path: Path):
    repository = AuthRepository(tmp_path / "auth.db")
    service = AuthService(repository, TokenService(SECRET), PasswordHasher(iterations=10_000))
    password = "StrongPrototypePassword!123"

    service.create_user("maintainer", password, Role.MAINTENANCE_ENGINEER)
    record = repository.user("maintainer")

    assert record is not None
    assert record["password_hash"] != password
    assert password not in record["password_hash"]
    assert record["password_hash"].startswith("pbkdf2_sha256$")
    assert service.hasher.verify(password, record["password_hash"])


def test_token_expiration_and_signature_are_enforced():
    tokens = TokenService(SECRET, lifetime_minutes=1)
    issued_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token, _ = tokens.issue("operator", Role.OPERATOR, issued_at)

    assert tokens.verify(token, issued_at + timedelta(seconds=59)).role is Role.OPERATOR
    with pytest.raises(AuthenticationError):
        tokens.verify(token, issued_at + timedelta(seconds=60))
    with pytest.raises(AuthenticationError):
        tokens.verify(token[:-1] + ("A" if token[-1] != "A" else "B"), issued_at)


def test_rate_limiter_hook_has_a_deterministic_window():
    limiter = RateLimiter(2)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert limiter.allow("subject:path", start)
    assert limiter.allow("subject:path", start)
    assert not limiter.allow("subject:path", start)
    assert limiter.allow("subject:path", start + timedelta(seconds=60))


def test_production_configuration_requires_persistent_secret(monkeypatch):
    monkeypatch.setenv("DIGITAL_TWIN_ENV", "production")
    monkeypatch.delenv("DIGITAL_TWIN_TOKEN_SECRET", raising=False)
    with pytest.raises(ValueError, match="production requires"):
        Settings()


def test_production_configuration_rejects_demo_auth_bypass(monkeypatch):
    monkeypatch.setenv("DIGITAL_TWIN_ENV", "production")
    monkeypatch.setenv("DIGITAL_TWIN_TOKEN_SECRET", SECRET)
    monkeypatch.setenv("DIGITAL_TWIN_DEMO_MODE", "true")
    with pytest.raises(ValueError, match="demo mode cannot be enabled in production"):
        Settings()


def test_rbac_request_id_and_denial_audit():
    username = f"viewer_{uuid4().hex[:10]}"
    password = "ViewerPrototypePassword!123"
    request_id = f"rbac-{uuid4().hex}"

    with TestClient(app) as client:
        authenticate(client)
        created = client.post(
            "/api/v1/auth/users",
            json={"username": username, "password": password, "role": "VIEWER"},
        )
        assert created.status_code == 201

        viewer_login = client.post(
            "/api/v1/auth/token", json={"username": username, "password": password}
        )
        assert viewer_login.status_code == 200
        viewer_token = viewer_login.json()["access_token"]

        denied = client.post(
            "/api/v1/telemetry",
            headers={"Authorization": f"Bearer {viewer_token}", "X-Request-ID": request_id},
            json={},
        )
        assert denied.status_code == 403
        assert denied.headers["x-request-id"] == request_id

        audit = client.get("/api/v1/auth/audit?limit=100")
        assert audit.status_code == 200
        event = next(item for item in audit.json() if item["request_id"] == request_id)
        assert event["actor"] == username
        assert event["role"] == "VIEWER"
        assert event["status"] == 403


def test_unauthenticated_protected_route_is_rejected():
    with TestClient(app) as client:
        response = client.get("/api/v1/missions")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
