from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pilot.exceptions import BenchError, BenchNotRunningError
from pilot.managers.processes import local as process_module
from pilot.managers.processes.local import ProcessManager
from tests.pilot.managers.test_managers_extra import make_bench


def _manager(tmp_path: Path) -> ProcessManager:
    bench = make_bench(tmp_path)
    bench.pids_path.mkdir(parents=True, exist_ok=True)
    return ProcessManager(bench)


def _spawn_reaped_sleep(
    *, start_new_session: bool = False, bench_root: Path | None = None
) -> subprocess.Popen:
    """A sleeping child whose zombie gets reaped, so its process stamp vanishes on exit.

    Spawns python, not /bin/sleep: macOS hides the environment of Apple platform
    binaries from `ps -E`, which would defeat the ownership check."""
    env = None
    if bench_root is not None:
        env = {**process_module.os.environ, process_module.BENCH_ROOT_ENV: str(bench_root)}
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=start_new_session,
        env=env,
    )
    threading.Thread(target=proc.wait, daemon=True).start()
    return proc


def _record_supervisor(manager: ProcessManager, proc: subprocess.Popen) -> None:
    manager.pid_file.write_text(str(proc.pid))
    manager.supervisor_identity_file.write_text(process_module.get_process_stamp(proc.pid))


@pytest.mark.parametrize(
    ("macos", "stdout", "expected_argv", "expected_pids"),
    [
        (True, "123\n456\n", ["lsof", "-ti", "tcp:7001", "-sTCP:LISTEN"], {123, 456}),
        (
            False,
            'users:(("python",pid=123,fd=4))\nusers:(("redis",pid=456,fd=5))\n',
            ["ss", "-H", "-ltnp", "sport = :7001"],
            {123, 456},
        ),
    ],
)
def test_pids_listening_uses_platform_tool(
    monkeypatch, macos: bool, stdout: str, expected_argv: list[str], expected_pids: set[int]
) -> None:
    run = MagicMock(return_value=subprocess.CompletedProcess(expected_argv, 0, stdout=stdout))
    monkeypatch.setattr("pilot.managers.platform.is_macos", lambda: macos)
    monkeypatch.setattr(process_module.subprocess, "run", run)

    assert process_module._pids_listening(7001) == expected_pids
    assert run.call_args.args[0] == expected_argv


