"""Tests for the secure-by-default secret and bind rules (HI-09)."""
from __future__ import annotations

import pytest

import app
import config

INSECURE_DEFAULT = "createlee-local-dev-key-change-me"


def test_secret_key_is_never_the_shared_default():
    assert config.SECRET_KEY != INSECURE_DEFAULT
    assert len(config.SECRET_KEY) >= 32


def test_loopback_detection():
    for host in ("127.0.0.1", "127.0.0.5", "::1", "localhost", "LOCALHOST"):
        assert config.is_loopback(host), host
    for host in ("0.0.0.0", "::", "10.0.0.4", "example.com", ""):
        assert not config.is_loopback(host), host


def test_loopback_bind_needs_no_configuration():
    config.validate_runtime("127.0.0.1")  # must not raise


def test_non_loopback_bind_fails_closed_without_secret_and_token(monkeypatch):
    monkeypatch.setattr(config, "SECRET_KEY_IS_EPHEMERAL", True)
    monkeypatch.setattr(config, "AUTH_TOKEN", "")
    with pytest.raises(RuntimeError) as excinfo:
        config.validate_runtime("0.0.0.0")
    message = str(excinfo.value)
    assert "CREATELEE_SECRET_KEY" in message
    assert "CREATELEE_AUTH_TOKEN" in message


def test_non_loopback_bind_accepts_stable_secret_and_token(monkeypatch):
    monkeypatch.setattr(config, "SECRET_KEY_IS_EPHEMERAL", False)
    monkeypatch.setattr(config, "SECRET_KEY", "s" * 48)
    monkeypatch.setattr(config, "AUTH_TOKEN", "t" * 32)
    config.validate_runtime("0.0.0.0")  # must not raise


def test_short_auth_token_is_rejected_for_non_loopback(monkeypatch):
    monkeypatch.setattr(config, "SECRET_KEY_IS_EPHEMERAL", False)
    monkeypatch.setattr(config, "SECRET_KEY", "s" * 48)
    monkeypatch.setattr(config, "AUTH_TOKEN", "too-short")
    with pytest.raises(RuntimeError):
        config.validate_runtime("0.0.0.0")


def test_routes_require_bearer_token_when_configured(monkeypatch):
    monkeypatch.setattr(config, "AUTH_TOKEN", "a" * 32)
    app.app.testing = True
    with app.app.test_client() as client:
        assert client.get("/api/status").status_code == 401
        assert client.get("/api/status",
                          headers={"Authorization": "Bearer " + "a" * 32}).status_code == 200
        assert client.get("/api/status",
                          headers={"X-Createlee-Token": "a" * 32}).status_code == 200
        # A wrong token is still refused, and the health probe stays open.
        assert client.get("/api/status",
                          headers={"Authorization": "Bearer " + "b" * 32}).status_code == 401
        assert client.get("/healthz").status_code == 200


def test_routes_are_open_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(config, "AUTH_TOKEN", "")
    app.app.testing = True
    with app.app.test_client() as client:
        assert client.get("/api/status").status_code == 200
