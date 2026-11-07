import os
import secrets

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TERRAVIA_DATABASE", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("TERRAVIA_CONTROL_KEY", secrets.token_urlsafe(40))
    from terravia.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def signed_in(client):
    response = client.post("/v1/auth/register", json={"email": "citizen@example.test", "password": "a-strong-password-123"})
    assert response.status_code == 201, response.text
    return client, response.json()["person_id"]


def csrf(client):
    token = client.cookies.get("tv_csrf")
    assert token
    return {"X-CSRF-Token": token}
