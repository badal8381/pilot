from __future__ import annotations

import typing
from pathlib import Path

from pilot.exceptions import BenchError
from pilot.managers.platform import is_linux
from pilot.managers.systemd_user import SystemdUserMixin, install_user_timer, user_timer_installed
from pilot.utils import cli_root

if typing.TYPE_CHECKING:
    from pilot.core.bench import Bench

SITE_UPTIME_TIMER_TEMPLATE = """\
[Unit]
Description=site uptime monitor timer

[Timer]
OnBootSec=5s
OnUnitInactiveSec=5s
AccuracySec=1s

[Install]
WantedBy=timers.target
"""

SITE_UPTIME_DAEMON_TEMPLATE = """\
[Unit]
Description=site uptime monitor

[Service]
Type=oneshot
WorkingDirectory={cli_root}
Environment=PYTHONPATH={cli_root}
ExecStart={python} -m pilot.core.site.uptime_monitoring
StandardOutput=append:{cli_root}/system/uptime/site-uptime.log
StandardError=append:{cli_root}/system/uptime/site-uptime.error.log

[Install]
WantedBy=default.target
"""


class UptimeMonitorConfigurator(SystemdUserMixin):
    """Installs the shared systemd timer that wakes every few seconds and
    pings every production site's /api/method/ping endpoint. One timer for
    the whole host, covering every sibling bench's sites - install() is a
    no-op once it's already set up. The actual polling logic lives in
    pilot.core.site.uptime_monitoring."""

    def __init__(self, bench: "Bench | None" = None):
        self.bench = bench
        self.unit_name = "site-uptime.service"
        self.timer_unit_name = "site-uptime.timer"
        self.uptime_dir = cli_root() / "system" / "uptime"

    def install(self) -> None:
        if user_timer_installed(self.timer_unit_name):
            return
        install_user_timer(
            unit_dir=self.uptime_dir,
            unit_name=self.unit_name,
            unit_text=self._render_unit(),
            timer_unit_name=self.timer_unit_name,
            timer_text=SITE_UPTIME_TIMER_TEMPLATE,
        )

    @property
    def log_path(self) -> Path:
        return self._require_bench().logs_path / "uptime.json.log"

    def setup(self) -> None:
        if not is_linux():
            raise BenchError("Uptime monitoring is only supported on linux based machines.")

        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _render_unit(self) -> str:
        from pilot.managers.environment import AdminEnvManager

        root = cli_root()
        return SITE_UPTIME_DAEMON_TEMPLATE.format(
            cli_root=root,
            python=AdminEnvManager(root).python,
        )

    def _require_bench(self) -> "Bench":
        assert self.bench is not None, "UptimeMonitorConfigurator needs a bench for this operation"
        return self.bench
