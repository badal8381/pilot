from __future__ import annotations

import contextlib
import fcntl
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from pilot.exceptions import BenchError, BenchNotRunningError, CommandError
from pilot.internal.tasks.process_identity import get_process_stamp
from pilot.managers.environment import AdminEnvManager
from pilot.managers.gunicorn import GunicornManager
from pilot.managers.processes.definitions import ProcessDefinition, ProcessDefinitionBuilder
from pilot.utils import cli_root, run_command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


def _tcp_port_open(port: int, host: str = "127.0.0.1") -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _pids_listening(port: int) -> set[int]:
    """PIDs listening on port (this user)."""
    from pilot.managers.platform import is_macos

    if is_macos():
        argv = ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"]
        pid_pattern = r"(\d+)"
    else:
        argv = ["ss", "-H", "-ltnp", f"sport = :{port}"]
        pid_pattern = r"pid=(\d+)"
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return set()
    return {int(m) for m in re.findall(pid_pattern, result.stdout)}


def _process_command(pid: int) -> str:
    try:
        result = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _process_cwd(pid: int) -> Path | None:
    from pilot.managers.platform import is_macos

    if not is_macos():
        try:
            return (Path("/proc") / str(pid) / "cwd").resolve(strict=True)
        except OSError:
            return None
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    path = next((line[1:] for line in result.stdout.splitlines() if line.startswith("n")), "")
    try:
        return Path(path).resolve(strict=True) if path else None
    except OSError:
        return None


