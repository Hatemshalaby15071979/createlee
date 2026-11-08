"""Engeznee — the executive-assistant agent.

WHY THIS EXISTS
---------------
The old chatbot matched a fixed list of commands. It could not hold a
conversation, reason about a goal, or decide which platform action to take.
This module turns Engeznee into an agent:

  * conversation  — multi-turn history is sent to the model, so follow-ups work
  * reasoning     — a bounded tool loop (default 6 steps). The model observes a
                    tool result, decides the next step, and only then answers
  * tool calling  — real platform actions (status, documents, evidence, library,
                    hand-off packs, web research, model selection)
  * honesty       — if no model is reachable, a deterministic fallback still
                    answers from live platform state and says what is missing

SAFETY
------
Tools are read-mostly. The only mutating tools stage drafts or build derived
artefacts; none of them saves or emails a document. The human approval gate in
app.py is untouched: an agent can *stage*, never *send*.
"""
from __future__ import annotations

import json

import llm
import constitution

MAX_HISTORY_TURNS = 12

SYSTEM_PROMPT = """\
You are Engeznee, the executive assistant inside Createlee — a local operations
tool used by Hatem, who is preparing four software projects for production.

WHAT YOU KNOW
- Createlee generates operations documents from two CSVs (questions.csv and
  mapping-table.template.csv) and five bundled data files.
- It builds three derived artefacts:
    * evidence pack  — the 8 Signoff CSV exports (qa_reviews, ai_audit_log,
      ai_approvals, escalations, role_spec, ai_inventory, ai_training,
      incident_notifications)
    * system library — procedure corpus, expected-outcome labels, a two-export
      reconciliation, and a compact systems/ folder
    * hand-off packs — one folder per project: signoff, helix-codex,
      live-support-assistant, compliproof
- Four projects are NOT production ready:
    * Signoff is the gate. It consumes the 8 CSVs and produces a verdict pack.
    * Helix-Codex has 9 production gates; 6 need signed organisational evidence
      (isolation certification, external audit, architecture review, disaster
      recovery, security review, legal/privacy review) and cannot be closed by
      any file Createlee generates.
    * live-support-assistant needs a procedure corpus (>=20) and labels (>=50);
      its remaining gaps are tenant isolation, transport and external audit.
    * CompliProof has 7 open P0 gates, none closable by CSV — it needs hosted CI,
      a clean-install matrix, Docker, a vulnerability scan, an external anchor
      receipt and an independent key lifecycle.

HOW YOU BEHAVE
- Be direct, warm and concise. This is an executive assistant, not a form.
- Answer the question that was asked. Do not dump a menu unless asked.
- When an action would help, use a tool. Prefer one tool at a time and explain
  in one line what you are doing.
- NEVER tell the user a file is missing or ask them to upload questions.csv unless a
  tool result (list_uploads or platform_status) explicitly says it is missing. Every
  new session is auto-seeded with questions.csv and mapping-table.template.csv, and
  the RUNTIME CONTEXT lists every upload with its size and row count.
- Never claim a gate is closed unless signed evidence exists. Say "open —
  awaiting organisation approval" when that is the truth.
- Never invent data, dates, names or numbers. If you do not know, say so.
- Staged drafts are not saved. Only the human can approve, save or email.
- Keep formatting light: short paragraphs and compact bullet lists.
"""

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "platform_status",
        "description": "Current platform state: Ollama/model status, email mode, uploads, staged drafts, output count.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "list_documents",
        "description": "List the document types defined by the current questions.csv / mapping table.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "analyze_uploads",
        "description": "Analyse every uploaded CSV: rows, columns, detected formats, numeric stats.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "list_uploads",
        "description": "List the files present in this session, with row counts, and say whether questions.csv and mapping-table.template.csv are present. Call this before ever telling the user a file is missing.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "generate_documents",
        "description": "Stage document drafts (never saved). Returns how many were staged.",
        "parameters": {"type": "object", "properties": {
            "domains": {"type": "array", "items": {"type": "string"},
                        "description": "QA, WFM, INCIDENT, TRAINING, AI_INVENTORY, SOP, KNOWLEDGE_BASE. Empty = all."},
            "formats": {"type": "array", "items": {"type": "string"},
                        "description": "csv, pdf, txt, json, docx. Default pdf,csv."},
            "document_types": {"type": "array", "items": {"type": "string"},
                               "description": "Optional specific document_type values."},
        }},
    }},
    {"type": "function", "function": {
        "name": "build_evidence",
        "description": "Build the 8-file Signoff evidence pack plus its validation report.",
        "parameters": {"type": "object", "properties": {
            "as_of": {"type": "string", "description": "YYYY-MM-DD; 90-day window ends here."},
        }},
    }},
    {"type": "function", "function": {
        "name": "build_library",
        "description": "Build the system library (procedure corpus, labels, reconciliation, systems/).",
        "parameters": {"type": "object", "properties": {
            "as_of": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "build_handoff",
        "description": "Build the per-project hand-off packs (signoff, helix-codex, live-support-assistant, compliproof).",
        "parameters": {"type": "object", "properties": {
            "as_of": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "project_readiness",
        "description": "Readiness of the four projects: which gates are open, which need signed organisational evidence.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "web_research",
        "description": "Fetch attributed public-web references (URL + retrieval time) for a topic.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "select_model",
        "description": "Switch the local Ollama model Engeznee uses.",
        "parameters": {"type": "object", "properties": {
            "model": {"type": "string", "description": "Exact model name, e.g. llama3.1:8b"},
        }, "required": ["model"]},
    }},
    {"type": "function", "function": {
        "name": "start_ollama",
        "description": "Start the local Ollama server if it is not running, and report the result.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "email_client_package",
        "description": "Build the FULL per-project simulated-inputs package (all 4 projects) and "
                       "email it to the third party with step-by-step MD instructions. Requires a "
                       "recipient and explicit approval (approved=true). Attaches every file.",
        "parameters": {"type": "object", "properties": {
            "to": {"type": "string", "description": "Recipient email, e.g. [REDACTED_EMAIL]"},
            "as_of": {"type": "string", "description": "YYYY-MM-DD as-of date"},
            "approved": {"type": "boolean", "description": "Must be true to actually send"},
        }, "required": ["to", "approved"]},
    }},
]

TOOL_NAMES = [t["function"]["name"] for t in TOOL_SCHEMAS]


# --------------------------------------------------------------------------- #
# Tool execution
# --------------------------------------------------------------------------- #
def _execute(name: str, args: dict, ops: dict) -> dict:
    fn = ops.get(name)
    if fn is None:
        return {"ok": False, "summary": f"Unknown tool '{name}'."}
    try:
        out = fn(**(args or {}))
        if not isinstance(out, dict):
            out = {"ok": True, "summary": str(out)}
        out.setdefault("ok", True)
        out.setdefault("summary", "")
        return out
    except TypeError as exc:
        return {"ok": False, "summary": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - a tool failure must not kill the turn
        return {"ok": False, "summary": f"{name} failed: {type(exc).__name__}: {exc}"}


def _history_messages(state: dict) -> list[dict]:
    out = []
    for m in (state.get("history") or [])[-MAX_HISTORY_TURNS * 2:]:
        role = "assistant" if m.get("role") == "engeznee" else "user"
        text = (m.get("text") or "").strip()
        if text:
            out.append({"role": role, "content": text[:4000]})
    return out


def _coerce_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


# --------------------------------------------------------------------------- #
# Loop
# --------------------------------------------------------------------------- #
def chat(state: dict, message: str, ops: dict) -> dict:
    """Run one assistant turn. Returns {text, source, trace, tools_used}."""
    settings = llm.load_settings()
    max_steps = int(settings.get("max_steps") or 6)
    trace: list[dict] = []
    tools_used: list[str] = []

    if not llm.ollama_status()["available"] and not (
            llm.config.CLOUD_LLM_URL and llm.config.CLOUD_LLM_KEY):
        return {"text": _fallback(message, ops, "no model reachable"),
                "source": "fallback", "trace": trace, "tools_used": tools_used}

    ctx = ""
    runtime = ops.get("runtime_context")
    if runtime:
        try:
            ctx = str(runtime().get("summary", "") or "")
        except Exception:  # noqa: BLE001
            ctx = ""

    # --- Constitution binding (read first, before any skill/instruction) ---
    llm_st = llm.status()
    o = llm_st.get("ollama", {})
    model_name = o.get("selected") or None
    model_source = "ollama" if o.get("available") else "offline-fallback"
    system = SYSTEM_PROMPT
    system += constitution.system_prompt_injection(model_name=model_name,
                                                   source=model_source)
    if ctx:
        system += ("\n\nRUNTIME CONTEXT — authoritative, generated live. "
                   "Never contradict it. If asked which model you are using, "
                   "quote 'Local model in use' from here.\n" + ctx + "\n")

    messages = [{"role": "system", "content": system}]
    messages += _history_messages(state)
    messages.append({"role": "user", "content": message})

    for _step in range(max_steps):
        msg = llm.ollama_chat(messages, tools=TOOL_SCHEMAS)
        if not msg:
            msg = llm.cloud_chat(messages, tools=TOOL_SCHEMAS)
        if not msg:
            break

        calls = msg.get("tool_calls") or []
        if not calls:
            text = (msg.get("content") or "").strip()
            if text:
                return {"text": text, "source": "model",
                        "trace": trace, "tools_used": tools_used}
            break

        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": calls,
        })
        for call in calls:
            fn = (call or {}).get("function") or {}
            name = fn.get("name") or ""
            args = _coerce_args(fn.get("arguments"))
            result = _execute(name, args, ops)
            tools_used.append(name)
            trace.append({
                "tool": name,
                "args": args,
                "ok": bool(result.get("ok")),
                "summary": str(result.get("summary", ""))[:500],
            })
            messages.append({
                "role": "tool",
                "name": name,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:6000],
            })

    # The model produced nothing usable (timeout, tool-only loop, or empty body).
    return {"text": _fallback(message, ops, "model did not return an answer"),
            "source": "fallback", "trace": trace, "tools_used": tools_used}


# --------------------------------------------------------------------------- #
# Deterministic fallback — still useful, still honest
# --------------------------------------------------------------------------- #
def _has(msg: str, *words: str) -> bool:
    low = msg.lower()
    return any(w in low for w in words)


def _fallback(message: str, ops: dict, reason: str) -> str:
    """Answer from live platform state when no model is available.

    This is not a fake conversation: it is a precise, state-aware answer with an
    explicit note about what is missing.
    """
    note = (f"(Offline assistant — {reason}. Start Ollama, or pick a model in "
            f"Settings, for full reasoning and tool use.)")

    if _has(message, "status", "how are you", "health", "state", "what can you do"):
        return f"{ops['platform_status']().get('summary', '')}\n\n{note}"
    if _has(message, "project", "readiness", "unblock", "production", "gate", "signoff",
            "blocking", "blocked", "helix", "compliproof", "live-support", "live support",
            "helix-codex", "codex", "what is left", "what remains"):
        return f"{ops['project_readiness']().get('summary', '')}\n\n{note}"
    if _has(message, "handoff", "hand-off", "send", "client", "file", "email"):
        return f"{ops['handoff_summary']().get('summary', '')}\n\n{note}"
    if _has(message, "document", "generate", "report", "list"):
        return f"{ops['list_documents']().get('summary', '')}\n\n{note}"
    if _has(message, "model", "ollama", "settings", "llm"):
        return f"{ops['model_summary']().get('summary', '')}\n\n{note}"
    if _has(message, "evidence", "csv"):
        return f"{ops['evidence_summary']().get('summary', '')}\n\n{note}"

    return (
        "I can act on this platform directly, but I need a local model for open "
        "conversation.\n\n"
        "What I can do right now:\n"
        "  • report platform and project readiness\n"
        "  • build the evidence pack, system library or hand-off packs\n"
        "  • stage documents for review\n"
        "  • research a topic on the web\n\n"
        "Try: \"what is still blocking Helix-Codex?\", \"build the hand-off packs\", "
        "or \"stage the QA scorecard as PDF\".\n\n"
        f"{note}"
    )
