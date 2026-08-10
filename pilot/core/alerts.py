from __future__ import annotations

import json
import time
import typing
import urllib.request
from pathlib import Path

if typing.TYPE_CHECKING:
    from pilot.config import BenchConfig

# How long a condition must hold before it is worth telling anyone about.
ALERT_SUSTAINED_SECONDS = 300

# A sink that hangs must not hold up the tick that writes the metrics log.
ALERT_TIMEOUT_SECONDS = 10


def send_alert(endpoint: str, token: str, payload: dict[str, typing.Any]) -> None:
    """POST one alert to a webhook endpoint."""
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(request, timeout=ALERT_TIMEOUT_SECONDS):
        pass


def notify_webhooks(config: "BenchConfig", payload: dict[str, typing.Any]) -> None:
    """Deliver to every endpoint the operator configured. One unreachable sink
    must not cost the others their alert, or stop the tick that called this."""
    for endpoint, token in config.resource_limits.webhook_endpoints.items():
        try:
            send_alert(endpoint, token, payload)
        except OSError:
            continue


class SustainedAlerts:
    """Names the conditions that have held long enough to alert on. The file is
    the only record of how long each has been true, so one that recovers is
    dropped from it and the file goes away once nothing is active."""

    def __init__(self, path: Path, window_seconds: int = ALERT_SUSTAINED_SECONDS) -> None:
        self.path = path
        self.window_seconds = window_seconds

    def due(self, active: list[str]) -> list[str]:
        """Record this round and return the names that just crossed the window.
        A name alerts once and re-arms only after it has recovered."""
        previous = self._read()
        now = time.time()

        state = {}
        due = []
        for name in sorted(active):
            entry = previous.get(name) or {"since": now, "notified": False}
            if not entry["notified"] and now - entry["since"] >= self.window_seconds:
                entry["notified"] = True
                due.append(name)
            state[name] = entry

        self._write(state)
        return due

    def _read(self) -> dict[str, dict]:
        """A hand-edited or truncated file starts the window over rather than
        stopping the daemon."""
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, ValueError):
            return {}

    def _write(self, state: dict[str, dict]) -> None:
        if not state:
            self.path.unlink(missing_ok=True)
            return
        self.path.write_text(json.dumps(state))
