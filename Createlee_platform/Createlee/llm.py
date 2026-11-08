"""LLM layer: local Ollama first, then an optional OpenAI-compatible endpoint.

Two responsibilities:

  1. Model management — list installed Ollama models, let the operator pick one,
     persist the choice, and start `ollama serve` automatically when it is not
     running. The web app calls `ensure_ollama()` at startup so the operator does
     not have to start the server by hand.

  2. Chat transport — `ollama_chat()` speaks Ollama's `/api/chat` including
     tool calling. `agent.py` owns the tool loop and the persona; this module
     only moves messages.

Reliability rule that has not changed: the deterministic command parser in
app.py still owns explicit commands. The LLM is used for genuine conversation,
reasoning and tool selection — never to silently change platform behaviour. If
nothing is reachable, every call returns cleanly and the UI says so.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import requests

import config
import constitution

SETTINGS_PATH = Path(os.environ.get("CREATELEE_SETTINGS_PATH",
                                    str(config.BASE_DIR / "settings.json")))

# Local-first: CreateLee uses available Ollama free models only. A cloud
# endpoint is used ONLY when the operator explicitly sets both URL and key.
_CLOUD_CONFIGURED = bool(config.CLOUD_LLM_URL and config.CLOUD_LLM_KEY)
_LAST_LOAD = {"at": 0.0, "model": None, "source": "none", "detail": ""}

DEFAULT_SETTINGS = {
    "model": "",
    "autostart": True,
    "temperature": 0.3,
    "max_steps": 6,
    "num_predict": 900,
}


# --------------------------------------------------------------------------- #
# Settings persistence
# --------------------------------------------------------------------------- #
def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    try:
        if SETTINGS_PATH.is_file():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                s.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    except Exception:  # noqa: BLE001 - a corrupt settings file must never stop the app
        pass
    return s


def save_settings(patch: dict) -> dict:
    s = load_settings()
    for k, v in (patch or {}).items():
        if k in DEFAULT_SETTINGS:
            s[k] = v
    try:
        SETTINGS_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return s


# --------------------------------------------------------------------------- #
# Ollama process management
# --------------------------------------------------------------------------- #
def _reachable(timeout: float = 1.5) -> bool:
    try:
        r = requests.get(config.OLLAMA_HOST + "/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _spawn_serve() -> tuple[bool, str]:
    """Start `ollama serve` detached. Returns (launched, detail)."""
    exe = shutil.which("ollama")
    if not exe:
        return False, "ollama binary not found on PATH"
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                  "stdin": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([exe, "serve"], **kwargs)
        return True, f"started {exe} serve"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


_LAST_START = {"at": 0.0, "ok": False, "detail": ""}


def ensure_ollama(wait_seconds: float = 12.0, force: bool = False) -> dict:
    """Make Ollama reachable, starting it if allowed. Idempotent and cheap.

    Called at app startup and from the Settings panel. Never raises.
    """
    if _reachable():
        _LAST_START.update({"ok": True, "detail": "already running", "at": time.time()})
        return {"ok": True, "started": False, "detail": "already running",
                "host": config.OLLAMA_HOST}

    s = load_settings()
    if not s["autostart"] and not force:
        return {"ok": False, "started": False, "detail": "autostart disabled",
                "host": config.OLLAMA_HOST}

    launched, detail = _spawn_serve()
    if not launched:
        _LAST_START.update({"ok": False, "detail": detail, "at": time.time()})
        return {"ok": False, "started": False, "detail": detail,
                "host": config.OLLAMA_HOST}

    deadline = time.time() + max(1.0, wait_seconds)
    while time.time() < deadline:
        if _reachable(timeout=1.0):
            _LAST_START.update({"ok": True, "detail": detail, "at": time.time()})
            return {"ok": True, "started": True, "detail": detail,
                    "host": config.OLLAMA_HOST}
        time.sleep(0.4)
    _LAST_START.update({"ok": False, "detail": "started but did not answer in time",
                        "at": time.time()})
    return {"ok": False, "started": True, "detail": "started but did not answer in time",
            "host": config.OLLAMA_HOST}


def start_ollama_background() -> None:
    """Fire-and-forget autostart for app boot (never blocks the first request)."""
    import threading
    threading.Thread(target=ensure_ollama, kwargs={"wait_seconds": 20.0},
                     daemon=True).start()


# --------------------------------------------------------------------------- #
# Model discovery / selection
# --------------------------------------------------------------------------- #
def available_models() -> list[str]:
    try:
        r = requests.get(config.OLLAMA_HOST + "/api/tags", timeout=3)
        if r.status_code != 200:
            return []
        return sorted({m.get("name") for m in r.json().get("models", []) if m.get("name")})
    except Exception:  # noqa: BLE001
        return []


def selected_model(models: list[str] | None = None) -> str:
    s = load_settings()
    models = available_models() if models is None else models
    if s["model"] and (not models or s["model"] in models):
        return s["model"]
    if config.OLLAMA_MODEL:
        return config.OLLAMA_MODEL
    return _rank(models)[0] if models else ""


# Preference order for the default when the operator has not chosen a model.
# Tool calling is the requirement, so models known to support it come first.
_PREFERRED = ("qwen3", "qwen2.5", "llama3.3", "llama3.2", "llama3.1", "mistral",
              "firefunction", "command-r", "granite3", "hermes3")


def _rank(models: list[str]) -> list[str]:
    def key(name: str):
        low = name.lower()
        for i, p in enumerate(_PREFERRED):
            if low.startswith(p) or p in low:
                return (i, name)
        return (len(_PREFERRED), name)
    return sorted(models, key=key)


def ollama_status() -> dict:
    models = available_models()
    s = load_settings()
    return {
        "available": bool(models),
        "host": config.OLLAMA_HOST,
        "models": models,
        "selected": selected_model(models),
        "autostart": s["autostart"],
        "last_start": dict(_LAST_START),
        "binary": shutil.which("ollama") or "",
    }


def probe_ollama() -> dict:
    """Probe the local Ollama server: reachability, installed models, binary.

    Local-first / free only. Returns a dict the app can log and surface.
    Never raises.
    """
    exe = shutil.which("ollama") or ""
    reachable = _reachable()
    models: list[str] = []
    detail = ""
    if reachable:
        try:
            r = requests.get(config.OLLAMA_HOST + "/api/tags", timeout=3)
            if r.status_code == 200:
                models = sorted({m.get("name") for m in r.json().get("models", [])
                                 if m.get("name")})
            else:
                detail = f"tags HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}"
    elif not exe:
        detail = "ollama binary not found on PATH"
    else:
        detail = "Ollama server not reachable at " + config.OLLAMA_HOST
    return {
        "available": reachable,
        "host": config.OLLAMA_HOST,
        "binary": exe,
        "models": models,
        "count": len(models),
        "detail": detail,
    }


def bind_model(model_name: str | None = None, source: str = "probe") -> dict:
    """Bind (select) a local Ollama model and record the load event.

    Logs via constitution.sign_in() so every load has: what changed, timestamp,
    and which model. Returns {ok, model, source, detail}.
    """
    probe = probe_ollama()
    models = probe["models"]
    chosen = (str(model_name or "").strip() or "").strip()
    if chosen and chosen not in models:
        return {"ok": False, "model": chosen, "source": source,
                "detail": f"'{chosen}' not installed. Available: {', '.join(models) or '(none)'}"}
    if not chosen:
        chosen = selected_model(models) or ""
    if chosen:
        save_settings({"model": chosen})
        _LAST_LOAD.update({"at": time.time(), "model": chosen, "source": source,
                           "detail": "bound"})
        constitution.sign_in(model_name=chosen, source=source,
                             extra={"ollama_host": config.OLLAMA_HOST,
                                    "cloud_configured": _CLOUD_CONFIGURED})
        return {"ok": True, "model": chosen, "source": source,
                "detail": f"local Ollama model bound: {chosen}"}
    _LAST_LOAD.update({"at": time.time(), "model": None, "source": source,
                       "detail": "no model installed"})
    constitution.sign_in(model_name=None, source=source,
                         extra={"ollama_host": config.OLLAMA_HOST,
                                "cloud_configured": _CLOUD_CONFIGURED,
                                "offline_fallback": True})
    return {"ok": False, "model": None, "source": source,
            "detail": "no local Ollama model installed — offline deterministic fallback"}


def status() -> dict:
    o = ollama_status()
    cloud = bool(config.CLOUD_LLM_URL and config.CLOUD_LLM_KEY)
    return {
        "ollama": o,
        "cloud": {"available": cloud, "model": config.CLOUD_LLM_MODEL or "(unset)"},
        "active": "ollama" if o["available"] else ("cloud" if cloud else "none"),
        "settings": load_settings(),
        "last_load": dict(_LAST_LOAD),
    }


# --------------------------------------------------------------------------- #
# Chat transport
# --------------------------------------------------------------------------- #
def _post(url: str, payload: dict, timeout: float):
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def ollama_chat(messages: list[dict], tools: list[dict] | None = None,
                model: str | None = None, temperature: float | None = None,
                num_predict: int | None = None) -> dict | None:
    """One non-streaming /api/chat turn. Returns the assistant message dict."""
    if not _reachable():
        return None
    s = load_settings()
    mdl = model or selected_model()
    if not mdl:
        return None
    payload = {
        "model": mdl,
        "messages": messages,
        "stream": False,
        "keep_alive": "30m",
        # Thinking models (qwen3 and friends) otherwise burn the whole token
        # budget on hidden reasoning and can return an EMPTY content field.
        "think": False,
        "options": {
            "temperature": s["temperature"] if temperature is None else temperature,
            "num_predict": num_predict or s["num_predict"],
        },
    }
    if tools:
        payload["tools"] = tools
    try:
        data = _post(config.OLLAMA_HOST + "/api/chat", payload, config.OLLAMA_TIMEOUT)
        return data.get("message") or None
    except Exception:  # noqa: BLE001
        # Older Ollama builds reject the `think` field; retry without it.
        if "think" in payload:
            payload.pop("think", None)
            try:
                data = _post(config.OLLAMA_HOST + "/api/chat", payload, config.OLLAMA_TIMEOUT)
                return data.get("message") or None
            except Exception:  # noqa: BLE001
                return None
        return None


def cloud_chat(messages: list[dict], tools: list[dict] | None = None) -> dict | None:
    if not (config.CLOUD_LLM_URL and config.CLOUD_LLM_KEY):
        return None
    payload = {
        "model": config.CLOUD_LLM_MODEL or "gpt-4o-mini",
        "messages": messages,
        "temperature": load_settings()["temperature"],
        "max_tokens": load_settings()["num_predict"],
    }
    if tools:
        payload["tools"] = [{"type": "function", "function": t["function"]} for t in tools]
    try:
        data = _post(config.CLOUD_LLM_URL, payload, config.OLLAMA_TIMEOUT)  # type: ignore[arg-type]
        return (data.get("choices") or [{}])[0].get("message")
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Backwards-compatible helpers used by the document pipeline
# --------------------------------------------------------------------------- #
def _ollama_generate(prompt: str, system: str = "") -> str | None:
    msg = ollama_chat([
        {"role": "system", "content": system or "You are Engeznee, a precise operations assistant."},
        {"role": "user", "content": prompt},
    ], tools=None)
    if not msg:
        return None
    return (msg.get("content") or "").strip() or None


def _cloud_generate(prompt: str, system: str = "") -> str | None:
    msg = cloud_chat([
        {"role": "system", "content": system or "You are Engeznee."},
        {"role": "user", "content": prompt},
    ])
    if not msg:
        return None
    return (msg.get("content") or "").strip() or None


def generate(prompt: str, system: str = "") -> tuple[str | None, str]:
    """Return (text, source). source is 'ollama' | 'cloud' | 'none'."""
    for name, fn in (("ollama", _ollama_generate), ("cloud", _cloud_generate)):
        out = fn(prompt, system)
        if out:
            return out, name
    return None, "none"


def polish(text: str, instruction: str) -> tuple[str, str]:
    """Best-effort prose polishing. Always returns usable text."""
    out, source = generate(
        f"{instruction}\n\n--- SOURCE TEXT ---\n{text[:6000]}\n--- END ---\n"
        "Rewrite only the prose. Keep every fact, number, date and field name exactly. "
        "Do not invent data. Output plain text.",
        system="You are Engeznee. You improve clarity of operational documents without adding or changing facts.",
    )
    return (out or text), source


def interpret(message: str, allowed: str) -> dict | None:
    """Legacy single-shot intent parser (kept for compatibility)."""
    out, _ = generate(
        f"Available commands: {allowed}\nUser request: {message!r}\n"
        'Reply with ONE JSON object only, e.g. {"intent":"generate","domains":["QA"],"formats":["pdf"]}. '
        "No prose, no code fences.",
        system="You output strict JSON only.",
    )
    if not out:
        return None
    try:
        start, end = out.find("{"), out.rfind("}")
        if start >= 0 and end > start:
            return json.loads(out[start:end + 1])
    except Exception:  # noqa: BLE001
        return None
    return None
