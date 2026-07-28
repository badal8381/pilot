from __future__ import annotations

import subprocess

import pytest

from pilot.core.site.config import is_setup_complete

_DB_CONFIG = {"db_name": "site_db", "db_password": "secret"}


def _fake_run(stdout: str, returncode: int = 0):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")

    return run


def test_is_setup_complete_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/mariadb")
    monkeypatch.setattr(subprocess, "run", _fake_run("1\n"))

    assert is_setup_complete(_DB_CONFIG) is True


def test_is_setup_complete_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/mariadb")
    monkeypatch.setattr(subprocess, "run", _fake_run("0\n"))

    assert is_setup_complete(_DB_CONFIG) is False


def test_is_setup_complete_none_without_db_credentials() -> None:
    assert is_setup_complete({}) is None
