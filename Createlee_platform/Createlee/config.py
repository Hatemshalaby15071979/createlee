"""Createlee configuration. All optional integrations degrade gracefully."""
from __future__ import annotations

import os
import secrets
import warnings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from .env into os.environ (existing vars win).

    run.sh already sources .env, but launching with `python app.py` directly did
    not — so editing .env appeared to do nothing. Load it here, once, for both.
    Never raises: a malformed .env must not stop the app.
    """
    try:
        if not path.is_file():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:  # noqa: BLE001
        pass


_load_dotenv(BASE_DIR / ".env")

SAMPLES_DIR = BASE_DIR / "samples"
OUTPUT_DIR = Path(os.environ.get("CREATELEE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
SESSION_DIR = Path(os.environ.get("CREATELEE_SESSION_DIR", str(BASE_DIR / "sessions")))
EVIDENCE_DIR = Path(os.environ.get("CREATELEE_EVIDENCE_DIR", str(BASE_DIR / "evidence_pack")))
LIBRARY_DIR = Path(os.environ.get("CREATELEE_LIBRARY_DIR", str(BASE_DIR / "system_library")))
# Per-project, ready-to-send hand-off packs (see handoff.py).
HANDOFF_DIR = Path(os.environ.get("CREATELEE_HANDOFF_DIR", str(BASE_DIR / "handoff")))
# The 6 REAL signoff files the user supplied (XLSX saved as .csv, decoded to UTF-8).
# Used by the system-library builder to ingest real records. Overridable via env.
UPLOADS_DIR = Path(os.environ.get("CREATELEE_UPLOADS_DIR", str(BASE_DIR / "uploads")))
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

for _p in (OUTPUT_DIR, SESSION_DIR, EVIDENCE_DIR, LIBRARY_DIR, HANDOFF_DIR, UPLOADS_DIR, SAMPLES_DIR):
    _p.mkdir(parents=True, exist_ok=True)

SCHEMA_VERSION = "1.0"
PLATFORM_NAME = "Createlee"
AGENT_NAME = "Engeznee"

# --- Local Ollama -----------------------------------------------------------
def _normalise_host(value: str, default: str = "http://127.0.0.1:11434") -> str:
    """Ollama's own CLI exports OLLAMA_HOST as 'host:port' with NO scheme.

    requests/urllib need a scheme, so '127.0.0.1:11434' would fail with
    InvalidSchema on every call. Normalise it once, here.
    """
    v = (value or "").strip()
    if not v:
        return default
    if "://" not in v:
        v = "http://" + v
    return v.rstrip("/")


OLLAMA_HOST = _normalise_host(os.environ.get("OLLAMA_HOST", ""))
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "").strip()  # empty = auto-detect first
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "180"))

# --- Optional OpenAI-compatible cloud endpoint -----------------------------
CLOUD_LLM_URL = os.environ.get("CREATELEE_CLOUD_LLM_URL", "").strip()
CLOUD_LLM_KEY = os.environ.get("CREATELEE_CLOUD_LLM_KEY", "").strip()
CLOUD_LLM_MODEL = os.environ.get("CREATELEE_CLOUD_LLM_MODEL", "").strip()

# --- Web enrichment (free, no API key) -------------------------------------
# OFF by default: the evidence path must not touch the network unless the
# operator explicitly asks for live references. Opt in with
# CREATELEE_WEB_ENRICH=1 (or the `web` keyword on a generate command).
WEB_ENRICH = os.environ.get("CREATELEE_WEB_ENRICH", "0").strip() == "1"
WEB_TIMEOUT = int(os.environ.get("CREATELEE_WEB_TIMEOUT", "10"))

# --- Email (SMTP). No credentials -> .eml draft is produced instead. -------
SMTP_HOST = os.environ.get("CREATELEE_SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("CREATELEE_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("CREATELEE_SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("CREATELEE_SMTP_PASSWORD", "").strip()
SMTP_FROM = os.environ.get("CREATELEE_SMTP_FROM", "").strip() or SMTP_USER
SMTP_SECURITY = os.environ.get("CREATELEE_SMTP_SECURITY", "starttls").strip().lower()
# Recipient pre-filled in the Review & Approve panel.
DEFAULT_EMAIL_TO = os.environ.get("CREATELEE_DEFAULT_EMAIL_TO", "").strip()

# --- Uploads ---------------------------------------------------------------
MAX_UPLOAD_MB = int(os.environ.get("CREATELEE_MAX_UPLOAD_MB", "25"))
ALLOWED_EXT = {".csv", ".txt", ".json", ".xlsx", ".xls", ".pdf", ".docx", ".md", ".tsv", ".log"}

# --- Session secret + network exposure -------------------------------------
# A shared, guessable default is not a secret: anyone who has read this file
# can forge a Flask session cookie. When CREATELEE_SECRET_KEY is unset (or set
# to a documented placeholder) we generate a fresh random key per process and
# mark it ephemeral. That is safe for the local single-operator tool, and
# validate_runtime() refuses to expose such a process beyond loopback.
INSECURE_SECRET_KEYS = {
    "",
    "createlee-local-dev-key-change-me",
    "change-this-to-a-random-string",
    "changeme",
    "secret",
}
MIN_SECRET_KEY_LENGTH = 32


def _load_secret_key() -> tuple[str, bool]:
    """Return (secret, is_ephemeral). Never returns a shared default."""
    raw = os.environ.get("CREATELEE_SECRET_KEY", "").strip()
    if raw and raw.lower() not in INSECURE_SECRET_KEYS:
        return raw, False
    if raw:
        warnings.warn(
            "CREATELEE_SECRET_KEY is a documented placeholder; generating a "
            "random per-process key instead. Set a real random value for a "
            "stable deployment.",
            RuntimeWarning,
            stacklevel=2,
        )
    return secrets.token_urlsafe(48), True


SECRET_KEY, SECRET_KEY_IS_EPHEMERAL = _load_secret_key()

# Bind loopback by default. Network exposure is an explicit opt-in
# (CREATELEE_BIND_HOST=0.0.0.0) and requires a stable secret plus a bearer
# token, enforced by validate_runtime().
DEFAULT_BIND_HOST = "127.0.0.1"
BIND_HOST = os.environ.get("CREATELEE_BIND_HOST", "").strip() or DEFAULT_BIND_HOST
AUTH_TOKEN = os.environ.get("CREATELEE_AUTH_TOKEN", "").strip()
MIN_AUTH_TOKEN_LENGTH = 24
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "localhost.localdomain"}


def is_loopback(host: str) -> bool:
    """True when `host` only accepts connections from this machine."""
    value = (host or "").strip().lower()
    if value in LOOPBACK_HOSTS:
        return True
    return value.startswith("127.")


def validate_runtime(host: str) -> None:
    """Fail closed before binding to anything reachable off this machine.

    Raises RuntimeError with every unmet requirement, so the operator fixes
    them in one pass instead of one restart at a time.
    """
    if is_loopback(host):
        return
    problems = []
    if SECRET_KEY_IS_EPHEMERAL:
        problems.append(
            "CREATELEE_SECRET_KEY must be set to a stable random value "
            f"(>= {MIN_SECRET_KEY_LENGTH} characters)"
        )
    elif len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
        problems.append(
            f"CREATELEE_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters"
        )
    if len(AUTH_TOKEN) < MIN_AUTH_TOKEN_LENGTH:
        problems.append(
            "CREATELEE_AUTH_TOKEN must be set "
            f"(>= {MIN_AUTH_TOKEN_LENGTH} characters) so every route requires "
            "a bearer token"
        )
    if problems:
        raise RuntimeError(
            f"Refusing to bind to {host!r} without authentication:\n  - "
            + "\n  - ".join(problems)
        )

