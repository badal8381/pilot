from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from pilot.managers.processes.supervisor import SupervisorProcessManager
    from pilot.managers.processes.systemd import SystemdProcessManager


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


@dataclass
class ProcessInfo:
    name: str
    status: str  # 'running' | 'stopped' | 'unknown'
    pid: int | None
    uptime: str | None
    log_file: Path
    cpu_percent: float | None = None
    rss_mb: float | None = None
    pss_mb: float | None = None


class ProcessProvider:
    def __init__(self, bench_root: Path) -> None:
        self._bench_root = bench_root

    def get_all(self) -> list[ProcessInfo]:
        from pilot.core.bench import Bench

        bench = Bench(self._bench_root)

        from pilot.managers.processes.supervisor import SupervisorProcessManager
        from pilot.managers.processes.systemd import SystemdProcessManager

        systemd = SystemdProcessManager(bench)
        supervisor = SupervisorProcessManager(bench)
        if systemd.is_running():
            return self.get_from_systemd(systemd)
        if supervisor.is_running():
            return self.get_from_supervisor(supervisor)

        return self.get_from_pids()

    def get_from_systemd(self, systemd: "SystemdProcessManager") -> list[ProcessInfo]:
        bench_name = systemd.bench.config.name
        units = [f.name for f in sorted(systemd.user_unit_dir.glob(f"{bench_name}-*.service"))]
        if not units:
            return []

        result = subprocess.run(
            [*systemd._systemctl("show", *units), "--property=Id,ActiveState,MainPID"],
            capture_output=True,
            text=True,
            env=systemd._systemctl_env(),
        )
        return [
            info
            for block in result.stdout.strip().split("\n\n")
            if (info := self._get_systemd_process(block.strip(), bench_name))
        ]

    def _get_systemd_process(self, block: str, bench_name: str) -> ProcessInfo | None:
        """Parses one blank-line-separated `systemctl show` property block."""
        props = dict(line.partition("=")[::2] for line in block.splitlines() if "=" in line)
        unit_id = props.get("Id", "")
        if not unit_id.endswith(".service"):
            return None

        name = unit_id.removesuffix(".service").removeprefix(f"{bench_name}-")
        state = props.get("ActiveState", "")
        status = (
            "running"
            if state == "active"
            else ("stopped" if state in ("inactive", "failed", "deactivating") else "unknown")
        )
        pid_str = props.get("MainPID", "0")
        pid = int(pid_str) if pid_str.isdigit() and pid_str != "0" else None
        return self._build_info(name, status, pid)

    def get_from_supervisor(self, supervisor: SupervisorProcessManager) -> list[ProcessInfo]:
        bench_name = supervisor.bench.config.name
        result = subprocess.run(
            [*supervisor._supervisorctl(), "status"],
            capture_output=True,
            text=True,
        )
        return [
            info
            for line in result.stdout.splitlines()
            if line.strip() and (info := self._get_supervisor_process(line.strip(), bench_name))
        ]

    def _get_supervisor_process(self, line: str, bench_name: str) -> ProcessInfo | None:
        """Parses one fixed-column `supervisorctl status` line."""
        m = re.match(r"(\S+:\S+)\s+(\S+)\s*(.*)", line)
        if not m:
            return None

        full_name, state, rest = m.group(1), m.group(2).lower(), m.group(3)
        status = (
            "running"
            if state == "running"
            else ("stopped" if state in ("stopped", "exited", "fatal", "backoff") else "unknown")
        )

        pid: int | None = None
        if pid_m := re.search(r"pid (\d+)", rest):
            pid = int(pid_m.group(1))

        program = full_name.split(":", 1)[-1].removeprefix(f"{bench_name}-")
        # supervisor names units with dashes but writes logs with underscores.
        log_name = program.replace("-", "_")
        return self._build_info(program, status, pid, log_name)

    def get_from_pids(self) -> list[ProcessInfo]:
        pids_dir = self._bench_root / "pids"
        if not pids_dir.exists():
            return []

        return [self.get_process(f.stem, f) for f in sorted(pids_dir.glob("*.pid"))]

    def get_process(self, name: str, pid_file: Path) -> ProcessInfo:
        try:
            pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return self._build_info(name, "unknown", None)

        try:
            os.kill(pid, 0)
            status = "running"
        except OSError:
            status = "stopped"
        return self._build_info(name, status, pid)

    def _build_info(
        self, name: str, status: str, pid: int | None, log_name: str | None = None
    ) -> ProcessInfo:
        log_file = self._bench_root / "logs" / f"{log_name or name}.log"
        if pid and status == "running":
            cpu, rss, pss = self._get_process_stats(pid)
            uptime = self._get_proc_uptime(pid)
        else:
            cpu = rss = pss = uptime = None
        return ProcessInfo(
            name=name,
            status=status,
            pid=pid,
            uptime=uptime,
            log_file=log_file,
            cpu_percent=cpu,
            rss_mb=rss,
            pss_mb=pss,
        )

    @classmethod
    def _get_process_stats(cls, pid: int) -> tuple[float | None, float | None, float | None]:
        """CPU%, RSS and PSS (MB) summed across the process subtree."""
        try:
            root = psutil.Process(pid)
            subtree = [root, *root.children(recursive=True)]
        except psutil.Error:
            return None, None, None

        cpu_total, rss_kb, pss_kb = 0.0, 0, []
        for process in subtree:
            try:
                cpu_total += cls._lifetime_cpu_percent(process)
                rss_kb += process.memory_info().rss // 1024
                if (pss := getattr(process.memory_full_info(), "pss", None)) is not None:
                    pss_kb.append(pss // 1024)
            except psutil.Error:
                continue

        pss_mb = round(sum(pss_kb) / 1024.0, 1) if pss_kb else None
        return round(cpu_total, 1), round(rss_kb / 1024.0, 1), pss_mb

    @staticmethod
    def _lifetime_cpu_percent(process: psutil.Process) -> float:
        """CPU averaged over the process's whole life, matching what `ps %cpu`
        reports. psutil's own cpu_percent() needs two samples and would read 0
        on a one-shot request."""
        cpu_times = process.cpu_times()
        elapsed = time.time() - process.create_time()
        if elapsed <= 0:
            return 0.0
        return (cpu_times.user + cpu_times.system) / elapsed * 100

    @staticmethod
    def _get_proc_uptime(pid: int) -> str | None:
        try:
            elapsed = time.time() - psutil.Process(pid).create_time()
        except psutil.Error:
            return None
        return _format_duration(elapsed) if elapsed >= 0 else None
