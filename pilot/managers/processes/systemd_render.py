from __future__ import annotations

import re
import shlex

from pilot.managers.processes.base import ServiceRenderer, override
from pilot.managers.processes.local import ProcessDefinition

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def reject_control_chars(pd: ProcessDefinition) -> None:
    """Guard against unit-directive injection: a control char in any declared
    field would let an app inject arbitrary systemd directives into the unit."""
    fields = [pd.name, str(pd.working_dir or ""), *pd.argv]
    for key, value in pd.env.items():
        fields += [key, value]
    if any(_CONTROL_RE.search(field) for field in fields):
        raise ValueError(f"process '{pd.name}' has a control character in a unit field")


def supervisor_escape(value: str) -> str:
    # Double '%' (supervisord expands %(...)s) and escape '"' in quoted values.
    return value.replace("%", "%%").replace('"', '\\"')


def _render_env(env: dict) -> str:
    # Quote every value: an unquoted value with a space would be split by
    # systemd into a second, bogus assignment.
    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    return "".join(f'Environment="{k}={escape(v)}"\n' for k, v in env.items())


class SystemdRenderer(ServiceRenderer):
    """Builds systemd --user unit/socket/target text for a bench."""

    @override
    def render(self, pd: ProcessDefinition) -> str:
        reject_control_chars(pd)
        working_dir = f"WorkingDirectory={pd.working_dir}\n" if pd.working_dir else ""
        env = _render_env(pd.env)
        stop = f"TimeoutStopSec={pd.stop_timeout}\n" if pd.stop_timeout is not None else ""
        return (
            f"[Unit]\n"
            f"Description={self.bench_name} {pd.name}\n"
            f"PartOf={self.bench_name}.target\n\n"
            f"[Service]\n"
            f"Type=simple\n"
            f"{working_dir}{env}"
            f"ExecStart={shlex.join(pd.argv)}\n"
            f"Restart=on-failure\n"
            f"{stop}"
            f"StandardOutput=append:{pd.log_file}\n"
            f"StandardError=append:{pd.log_file}.error.log\n"
        )

    def render_admin_socket(self, port: int) -> str:
        # No PartOf: admin stays reachable while the workload is stopped.
        return (
            f"[Unit]\n"
            f"Description={self.bench_name} admin (socket)\n\n"
            f"[Socket]\n"
            f"ListenStream=127.0.0.1:{port}\n\n"
            f"[Install]\n"
            f"WantedBy=default.target\n"
        )

    def render_admin_service(self, pd: ProcessDefinition, socket_name: str) -> str:
        reject_control_chars(pd)
        env = _render_env(pd.env)
        return (
            f"[Unit]\n"
            f"Description={self.bench_name} admin\n"
            f"Requires={socket_name}\n"
            f"After={socket_name}\n\n"
            f"[Service]\n"
            f"Type=simple\n"
            f"WorkingDirectory={pd.working_dir}\n"
            f"{env}"
            f"ExecStart={shlex.join(pd.argv)}\n"
            # Re-activation is via the socket, not a restart loop.
            f"Restart=no\n"
            # Signal gunicorn only; never cgroup-kill - tasks run as its children
            # and must outlive it idle-stopping or restarting its socket.
            f"KillMode=process\n"
            f"StandardOutput=append:{pd.log_file}\n"
            f"StandardError=append:{pd.log_file}.error.log\n"
        )

    def render_target(self, unit_names: list[str]) -> str:
        return (
            f"[Unit]\n"
            f"Description={self.bench_name} bench\n"
            f"Wants={' '.join(unit_names)}\n\n"
            f"[Install]\n"
            f"WantedBy=default.target\n"
        )
