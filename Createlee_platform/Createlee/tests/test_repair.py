"""Tests for the state.json absolute-path repair helper."""
from __future__ import annotations

import json
from pathlib import Path

import app
import config


def _write_state(sdir: Path, sid: str, uploads: list[dict]) -> None:
    state = {
        "sid": sid,
        "created_at_iso8601": "2026-11-06T00:00:00Z",
        "uploads": uploads,
        "history": [], "staged": [], "outputs": [],
        "options": {"include_timestamp": True},
    }
    (sdir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _session(sessions_root: Path, sid: str, filename: str,
             stale_path: str | None = None, valid_path: str | None = None,
             create_upload_file: bool = True) -> Path:
    sdir = sessions_root / sid
    up = sdir / "uploads"
    up.mkdir(parents=True)
    target = Path(valid_path) if valid_path else (up / filename if filename else None)
    if valid_path:
        Path(valid_path).parent.mkdir(parents=True, exist_ok=True)
        Path(valid_path).write_text("a,b\n1,2\n", encoding="utf-8")
    elif create_upload_file and filename:
        (up / filename).write_text("a,b\n1,2\n", encoding="utf-8")
    uploads = []
    for fn, path in ((filename, stale_path), (filename, valid_path)):
        if path is None:
            continue
        uploads.append({"filename": fn, "path": path, "size_bytes": 0,
                        "is_sample": True, "uploaded_at_iso8601": "2026-11-06T00:00:00Z",
                        "analysis": {"kind": "tabular", "rows": 1}})
    _write_state(sdir, sid, uploads)
    return sdir


def test_repair_repoints_stale_absolute_path(tmp_path, monkeypatch):
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(config, "SESSION_DIR", sessions_root)
    sid = "sABCD1234"
    filename = "questions.csv"
    stale = ("[LOCAL_PATH]/[REDACTED_VOLUME]/Career/CreateLee/"
             "old/sessions/" + sid + "/uploads/" + filename)
    _session(sessions_root, sid, filename, stale_path=stale)

    state = app.get_state(sid)
    entry = state["uploads"][0]
    assert Path(entry["path"]).is_file()
    assert entry["path"].endswith("uploads/" + filename)
    assert not entry["path"].startswith("[LOCAL_PATH]/[REDACTED_VOLUME]/Career/CreateLee")


def test_repair_leaves_valid_paths_untouched(tmp_path, monkeypatch):
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(config, "SESSION_DIR", sessions_root)
    sid = "sXY99999"
    filename = "mapping-table.template.csv"
    valid = str(sessions_root / sid / "uploads" / filename)
    _session(sessions_root, sid, filename, valid_path=valid)

    st = app.get_state(sid)
    assert st["uploads"][0]["path"] == valid


def test_repair_missing_file_stays_honest(tmp_path, monkeypatch):
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(config, "SESSION_DIR", sessions_root)
    sid = "sZZ99999"
    _session(sessions_root, sid, "questions.csv",
             stale_path="/nonexistent/whatever.csv",
             create_upload_file=False)

    st = app.get_state(sid)
    # No uploads/ file to re-point to -> stays as-is (honest, not silently fixed).
    assert st["uploads"][0]["path"] == "/nonexistent/whatever.csv"


def test_repair_api_dry_run_reports_candidates(tmp_path, monkeypatch):
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(config, "SESSION_DIR", sessions_root)
    sid = "sDRY12345"
    filename = "agents.csv"
    stale = ("[LOCAL_PATH]/[REDACTED_VOLUME]/Career/CreateLee/"
             "old/sessions/" + sid + "/uploads/" + filename)
    _session(sessions_root, sid, filename, stale_path=stale)

    with app.app.test_client() as client:
        resp = client.get("/api/repair-state?sid=" + sid)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["dry_run"] is True
        assert body["candidates"][0]["exists_now"] is True
        assert body["candidates"][0]["repaired_to"] is not None
        assert body["repaired"] is True