def _process_has_bench_root(pid: int, bench_root: Path) -> bool:
    from pilot.managers.platform import is_macos

    expected = f"{BENCH_ROOT_ENV}={bench_root}"
    if not is_macos():
        try:
            environment = (Path("/proc") / str(pid) / "environ").read_bytes().split(b"\0")
        except OSError:
            return False
        return expected.encode() in environment
    try:
        result = subprocess.run(
            ["ps", "-E", "-ww", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    return (
        result.returncode == 0
        and re.search(rf"(?:^|\s){re.escape(expected)}(?:\s|$)", result.stdout) is not None
    )


def _is_setup_wizard_for_bench(command: str, bench_root: Path) -> bool:
    try:
        argv = shlex.split(command)
        module_index = argv.index("-m")
    except ValueError:
        return False
    module_args = argv[module_index + 1 :]
    if not module_args or module_args[0] != "admin.backend.run_server":
        return False
    try:
        bench_root_index = module_args.index("--bench-root")
    except ValueError:
        return False
    return (
        "--wizard" in module_args
        and bench_root_index + 1 < len(module_args)
        and module_args[bench_root_index + 1] == str(bench_root)
    )


def _is_pilot_start(command: str) -> bool:
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    args = _pilot_args(argv)
    return args is not None and _without_pilot_group_options(args) == ["start"]


def _pilot_args(argv: list[str]) -> list[str] | None:
    if not argv:
        return None
    executable = Path(argv[0]).name
    if executable == "pilot":
        return argv[1:]
    if executable.startswith("python") and len(argv) > 1 and Path(argv[1]).name == "pilot":
        return argv[2:]
    return None


def _without_pilot_group_options(args: list[str]) -> list[str]:
    index = 0
    while index < len(args):
        option = args[index]
        if option in ("--verbose", "--yes", "-y"):
            index += 1
        elif option in ("--bench", "-b"):
            index += 2
        elif option.startswith(("--bench=", "-b=")):
            index += 1
        else:
            break
    return args[index:]


def _process_runs_from_bench(pid: int, bench_root: Path) -> bool:
    cwd = _process_cwd(pid)
    return cwd is not None and cwd == bench_root.resolve()


_RELOAD_REQUEST_FILE = "reload.request"
_STOP_WAIT_SECONDS = 15.0
_STOP_POLL_SECONDS = 0.2
_CHILD_STOP_SECONDS = 5.0
BENCH_ROOT_ENV = "PILOT_BENCH_ROOT"
# Redis holds the job queue, and the admin plane is what issues the reload.
# Both must survive it, so only app-code processes are restarted.
_NON_RELOADABLE = frozenset({"admin", "admin-ui", "redis_cache", "redis_queue", "watch"})

_COLORS = [
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[35m",
    "\033[34m",
    "\033[96m",
    "\033[92m",
    "\033[93m",
]
_RESET = "\033[0m"


class ProcessManager:
    def __init__(self, bench: "Bench", watch_admin_js: bool | None = None) -> None:
        self.bench = bench
        self.watch_admin_js = bench.config.watch_admin_js if watch_admin_js is None else watch_admin_js
        self._procs: dict[str, subprocess.Popen] = {}
        self._stop_timeouts: dict[str, int | None] = {}
        self._colors: dict[str, str] = {}
        self._stopping = False

    @classmethod
    def for_bench(cls, bench: "Bench") -> "ProcessManager":
        prod = bench.config.production
        if not prod.enabled:
            return ProcessManager(bench)
        if prod.process_manager == "systemd":
            from pilot.managers.processes.systemd import SystemdProcessManager

            return SystemdProcessManager(bench)
        from pilot.managers.processes.supervisor import SupervisorProcessManager

        return SupervisorProcessManager(bench)

    @classmethod
    def detect_running(cls, bench: "Bench") -> "ProcessManager":
        # Probe runtime state, not config presence, so a lingering config from a
        # switched manager can't mislead. Falls back to for_bench when none runs.
        from pilot.managers.processes.supervisor import SupervisorProcessManager
        from pilot.managers.processes.systemd import SystemdProcessManager

        for manager in (SystemdProcessManager(bench), SupervisorProcessManager(bench)):
            if manager.is_running():
                return manager
        return cls.for_bench(bench)

    @property
    def procfile_path(self) -> Path:
        return self.bench.config_path / "Procfile"

    @property
    def pid_file(self) -> Path:
        return self.bench.pids_path / "bench.pid"

    @property
    def supervisor_identity_file(self) -> Path:
        return self.bench.pids_path / "bench.identity"

    @property
    def supervisor_lock_file(self) -> Path:
        return self.bench.pids_path / "bench.lock"

    @property
    def reload_request_file(self) -> Path:
        return self.bench.pids_path / _RELOAD_REQUEST_FILE

    @property
    def python(self) -> Path:
        return self.bench.env_path / "bin" / "python"

    @property
    def _definitions(self) -> ProcessDefinitionBuilder:
        return ProcessDefinitionBuilder(self.bench, self.python, self.watch_admin_js)

    def write_config(self) -> None:
        AdminEnvManager(cli_root()).ensure()
        self._ensure_redis_config()
        self._ensure_gunicorn_config()
        lines = [f"{pd.name}: {shlex.join(pd.argv)}\n" for pd in self._process_definitions()]
        self.procfile_path.write_text("".join(lines))

    def _ensure_gunicorn_config(self) -> None:
        GunicornManager(self.bench).generate_config()

    def _ensure_redis_config(self) -> None:
        from pilot.managers.redis import RedisManager

        RedisManager(self.bench.config.redis, self.bench).generate_configs()

    def is_configured(self) -> bool:
        return self.procfile_path.exists()

    def start(self) -> None:
        if not self.is_configured():
            raise BenchError(f"Procfile not found at {self.procfile_path}. Run 'pilot init' first.")
        self.write_config()
        pid = os.getpid()
        stamp = get_process_stamp(pid)
        if not stamp:
            raise BenchError("Could not capture the development supervisor identity.")
        self._write_supervisor_record(pid, stamp)
        try:
            self._run_processes(self._process_definitions())
        finally:
            self._unlink_supervisor_record(pid, stamp)
            self._cleanup_proc_pid_files()

    def start_workload(self) -> None:
        self.start()

    def stop(self) -> None:
        stopped = self._stop_supervisor() or self._stop_port_holders()
        if not stopped:
            raise BenchNotRunningError("Bench is not running.")
        self._wait_for_ports()

    def _stop_supervisor(self) -> bool:
        """SIGTERM the dev supervisor and wait for it to finish cleanup."""
        record = self._read_supervisor_record()
        if record is None:
            return False
        pid, recorded_stamp = record
        if not recorded_stamp:
            return self._stop_legacy_supervisor(pid)
        if get_process_stamp(pid) != recorded_stamp:
            self._unlink_supervisor_record(pid, recorded_stamp)
            return False
        return self._terminate_supervisor(pid, recorded_stamp, recorded_stamp)

    def _stop_legacy_supervisor(self, pid: int) -> bool:
        """Stop a supervisor recorded by an older pilot, before identity stamps existed."""
        stamp = get_process_stamp(pid)
        if not stamp:
            self._unlink_supervisor_record(pid, "")
            return False
        command = _process_command(pid)
        if not _is_pilot_start(command) or not _process_runs_from_bench(pid, self.bench.path):
            raise BenchError(
                f"Recorded bench process {pid} does not match this bench's Pilot supervisor. "
                f"Stop it manually and remove {self.pid_file}."
            )
        return self._terminate_supervisor(pid, stamp, "")

    def _terminate_supervisor(self, pid: int, live_stamp: str, recorded_stamp: str) -> bool:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            self._unlink_supervisor_record(pid, recorded_stamp)
            return False
        self._wait_for_exit(pid, live_stamp)
        self._unlink_supervisor_record(pid, recorded_stamp)
        return True

    def _stop_port_holders(self) -> bool:
        pids = {pid for port_pids in self._port_holders().values() for pid in port_pids}
        pids.discard(os.getpid())
        owned_pids = {pid for pid in pids if self._owns_process(pid)}
        for pid in owned_pids:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGTERM)
        return bool(owned_pids)

    def _owns_process(self, pid: int) -> bool:
        if _process_has_bench_root(pid, self.bench.path):
            return True
        return _is_setup_wizard_for_bench(_process_command(pid), self.bench.path)

    def _port_holders(self) -> dict[int, set[int]]:
        return {port: pids for port in self._configured_ports if (pids := _pids_listening(port))}

    @property
    def _configured_ports(self) -> tuple[int, ...]:
        config = self.bench.config
        ports = [config.admin.port, config.http_port, config.redis.cache_port, config.redis.queue_port]
        if not self.bench.is_lite_mode:
            ports.append(config.socketio_port)
        return tuple(ports)

    def _wait_for_exit(self, pid: int, stamp: str, timeout: float | None = None) -> None:
        """Wait until the stamped process is gone; zombies and reused pids count as exited."""
        deadline = time.monotonic() + (self._supervisor_stop_seconds if timeout is None else timeout)
        while get_process_stamp(pid) == stamp:
            if time.monotonic() >= deadline:
                raise BenchError(f"Timed out waiting for bench supervisor {pid} to stop.")
            time.sleep(_STOP_POLL_SECONDS)

    @property
    def _supervisor_stop_seconds(self) -> float:
        """The supervisor honors its slowest child's stop timeout; allow that plus slack."""
        slowest = max((pd.stop_timeout or 0 for pd in self._process_definitions()), default=0)
        return float(max(slowest, _STOP_WAIT_SECONDS)) + 10.0

    def _wait_for_ports(self, timeout: float = _STOP_WAIT_SECONDS) -> None:
        deadline = time.monotonic() + timeout
        ownership: dict[int, bool] = {}
        while owned_ports := self._owned_port_holders(ownership):
            if time.monotonic() >= deadline:
                rendered = ", ".join(str(port) for port in sorted(owned_ports))
                raise BenchError(f"Timed out waiting for bench port(s) to be released: {rendered}.")
            time.sleep(_STOP_POLL_SECONDS)

    def _owned_port_holders(self, ownership: dict[int, bool]) -> set[int]:
        """Ports still held by this bench's processes; foreign holders are ignored."""
        owned_ports = set()
        for port, pids in self._port_holders().items():
            for pid in pids:
                if pid not in ownership:
                    ownership[pid] = self._owns_process(pid)
                if ownership[pid]:
                    owned_ports.add(port)
        return owned_ports

    def _write_supervisor_record(self, pid: int, stamp: str) -> None:
        with self._supervisor_record_lock():
            self.pid_file.write_text(str(pid))
            self.supervisor_identity_file.write_text(stamp)

    def _read_supervisor_record(self) -> tuple[int, str] | None:
        with self._supervisor_record_lock():
            return self._read_supervisor_record_unlocked()

    def _unlink_supervisor_record(self, pid: int, recorded_stamp: str) -> None:
        """Remove the record only while it still holds the values this stop used."""
        with self._supervisor_record_lock():
            if self._read_supervisor_record_unlocked() != (pid, recorded_stamp):
                return
            self.pid_file.unlink(missing_ok=True)
            self.supervisor_identity_file.unlink(missing_ok=True)

    def _read_supervisor_record_unlocked(self) -> tuple[int, str] | None:
        try:
            pid = int(self.pid_file.read_text().strip())
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            self.pid_file.unlink(missing_ok=True)
            self.supervisor_identity_file.unlink(missing_ok=True)
            return None
        try:
            stamp = self.supervisor_identity_file.read_text().strip()
        except OSError:
            stamp = ""
        return pid, stamp

    @contextlib.contextmanager
    def _supervisor_record_lock(self) -> Iterator[None]:
        self.bench.pids_path.mkdir(parents=True, exist_ok=True)
        with self.supervisor_lock_file.open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def is_running(self) -> bool:
        record = self._read_supervisor_record()
        if record is None:
            return False
        pid, recorded_stamp = record
        return bool(recorded_stamp) and get_process_stamp(pid) == recorded_stamp

    def stop_admin(self) -> None:
        pass

    def restart(self) -> None:
        pass

    def restart_admin(self) -> None:
        pass

    def is_admin_running(self) -> bool:
        return _tcp_port_open(self.bench.config.admin.port)

    def reload_workers(self, web_only: bool = False) -> None:
        """Ask the running dev supervisor to restart its workload processes.

        Callers are separate processes (tasks, CLI), so this leaves a request
        the supervisor picks up rather than signalling processes it does not own."""
        self._clear_frappe_cache()
        if not self.is_running():
            return
        self.bench.pids_path.mkdir(parents=True, exist_ok=True)
        self.reload_request_file.write_text("web" if web_only else "workload")

    def _clear_frappe_cache(self) -> None:
        """Drop the cached app/module map and asset manifest, so restarted
        processes read apps.txt instead of importing a removed app."""
        if not self.bench.sites():
            return
        with contextlib.suppress(BenchError, CommandError, OSError):
            run_command(
                [*self.bench.frappe_call, "frappe", "--site", "all", "clear-cache"],
                cwd=self.bench.sites_path,
                timeout=120,
            )

    def _apply_reload_request(self, defs_by_name: dict[str, ProcessDefinition]) -> None:
        """Restart the processes a queued reload asked for, leaving admin alone."""
        try:
            scope = self.reload_request_file.read_text().strip()
        except OSError:
            return
        self.reload_request_file.unlink(missing_ok=True)
        names = ["web"] if scope == "web" else [n for n in self._procs if n not in _NON_RELOADABLE]
        for name in names:
            definition = defs_by_name.get(name)
            if definition is None or name not in self._procs:
                continue
            print(f"[{name}] reloading", file=sys.stderr)
            self._terminate(self._procs[name])
            self._spawn(definition)

    def _terminate(self, proc: subprocess.Popen) -> None:
        self._signal_group(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=_CHILD_STOP_SECONDS)
        except subprocess.TimeoutExpired:
            self._signal_group(proc, signal.SIGKILL)

    def _signal_group(self, proc: subprocess.Popen, signum: int) -> None:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.killpg(os.getpgid(proc.pid), signum)

    def _spawn(self, pd: ProcessDefinition) -> None:
        proc = subprocess.Popen(
            pd.argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
            cwd=str(pd.working_dir) if pd.working_dir else None,
            env={**os.environ, **pd.env, BENCH_ROOT_ENV: str(self.bench.path)},
        )
        self._procs[pd.name] = proc
        (self.bench.pids_path / f"{pd.name}.pid").write_text(str(proc.pid))
        threading.Thread(target=self._stream, args=(pd.name, proc, self._color(pd.name)), daemon=True).start()

    def _color(self, name: str) -> str:
        return self._colors.setdefault(name, _COLORS[len(self._colors) % len(_COLORS)])

    def _run_processes(self, defs: list[ProcessDefinition]) -> None:
        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        def _stop(_signum, _frame):
            self._stopping = True
            self._stop_all()

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        self.reload_request_file.unlink(missing_ok=True)
        self._stop_timeouts = {pd.name: pd.stop_timeout for pd in defs}
        for pd in defs:
            self._spawn(pd)

        defs_by_name = {pd.name: pd for pd in defs}
        is_critical = {pd.name: pd.critical for pd in defs}
        while not self._stopping:
            for name, proc in list(self._procs.items()):
                if proc.poll() is None:
                    continue
                if is_critical[name]:
                    print(f"[{name}] exited with code {proc.returncode}", file=sys.stderr)
                    self._stopping = True
                    break
                print(f"[{name}] exited with code {proc.returncode}; continuing without it", file=sys.stderr)
                del self._procs[name]
                (self.bench.pids_path / f"{name}.pid").unlink(missing_ok=True)
            if not self._stopping:
                self._apply_reload_request(defs_by_name)
                time.sleep(0.5)

        self._stop_all()
        signal.signal(signal.SIGTERM, original_sigterm)
        signal.signal(signal.SIGINT, original_sigint)

    def _stream(self, name: str, proc: subprocess.Popen, color: str) -> None:
        assert proc.stdout is not None
        prefix = f"{color}[{name}]{_RESET} "
        for raw in proc.stdout:
            sys.stdout.write(prefix + raw.decode(errors="replace") + _RESET)
            sys.stdout.flush()

    def _stop_all(self) -> None:
        # SIGTERM everyone first, then measure each child's stop timeout from
        # that broadcast, so slow children drain concurrently rather than 5s each.
        started = time.monotonic()
        for proc in self._procs.values():
            self._signal_group(proc, signal.SIGTERM)
        for name, proc in self._procs.items():
            budget = self._stop_timeouts.get(name) or _CHILD_STOP_SECONDS
            try:
                proc.wait(timeout=max(started + budget - time.monotonic(), 0))
            except subprocess.TimeoutExpired:
                self._signal_group(proc, signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=_CHILD_STOP_SECONDS)
        self.reload_request_file.unlink(missing_ok=True)

    def _cleanup_proc_pid_files(self) -> None:
        for name in self._procs:
            (self.bench.pids_path / f"{name}.pid").unlink(missing_ok=True)

    def _prod_process_definitions(self) -> list[ProcessDefinition]:
        return self._definitions.prod_process_definitions()

    def _process_definitions(self) -> list[ProcessDefinition]:
        return self._definitions.process_definitions()
