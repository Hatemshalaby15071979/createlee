"""Createlee configuration. All optional integrations degrade gracefully."""
from __future__ import annotations

import os
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
WEB_ENRICH = os.environ.get("CREATELEE_WEB_ENRICH", "1") == "1"
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

SECRET_KEY = os.environ.get("CREATELEE_SECRET_KEY", "createlee-local-dev-key-change-me")
