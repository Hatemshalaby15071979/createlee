"""CreateLee Constitution loader.

Responsibilities (binding, never optional):

  1. Read CREATELEE_CONSTITUTION.md from the repo root on every app load and
     every time a local Ollama model is loaded — before any skill, plugin, or
     instruction takes effect.
  2. Render a system-prompt injection block from the constitution rules, so the
     model is told (in its own words): no inventing / hallucinating / pretending,
     always humanize generated text, ADHD reply style, never lie or fake, clean
     code, local Ollama free models only, sign in / sign out always.
  3. Keep a "what changed + timestamp + which model" must-do log entry at every
     load and at every model bind.
  4. Record sign-in / sign-out events to a JSONL audit file.

Nothing in this module generates text. It only supplies rules and metadata.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

CONSTITUTION_PATH = Path(
    os.environ.get("CREATELEE_CONSTITUTION_PATH",
                   str(config.BASE_DIR / "CREATELEE_CONSTITUTION.md"))
)
AUDIT_LOG_PATH = Path(
    os.environ.get("CREATELEE_AUDIT_LOG_PATH",
                   str(config.OUTPUT_DIR / "createlee_constitution_audit.jsonl"))
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_constitution() -> str:
    """Return the constitution text, or a minimal binding stub if the file is missing.

    Never raises: the app must start even if the constitution file is temporarily
    unreadable, but the absence is logged as an honest finding.
    """
    try:
        if CONSTITUTION_PATH.is_file():
            return CONSTITUTION_PATH.read_text(encoding="utf-8")
    except OSError:  # noqa: BLE001
        pass
    return ("# CreateLee Constitution (stub)\n"
            "The constitution file could not be read. Binding rules are still in force: "
            "no hallucination, always humanize, ADHD style, local Ollama free models only.")


# --------------------------------------------------------------------------- #
# System-prompt injection
# --------------------------------------------------------------------------- #
def system_prompt_injection(model_name: str | None = None,
                            source: str | None = None) -> str:
    """Build the constitution block prepended to the agent system prompt.

    Returns a self-contained string the agent prepends to SYSTEM_PROMPT.
    """
    text = load_constitution()
    model_line = f"{model_name} ({source})" if model_name else "(none — offline fallback)"
    block = f"""\n\n===== CREATELEE CONSTITUTION — BINDING ON EVERY TURN =====
{text}

---- Must-do entry (this load) ----
what changed : constitution loaded; local Ollama model probed; skills/plugins/instructions injected
timestamp    : {_now_iso()}
model        : {model_line}
sign in      : {_now_iso()}
===============================================================

Binding rules for this session (read before generating):
- Never invent, hallucinate, or pretend. No fabricated data, names, numbers, dates, or URLs.
- If you do not know or cannot verify, say so.
- Always humanize generated text: warm, direct, executive-assistant tone. No generic filler, no placeholder data, no synthetic data passed off as real.
- ADHD reply style: lead with the answer, short paragraphs, bold key facts, compact bullets, one idea per line, no tangents.
- Never lie or fake any answer. Simulated content is labelled 'sample' / 'simulated'.
- Clean code: fail closed, explicit human approval before anything is saved or emailed, deterministic code owns commands.
- Local Ollama free models only; no cloud model unless CREATELEE_CLOUD_LLM_URL/KEY are set by the operator.
- Every generated document carries ISO-8601 UTC time, schema version, generator name, review status.
"""
    return block


# --------------------------------------------------------------------------- #
# Sign in / sign out audit
# --------------------------------------------------------------------------- #
def _audit_append(record: dict[str, Any]) -> None:
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        # Append-only audit log; never rewrite history.
    except OSError:  # noqa: BLE001
        pass


def sign_in(model_name: str | None = None,
            source: str | None = None,
            extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record a sign-in event: what changed + timestamp + which model.

    Returns the record so callers can surface it in the first reply.
    """
    record = {
        "event": "sign_in",
        "what_changed": ("constitution loaded; local Ollama model probed; "
                         "skills/plugins/instructions injected"),
        "timestamp_iso8601": _now_iso(),
        "model": model_name or "(none — offline fallback)",
        "model_source": source or "probe",
        "constitution": str(CONSTITUTION_PATH),
        **(extra or {}),
    }
    _audit_append(record)
    return record


def sign_out(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record a sign-out event."""
    record = {
        "event": "sign_out",
        "timestamp_iso8601": _now_iso(),
        "constitution": str(CONSTITUTION_PATH),
        **(extra or {}),
    }
    _audit_append(record)
    return record


def last_sign_in() -> dict[str, Any] | None:
    """Read the most recent sign_in record from the audit log (best effort)."""
    try:
        if not AUDIT_LOG_PATH.is_file():
            return None
        last = None
        for line in AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") == "sign_in":
                last = rec
        return last
    except OSError:  # noqa: BLE001
        return None
