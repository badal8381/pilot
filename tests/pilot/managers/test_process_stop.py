"""Tests for stopping the dev bench supervisor and its leftovers."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from pilot.exceptions import BenchError
from pilot.managers.processes.local import ProcessManager
from tests.pilot.managers.test_managers_extra import make_bench


def _manager(tmp_path: Path) -> ProcessManager:
    bench = make_bench(tmp_path)
    bench.pids_path.mkdir(parents=True, exist_ok=True)
    return ProcessManager(bench)


def _spawn_reaped_sleep() -> subprocess.Popen:
    """A sleeping child whose zombie gets reaped, so os.kill(pid, 0) sees it die."""
    proc = subprocess.Popen(["sleep", "30"])
    threading.Thread(target=proc.wait, daemon=True).start()
    return proc


def test_stop_terminates_supervisor_and_waits_for_exit(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    proc = _spawn_reaped_sleep()
    manager.pid_file.write_text(str(proc.pid))

    manager.stop()

    assert proc.poll() is not None
    assert not manager.pid_file.exists()


def test_stop_with_stale_pid_file_kills_port_holders(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    manager.pid_file.write_text("999999")
    orphan = _spawn_reaped_sleep()
    monkeypatch.setattr(
        "pilot.managers.processes.local._pids_listening",
        lambda port: {orphan.pid} if port == manager.bench.config.redis.queue_port else set(),
    )

    manager.stop()

    assert orphan.poll() is not None
    assert not manager.pid_file.exists()


def test_stop_raises_when_nothing_is_running(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr("pilot.managers.processes.local._pids_listening", lambda port: set())

    with pytest.raises(BenchError, match="not running"):
        manager.stop()
