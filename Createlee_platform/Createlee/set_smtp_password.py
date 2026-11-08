#!/usr/bin/env python3
"""Set CREATELEE_SMTP_PASSWORD in .env — hidden input, no shell history.

Why this exists: `python3 - <<'EOF' ... input() ... EOF` cannot work, because the
heredoc becomes stdin and input() immediately hits EOF. This reads from the
terminal via getpass(), so the password is never echoed and never lands in your
shell history, and the file edit is atomic.

Usage:
    ./.venv/bin/python set_smtp_password.py            # set the password
    ./.venv/bin/python set_smtp_password.py --test     # set it, then verify with Gmail
    ./.venv/bin/python set_smtp_password.py --show     # show config status (no secret)
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import re
import smtplib
import ssl
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parent / ".env"
KEYS = ("CREATELEE_SMTP_HOST", "CREATELEE_SMTP_PORT", "CREATELEE_SMTP_SECURITY",
        "CREATELEE_SMTP_USER", "CREATELEE_SMTP_PASSWORD", "CREATELEE_SMTP_FROM",
        "CREATELEE_DEFAULT_EMAIL_TO")


def _read() -> str:
    if not ENV.is_file():
        sys.exit(f"No .env at {ENV}")
    return ENV.read_text(encoding="utf-8")


def _get(text: str, key: str) -> str:
    m = re.search(rf"^{key}=(.*)$", text, re.M)
    return (m.group(1) if m else "").strip().strip('"').strip("'")


def _set(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    if re.search(rf"^{key}=.*$", text, re.M):
        return re.sub(rf"^{key}=.*$", line, text, flags=re.M)
    return text.rstrip("\n") + "\n" + line + "\n"


def show() -> None:
    t = _read()
    for k in KEYS:
        v = _get(t, k)
        if k == "CREATELEE_SMTP_PASSWORD":
            print(f"  {k:<29} {'(set, ' + str(len(v)) + ' chars)' if v else '(blank)'}")
        else:
            print(f"  {k:<29} {v or '(blank)'}")
    pw = _get(t, "CREATELEE_SMTP_PASSWORD")
    if pw:
        print(f"  {'password fingerprint':<29} sha256[:8]={hashlib.sha256(pw.encode()).hexdigest()[:8]}")


def verify() -> int:
    """AUTH against Gmail without sending anything. Returns 0 on success."""
    t = _read()
    host, port = _get(t, "CREATELEE_SMTP_HOST") or "smtp.gmail.com", int(_get(t, "CREATELEE_SMTP_PORT") or 587)
    user, pw = _get(t, "CREATELEE_SMTP_USER"), _get(t, "CREATELEE_SMTP_PASSWORD")
    if not (user and pw):
        print("Cannot verify: user or password is blank.")
        return 2
    try:
        s = smtplib.SMTP(host, port, timeout=20)
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
        code, resp = s.docmd("AUTH", "LOGIN")
        if code != 334:
            raise smtplib.SMTPAuthenticationError(code, resp)
        code, resp = s.docmd(base64.b64encode(user.encode()).decode())
        if code != 334:
            raise smtplib.SMTPAuthenticationError(code, resp)
        code, resp = s.docmd(base64.b64encode(pw.encode()).decode())
        s.close()
        if code == 235:
            print(f"SUCCESS — Gmail accepted the app password for {user}.")
            return 0
        print(f"REJECTED — {code} {resp.decode(errors='replace')[:180]}")
        print("The credential is not valid for this account. Regenerate the App Password")
        print("at https://myaccount.google.com/apppasswords while signed in as the address above.")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED — {type(exc).__name__}: {exc}")
        return 1


def main() -> int:
    if "--show" in sys.argv:
        show()
        return 0

    t = _read()
    print(f"Account : {_get(t, 'CREATELEE_SMTP_USER') or '(blank)'}")
    print("Create it at https://myaccount.google.com/apppasswords with 2-Step Verification ON,")
    print("then copy the 16-character value.\n")
    try:
        pw = getpass.getpass("Paste the 16-char app password (input hidden): ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled — nothing written.")
        return 2
    pw = pw.strip().replace(" ", "")
    if len(pw) != 16:
        print(f"Expected 16 characters after removing spaces, got {len(pw)}. Nothing written.")
        return 2

    ENV.write_text(_set(t, "CREATELEE_SMTP_PASSWORD", pw), encoding="utf-8")
    print(f"Saved to {ENV}")
    print(f"Fingerprint sha256[:8]={hashlib.sha256(pw.encode()).hexdigest()[:8]}")
    print("Restart the app so it reloads .env (bash run.sh).")

    if "--test" in sys.argv:
        print("\nVerifying with Gmail (no email is sent)…")
        return verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
