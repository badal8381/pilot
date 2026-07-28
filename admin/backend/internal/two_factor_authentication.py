from __future__ import annotations

import hmac
import json
import secrets
import time

import pyotp

from pilot.core.bench import Bench
from pilot.exceptions import TwoFactorError
from pilot.internal.atomic_file import exclusive_file_lock, replace_private_text_locked

# One step either side of now, so a phone whose clock drifts slightly still works.
DRIFT_STEPS = 1
# An enrollment nobody completes is dropped, so an abandoned secret cannot linger.
PENDING_TTL = 24 * 3600


class TotpCredentialStore:
    """A private, lock-guarded ``{id: credential}`` file.

    Unconfirmed entries past ``PENDING_TTL`` are dropped on every read, and every gunicorn
    worker shares one view through an exclusive lock.
    """

    FILENAME = ".totp-credentials.json"

    def __init__(self, bench: Bench) -> None:
        self._path = bench.path / self.FILENAME

    def all(self) -> dict[str, dict]:
        """Live credentials. Abandoned enrollments are filtered out, not rewritten.

        Verification reads this on every sign-in, so it must never write: the writers
        below already drop expired entries when they rewrite the file anyway.
        """
        return self._prune(self._load_raw())

    def confirmed(self) -> dict[str, dict]:
        """Credentials someone has proved they hold. Only these can authenticate."""
        return {key: entry for key, entry in self.all().items() if entry.get("confirmed_at")}

    def add(self, label: str, secret: str) -> str:
        """Register a pending credential and return its id."""
        credential_id = secrets.token_urlsafe(8)
        with exclusive_file_lock(self._path):
            entries = self._prune(self._load_raw())

            if len(entries) >= 10:
                # This effectively means we don't allow for more than 10 concurrent logins in a 30s window.
                raise TwoFactorError("Too many enrolled devices.")

            entries[credential_id] = {
                "label": label,
                "secret": secret,
                "created_at": int(time.time()),
                "confirmed_at": None,
                "last_timestep": 0,
                "last_used_at": None,
            }
            self._write(entries)
        return credential_id

    def confirm(self, credential_id: str, timestep: int) -> bool:
        """Mark a credential usable, burning the time step that proved it."""
        with exclusive_file_lock(self._path):
            entries = self._prune(self._load_raw())
            entry = entries.get(credential_id)
            if entry is None or entry.get("confirmed_at"):
                return False
            now = int(time.time())
            entry.update(confirmed_at=now, last_timestep=timestep, last_used_at=now)
            self._write(entries)
        return True

    def burn_timestep(self, credential_id: str, timestep: int) -> bool:
        """Spend a time step for one credential, rejecting any step already used.

        Checked and written under a single lock: two workers reading the same stale value
        would otherwise both accept the same code.
        """
        with exclusive_file_lock(self._path):
            entries = self._prune(self._load_raw())
            entry = entries.get(credential_id)
            if entry is None or timestep <= int(entry.get("last_timestep", 0)):
                return False
            entry.update(last_timestep=timestep, last_used_at=int(time.time()))
            self._write(entries)
        return True

    def remove(self, credential_id: str) -> bool:
        with exclusive_file_lock(self._path):
            entries = self._prune(self._load_raw())
            if entries.pop(credential_id, None) is None:
                return False
            self._write(entries)
        return True

    def _write(self, entries: dict[str, dict]) -> None:
        replace_private_text_locked(self._path, json.dumps(entries))

    def _load_raw(self) -> dict[str, dict]:
        """Raw ``{id: credential}`` from disk; empty if missing or unreadable."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _prune(entries: dict[str, dict]) -> dict[str, dict]:
        cutoff = int(time.time()) - PENDING_TTL
        return {
            key: entry
            for key, entry in entries.items()
            if isinstance(entry, dict)
            and (entry.get("confirmed_at") or int(entry.get("created_at", 0)) > cutoff)
        }


class TwoFactorAuthentication:
    """Enrolls devices and verifies their codes for one bench.

    A secret is written once per device and never rotated implicitly: it lives on that
    phone, so regenerating it silently would lock the device out.
    """

    def __init__(self, bench: Bench) -> None:
        self.bench = bench
        self.store = TotpCredentialStore(bench)

    @property
    def is_enabled(self) -> bool:
        """Whether a second factor is required to sign in."""
        return bool(self.store.confirmed())

    def get_credentials(self) -> list[dict]:
        """Public rows for the settings UI. Never exposes a secret."""
        rows = [
            {
                "id": credential_id,
                "label": entry.get("label", ""),
                "confirmed": bool(entry.get("confirmed_at")),
                "created_at": entry.get("created_at"),
                "last_used_at": entry.get("last_used_at"),
            }
            for credential_id, entry in self.store.all().items()
        ]
        return sorted(rows, key=lambda row: row["created_at"] or 0)

    def start_enrollment(self, label: str) -> dict:
        """Create a pending credential and return what an authenticator app needs.

        The secret is returned exactly here. Once confirmed it is never handed back, so a
        stolen session cannot clone an existing device's factor.
        """
        label = label.strip()
        if not label:
            raise TwoFactorError("A device name is required.")
        secret = pyotp.random_base32()
        credential_id = self.store.add(label, secret)
        return {
            "id": credential_id,
            "secret": secret,
            "provisioning_url": self._provisioning_url(label, secret),
        }

    def confirm_enrollment(self, credential_id: str, otp: str) -> bool:
        """Activate a pending credential, but only once a code proves it was set up."""
        entry = self.store.all().get(credential_id)
        if entry is None or entry.get("confirmed_at"):
            return False
        timestep = self._matching_timestep(entry["secret"], otp.strip())
        if timestep is None:
            return False
        return self.store.confirm(credential_id, timestep)

    def remove_credential(self, credential_id: str) -> bool:
        return self.store.remove(credential_id)

    def verify_otp(self, otp: str) -> bool:
        """Accept a code from any enrolled device, burning that device's time step."""
        if not otp:
            return False
        otp = otp.strip()
        for credential_id, entry in self.store.confirmed().items():
            timestep = self._matching_timestep(entry["secret"], otp)
            if timestep is not None:
                return self.store.burn_timestep(credential_id, timestep)
        return False

    def _provisioning_url(self, label: str, secret: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(
            name=label, issuer_name=f"Pilot - {self.bench.config.name}"
        )

    @staticmethod
    def _matching_timestep(secret: str, otp: str) -> int | None:
        """The time step whose code equals ``otp``, or None. Compared in constant time."""
        totp = pyotp.TOTP(secret)
        now = int(time.time())
        for offset in range(-DRIFT_STEPS, DRIFT_STEPS + 1):
            moment = now + offset * totp.interval
            if hmac.compare_digest(totp.at(moment), otp):
                return moment // totp.interval
        return None
