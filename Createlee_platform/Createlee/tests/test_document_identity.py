"""Tests for unique document identity and the single status ledger (ME-02)."""
from __future__ import annotations

import json

import config
import core
import evidence


def test_same_second_generation_produces_distinct_document_ids(monkeypatch):
    monkeypatch.setattr(core, "compact_stamp", lambda: "20261106T233408Z")
    first = core.new_document_id("QA", "qa_report", "2026-11-06T23:34:08Z")
    second = core.new_document_id("QA", "qa_report", "2026-11-06T23:34:08Z")
    assert first != second
    assert first.startswith("CL-20261106T233408Z-QA-")
    assert len(first.split("-")) == 4


def test_status_ledger_is_the_single_source_of_truth(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSION_DIR", tmp_path)
    core.set_document_status("CL-TEST-0001", "APPROVED", actor="tester")
    assert core.resolve_status("CL-TEST-0001", "PENDING") == "APPROVED"
    assert core.resolve_status("CL-UNKNOWN", "PENDING") == "PENDING"
    ledger = json.loads((tmp_path / "document_status.json").read_text(encoding="utf-8"))
    assert ledger["CL-TEST-0001"]["status"] == "APPROVED"
    assert ledger["CL-TEST-0001"]["history"][0]["by"] == "tester"


def test_status_transitions_are_appended(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSION_DIR", tmp_path)
    core.set_document_status("CL-TEST-0002", "PENDING_APPROVAL")
    core.set_document_status("CL-TEST-0002", "APPROVED")
    ledger = json.loads((tmp_path / "document_status.json").read_text(encoding="utf-8"))
    history = [item["status"] for item in ledger["CL-TEST-0002"]["history"]]
    assert history == ["PENDING_APPROVAL", "APPROVED"]


def test_report_document_status_comes_from_the_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSION_DIR", tmp_path)
    monkeypatch.setattr(core, "new_document_id", lambda *a, **k: "CL-FIXED-EVID-0001")
    report = {
        "as_of": "2026-11-06",
        "window_start": "2026-08-08",
        "window_end": "2026-11-06",
        "files": [],
        "summary": {"total_gaps_reported": 0, "total_rows_preserved": 0},
        "alias_map": {},
        "disclaimer": "test",
    }
    pending = evidence.build_report_doc(report)
    assert pending["meta"]["review_status"].startswith("EXAMPLE_PREVIEW")

    core.set_document_status("CL-FIXED-EVID-0001", "APPROVED", actor="tester")
    approved = evidence.build_report_doc(report)
    assert approved["meta"]["review_status"] == "APPROVED"
