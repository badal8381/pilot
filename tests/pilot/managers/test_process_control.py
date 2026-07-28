"""Per-process control on the systemd manager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pilot.managers.processes.systemd import SystemdProcessManager
from tests.pilot.commands.test_commands import make_bench


def test_control_process_targets_bench_unit(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    manager = SystemdProcessManager(bench)
    with patch("pilot.managers.processes.systemd.run_command") as run:
        manager.control_process("mail-stalwart", "restart")
    argv = run.call_args[0][0]
    assert argv[:2] == ["systemctl", "--user"]
    assert "restart" in argv
    assert f"{bench.config.name}-mail-stalwart.service" in argv


def test_control_process_rejects_bad_action(tmp_path: Path) -> None:
    manager = SystemdProcessManager(make_bench(tmp_path))
    with pytest.raises(ValueError):
        manager.control_process("mail-stalwart", "delete")


def test_supervisor_control_process_targets_group_program(tmp_path: Path) -> None:
    from pilot.managers.processes.supervisor import SupervisorProcessManager

    bench = make_bench(tmp_path)
    manager = SupervisorProcessManager(bench)
    with patch("pilot.managers.processes.supervisor.run_command") as run:
        manager.control_process("mail-stalwart", "stop")
    argv = run.call_args[0][0]
    assert "stop" in argv
    assert f"{bench.config.name}:{bench.config.name}-mail-stalwart" in argv


def test_supervisor_control_process_rejects_bad_action(tmp_path: Path) -> None:
    from pilot.managers.processes.supervisor import SupervisorProcessManager

    manager = SupervisorProcessManager(make_bench(tmp_path))
    with pytest.raises(ValueError):
        manager.control_process("mail-stalwart", "delete")
