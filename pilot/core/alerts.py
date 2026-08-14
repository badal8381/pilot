from __future__ import annotations

import json
import time
import typing
import urllib.request
from pathlib import Path

from pilot.integrations.central import CentralClient, CentralClientError

if typing.TYPE_CHECKING:
    from pilot.core.bench import Bench

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


def notify(bench: "Bench", payload: dict[str, typing.Any]) -> bool:
    """If we made it to any of the webhooks we will mark this as a successful delivery."""
    delivered = False

    for endpoint, token in bench.config.resource_limits.webhook_endpoints.items():
        try:
            send_alert(endpoint, token, payload)
        except OSError:
            continue
        delivered = True

    try:
        CentralClient(bench).notify_central(**payload)
    except CentralClientError:
        return delivered
    return True


class SustainedAlerts:
    """Names the conditions that have held long enough to alert on. The file is
    the only record of how long each has been true, so one that recovers is
    dropped from it and the file goes away once nothing is active."""

    def __init__(self, path: Path, window_seconds: int = ALERT_SUSTAINED_SECONDS) -> None:
        self.path = path
        self.window_seconds = window_seconds

    def due(self, active: list[str]) -> list[str]:
        """Record this round and return the names that have crossed the window.
        They stay due until mark_notified() confirms an alert actually went out,
        so a round where every sink was down is retried on the next tick."""
        previous = self._read()
        now = time.time()

        state = {}
        due = []
        for name in sorted(active):
            entry = previous.get(name) or {"since": now, "notified": False}
            if not entry["notified"] and now - entry["since"] >= self.window_seconds:
                due.append(name)
            state[name] = entry

        self._write(state)
        return due

    def mark_notified(self, names: list[str]) -> None:
        """Call only once an alert has been delivered. A name marked here does
        not alert again until it recovers and breaks a second time."""
        state = self._read()
        for name in names:
            if name in state:
                state[name]["notified"] = True
        self._write(state)

    def unrecorded(self, names: list[str]) -> list[str]:
        """Of `names`, the ones the bench has not written to its own feed yet.

        Delivery and recording are different facts. A due condition stays due until
        some sink accepts it, so the delivery attempt repeats every tick - the local
        record must not, or a bench with no reachable sink writes one row per tick
        for as long as the condition holds."""
        state = self._read()
        return [name for name in names if not state.get(name, {}).get("recorded")]

    def mark_recorded(self, names: list[str]) -> None:
        """Call once the bench's own feed holds a record for these conditions."""
        state = self._read()
        for name in names:
            if name in state:
                state[name]["recorded"] = True
        self._write(state)

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
