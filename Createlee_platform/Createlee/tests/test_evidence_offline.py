"""The evidence path must be offline: no socket may be opened while building.

This is the regression test for ME-05. Live web references are an explicit
opt-in (CREATELEE_WEB_ENRICH=1); the evidence pack itself is derived only from
bundled samples and uploaded files.
"""
from __future__ import annotations

import socket

import evidence


def _no_network(*_args, **_kwargs):
    raise AssertionError("the evidence path attempted a network connection")


def test_building_the_evidence_pack_opens_no_sockets(tmp_path, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)

    result = evidence.build_pack(tmp_path, as_of="2026-11-06")

    assert (tmp_path / "INDEX.csv").is_file()
    assert (tmp_path / "qa_reviews.csv").is_file()
    assert result["report_document_id"].startswith("CL-")


def test_web_enrichment_defaults_to_off(monkeypatch):
    import importlib

    import config

    monkeypatch.delenv("CREATELEE_WEB_ENRICH", raising=False)
    reloaded = importlib.reload(config)
    try:
        assert reloaded.WEB_ENRICH is False
    finally:
        monkeypatch.undo()
        importlib.reload(config)