def test_stop_terminates_supervisor_and_waits_for_exit(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    proc = _spawn_reaped_sleep()
    _record_supervisor(manager, proc)
    monkeypatch.setattr(manager, "_port_holders", lambda: {})

    manager.stop()

    assert proc.poll() is not None
    assert not manager.pid_file.exists()
    assert not manager.supervisor_identity_file.exists()


def test_stop_preserves_pid_file_replaced_during_shutdown(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    manager.pid_file.write_text("123")
    manager.supervisor_identity_file.write_text("original")

    def replace_pid(_pid: int, _stamp: str, timeout: float | None = None) -> None:
        manager.pid_file.write_text("456")
        manager.supervisor_identity_file.write_text("replacement")

    monkeypatch.setattr("pilot.managers.processes.local.os.kill", MagicMock())
    monkeypatch.setattr(process_module, "get_process_stamp", lambda _pid: "original")
    monkeypatch.setattr(manager, "_wait_for_exit", replace_pid)
    monkeypatch.setattr(manager, "_wait_for_ports", lambda: None)

    manager.stop()

    assert manager.pid_file.read_text() == "456"
    assert manager.supervisor_identity_file.read_text() == "replacement"


def test_supervisor_cleanup_preserves_replacement_pid_file(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "is_configured", lambda: True)
    monkeypatch.setattr(manager, "write_config", lambda: None)
    monkeypatch.setattr(manager, "_process_definitions", lambda: [])

    def replace_supervisor(_definitions) -> None:
        manager.pid_file.write_text("456")
        manager.supervisor_identity_file.write_text("replacement")

    monkeypatch.setattr(manager, "_run_processes", replace_supervisor)

    manager.start()

    assert manager.pid_file.read_text() == "456"
    assert manager.supervisor_identity_file.read_text() == "replacement"


def test_stop_with_stale_pid_file_kills_port_holders(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    manager.pid_file.write_text("999999")
    orphan = _spawn_reaped_sleep(start_new_session=True, bench_root=manager.bench.path)
    (manager.bench.pids_path / "redis_queue.pid").write_text(str(orphan.pid))
    monkeypatch.setattr(
        "pilot.managers.processes.local._pids_listening",
        lambda port: (
            {orphan.pid} if port == manager.bench.config.redis.queue_port and orphan.poll() is None else set()
        ),
    )

    manager.stop()

    assert orphan.poll() is not None
    assert not manager.pid_file.exists()


def test_stop_legacy_pid_file_signals_pilot_supervisor(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    proc = _spawn_reaped_sleep()
    manager.pid_file.write_text(str(proc.pid))
    monkeypatch.setattr(process_module, "_process_command", lambda _pid: "/usr/local/bin/pilot start")
    monkeypatch.setattr(manager, "_port_holders", lambda: {})

    manager.stop()

    assert proc.poll() is not None
    assert not manager.pid_file.exists()


def test_stop_legacy_pid_file_rejects_unrelated_process(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    proc = _spawn_reaped_sleep()
    manager.pid_file.write_text(str(proc.pid))
    monkeypatch.setattr(process_module, "_process_command", lambda _pid: "nginx: master process")
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    try:
        with pytest.raises(BenchError, match="does not look like a pilot supervisor"):
            manager.stop()
        kill.assert_not_called()
        assert manager.pid_file.exists()
    finally:
        monkeypatch.undo()
        proc.terminate()


def test_stop_ignores_unowned_port_holder(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "_port_holders", lambda: {7000: {123}})
    monkeypatch.setattr(process_module, "_process_has_bench_root", lambda _pid, _root: False)
    monkeypatch.setattr(process_module, "_process_command", lambda _pid: "/usr/bin/python other.py")
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    with pytest.raises(BenchNotRunningError, match="not running"):
        manager.stop()

    kill.assert_not_called()


def test_stop_signals_owned_and_skips_foreign_holder(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "_port_holders", lambda: {7000: {123}, 8000: {456}})
    monkeypatch.setattr(manager, "_wait_for_ports", lambda: None)
    monkeypatch.setattr(process_module, "_process_has_bench_root", lambda pid, _root: pid == 456)
    monkeypatch.setattr(process_module, "_process_command", lambda _pid: "/usr/bin/python other.py")
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    manager.stop()

    kill.assert_called_once_with(456, process_module.signal.SIGTERM)


def test_stop_accepts_matching_bench_environment(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "_port_holders", lambda: {8000: {456}})
    monkeypatch.setattr(manager, "_wait_for_ports", lambda: None)
    monkeypatch.setattr(process_module, "_process_has_bench_root", lambda _pid, _root: True)
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    manager.stop()

    kill.assert_called_once_with(456, process_module.signal.SIGTERM)


def test_stop_rejects_reused_recorded_process_group(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    (manager.bench.pids_path / "web.pid").write_text("123")
    monkeypatch.setattr(manager, "_port_holders", lambda: {8000: {456}})
    monkeypatch.setattr(process_module, "_process_has_bench_root", lambda _pid, _root: False)
    monkeypatch.setattr(process_module, "_process_command", lambda _pid: "/usr/bin/python other.py")
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    with pytest.raises(BenchNotRunningError, match="not running"):
        manager.stop()

    kill.assert_not_called()


def test_stop_accepts_matching_setup_wizard(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "_port_holders", lambda: {7000: {123}})
    monkeypatch.setattr(manager, "_wait_for_ports", lambda: None)
    monkeypatch.setattr(
        process_module,
        "_process_command",
        lambda _pid: (
            f"python -m admin.backend.run_server --bench-root {manager.bench.path} --port 7000 --wizard"
        ),
    )
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    manager.stop()

    kill.assert_called_once_with(123, process_module.signal.SIGTERM)


def test_stop_rejects_sibling_bench_wizard(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "_port_holders", lambda: {7000: {123}})
    monkeypatch.setattr(process_module, "_process_has_bench_root", lambda _pid, _root: False)
    monkeypatch.setattr(
        process_module,
        "_process_command",
        lambda _pid: (
            f"python -m admin.backend.run_server --bench-root {manager.bench.path}2 --port 7000 --wizard"
        ),
    )
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    with pytest.raises(BenchNotRunningError, match="not running"):
        manager.stop()

    kill.assert_not_called()


def test_stop_verifies_ports_after_supervisor_exits(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    supervisor = _spawn_reaped_sleep()
    _record_supervisor(manager, supervisor)
    wait_for_ports = MagicMock()
    monkeypatch.setattr(manager, "_wait_for_ports", wait_for_ports)

    manager.stop()

    assert supervisor.poll() is not None
    wait_for_ports.assert_called_once_with()


def test_stop_does_not_signal_reused_supervisor_pid(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    manager.pid_file.write_text("123")
    manager.supervisor_identity_file.write_text("original")
    monkeypatch.setattr(process_module, "get_process_stamp", lambda _pid: "replacement")
    monkeypatch.setattr(manager, "_port_holders", lambda: {})
    kill = MagicMock()
    monkeypatch.setattr(process_module.os, "kill", kill)

    with pytest.raises(BenchNotRunningError, match="not running"):
        manager.stop()

    kill.assert_not_called()
    assert not manager.pid_file.exists()
    assert not manager.supervisor_identity_file.exists()


def test_macos_bench_root_match_requires_environment_boundary(tmp_path: Path, monkeypatch) -> None:
    bench_root = tmp_path / "bench"
    output = f"python worker.py {process_module.BENCH_ROOT_ENV}={bench_root}2 OTHER=value"
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, stdout=output))
    monkeypatch.setattr("pilot.managers.platform.is_macos", lambda: True)
    monkeypatch.setattr(process_module.subprocess, "run", run)

    assert process_module._process_has_bench_root(123, bench_root) is False

    run.return_value = subprocess.CompletedProcess(
        [], 0, stdout=f"python worker.py {process_module.BENCH_ROOT_ENV}={bench_root} OTHER=value"
    )
    assert process_module._process_has_bench_root(123, bench_root) is True


def test_stop_raises_when_nothing_is_running(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr("pilot.managers.processes.local._pids_listening", lambda port: set())

    with pytest.raises(BenchNotRunningError, match="not running"):
        manager.stop()


def test_configured_ports_skips_socketio_in_lite_mode(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(type(manager.bench), "is_lite_mode", property(lambda _self: True))

    assert manager.bench.config.socketio_port not in manager._configured_ports


def test_wait_for_exit_raises_instead_of_silently_timing_out(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    proc = _spawn_reaped_sleep()
    stamp = process_module.get_process_stamp(proc.pid)
    try:
        with pytest.raises(BenchError, match="Timed out waiting for bench supervisor"):
            manager._wait_for_exit(proc.pid, stamp, timeout=0)
    finally:
        proc.terminate()
        proc.wait()


def test_wait_for_exit_treats_unreaped_zombie_as_exited(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    proc = subprocess.Popen(["sleep", "30"])
    stamp = process_module.get_process_stamp(proc.pid)
    proc.terminate()
    try:
        manager._wait_for_exit(proc.pid, stamp, timeout=5)
    finally:
        proc.wait()


def test_wait_for_ports_reports_the_ports_still_in_use(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "_port_holders", lambda: {11000: {123}, 13000: {456}})
    monkeypatch.setattr(manager, "_owns_process", lambda _pid: True)

    with pytest.raises(BenchError, match="11000, 13000"):
        manager._wait_for_ports(timeout=0)


def test_wait_for_ports_ignores_foreign_holders(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    monkeypatch.setattr(manager, "_port_holders", lambda: {11000: {123}})
    monkeypatch.setattr(manager, "_owns_process", lambda _pid: False)

    manager._wait_for_ports(timeout=0)


def test_stop_all_escalates_to_sigkill_after_deadline(tmp_path: Path, monkeypatch) -> None:
    manager = _manager(tmp_path)
    proc = MagicMock()
    proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="web", timeout=1), None]
    manager._procs = {"web": proc}
    manager._stop_timeouts = {"web": 1}
    signals = []
    monkeypatch.setattr(manager, "_signal_group", lambda _proc, signum: signals.append(signum))

    manager._stop_all()

    assert signals == [process_module.signal.SIGTERM, process_module.signal.SIGKILL]
