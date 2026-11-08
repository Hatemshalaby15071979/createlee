#!/usr/bin/env bash
# Createlee / Engeznee — local launcher
set -e
cd "$(dirname "$0")"

# Pick the local interpreter: prefer the project venv, then python3.11, then python3.
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PY="python3.11"
else
  PY="python3"
fi

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

PORT="${CREATELEE_PORT:-7860}"
echo "Starting Createlee / Engeznee on http://127.0.0.1:${PORT}  (using $PY)"
exec "$PY" app.py
