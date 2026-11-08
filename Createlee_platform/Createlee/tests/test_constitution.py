"""Tests for the CreateLee constitution loader (binding rules on every load)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import constitution
import config


def _write_constitution(text: str) -> Path:
    p = Path(tempfile.mkdtemp()) / "CREATELEE_CONSTITUTION.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_constitution_reads_file(monkeypatch):
    p = _write_constitution("# My Constitution\nRule: never hallucinate.\n")
    monkeypatch.setattr(constitution, "CONSTITUTION_PATH", p)
    text = constitution.load_constitution()
    assert "never hallucinate" in text


def test_load_constitution_missing_never_raises(monkeypatch):
    monkeypatch.setattr(constitution, "CONSTITUTION_PATH",
                        Path(tempfile.mkdtemp()) / "DOES_NOT_EXIST.md")
    text = constitution.load_constitution()
    assert isinstance(text, str) and len(text) > 0


def test_system_prompt_injection_contains_binding_rules(monkeypatch):
    p = _write_constitution("# Constitution\nRule X: always humanize.\n")
    monkeypatch.setattr(constitution, "CONSTITUTION_PATH", p)
    block = constitution.system_prompt_injection(model_name="qwen3:8b",
                                                 source="ollama")
    assert "always humanize" in block
    assert "CREATELEE CONSTITUTION — BINDING ON EVERY TURN" in block
    assert "model        : qwen3:8b" in block or "qwen3:8b" in block
    assert "timestamp" in block
    assert "what changed" in block


def test_sign_in_and_last_sign_in_roundtrip(monkeypatch, tmp_path):
    # Point the audit log at a temp file.
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(constitution, "AUDIT_LOG_PATH", audit)
    rec = constitution.sign_in(model_name="qwen3:8b", source="startup",
                               extra={"note": "probe ok"})
    assert rec["event"] == "sign_in"
    assert rec["model"] == "qwen3:8b"
    assert "timestamp_iso8601" in rec and rec["timestamp_iso8601"].endswith("Z")
    assert "what_changed" in rec

    last = constitution.last_sign_in()
    assert last is not None
    assert last["event"] == "sign_in"
    assert last["model"] == "qwen3:8b"


def test_sign_out_writes_event(monkeypatch, tmp_path):
    audit = tmp_path / "audit2.jsonl"
    monkeypatch.setattr(constitution, "AUDIT_LOG_PATH", audit)
    constitution.sign_in(model_name="ornith-1.5:9b", source="ollama")
    out = constitution.sign_out(extra={"bye": True})
    assert out["event"] == "sign_out"
    assert "timestamp_iso8601" in out

    lines = [json.loads(l) for l in audit.read_text(encoding="utf-8").splitlines() if l.strip()]
    events = [l["event"] for l in lines]
    assert events == ["sign_in", "sign_out"]


def test_injection_mentions_no_hallucination_and_adhd(monkeypatch):
    p = _write_constitution("# C\n")
    monkeypatch.setattr(constitution, "CONSTITUTION_PATH", p)
    block = constitution.system_prompt_injection(model_name=None, source="offline-fallback")
    assert "Never invent, hallucinate, or pretend" in block
    assert "ADHD reply style" in block
    assert "Local Ollama free models only" in block
    assert "(none — offline fallback)" in block


def test_cloud_not_configured_by_default():
    assert config.CLOUD_LLM_URL == "" or not config.CLOUD_LLM_KEY
