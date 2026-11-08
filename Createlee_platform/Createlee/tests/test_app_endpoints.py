"""Flask test-client tests for CreateLee endpoints (no server, no Ollama needed)."""
from __future__ import annotations

import app


def _client():
    app.app.testing = True
    return app.app.test_client()


def test_status_returns_ollama_and_formats():
    with _client() as c:
        r = c.get("/api/status")
        assert r.status_code == 200
        body = r.get_json()
        assert body["platform"] == "Createlee"
        assert body["agent"] == "Engeznee"
        assert "csv" in body["formats"]
        assert "ollama" in body


def test_models_endpoint():
    with _client() as c:
        r = c.get("/api/models")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert "models" in body


def test_constitution_endpoint():
    with _client() as c:
        r = c.get("/api/constitution")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert body["loaded"] is True
        assert "CreateLee Constitution" in body["text"]
        assert "server_time_iso8601" in body


def test_scan_endpoint():
    with _client() as c:
        r = c.get("/api/scan")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        scan = body["scan"]
        assert "server_time_iso8601" in scan
        assert "ollama" in scan
        assert "signoff_strict_contract" in scan


def test_scan_no_sid_reports_no_session():
    with _client() as c:
        r = c.get("/api/scan")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert body["scan"]["session"] is None
        assert "finding" in body["scan"]


def test_repair_state_requires_sid():
    with _client() as c:
        r = c.get("/api/repair-state")
        assert r.status_code == 400
        r = c.post("/api/repair-state", json={"sid": "bad"})
        assert r.status_code == 400


def test_help_command():
    with _client() as c:
        r = c.post("/api/chat", json={"sid": "sHLP123456", "message": "help"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert "help" in body["reply"].lower() or "Engeznee" in body["reply"]


def test_status_command():
    with _client() as c:
        r = c.post("/api/chat", json={"sid": "sSTA123456", "message": "status"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert "Ollama" in body["reply"]
