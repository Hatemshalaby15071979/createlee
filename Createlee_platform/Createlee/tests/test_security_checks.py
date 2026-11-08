"""Regression tests for blocking committed dotenv files."""
from __future__ import annotations

import security_checks
import subprocess


def test_exact_dotenv_is_rejected():
    assert security_checks.forbidden_tracked_env_paths(
        ["Createlee_platform/Createlee/.env"]
    ) == ["Createlee_platform/Createlee/.env"]


def test_environment_specific_dotenv_is_rejected():
    assert security_checks.forbidden_tracked_env_paths(
        ["Createlee_platform/Createlee/.env.production"]
    ) == ["Createlee_platform/Createlee/.env.production"]


def test_example_dotenv_is_allowed():
    assert security_checks.forbidden_tracked_env_paths(
        ["Createlee_platform/Createlee/.env.example"]
    ) == []


def test_unrelated_files_are_allowed():
    assert security_checks.forbidden_tracked_env_paths(
        [".gitignore", "environment.yml", "config.py"]
    ) == []


def test_tracked_file_added_before_ignore_rule_is_rejected(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Security test"], check=True)
    ignored_file = tmp_path / "runtime" / "session.jsonl"
    ignored_file.parent.mkdir()
    ignored_file.write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "runtime/session.jsonl"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "add runtime fixture"], check=True)
    (tmp_path / ".gitignore").write_text("runtime/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore"], check=True)

    assert security_checks.tracked_ignored_paths(tmp_path) == ["runtime/session.jsonl"]
