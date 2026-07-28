"""Bench-wide TOTP second factor: enrollment, verification, and replay protection.

One shared secret per bench, matching the single shared admin password. Every enrolled
device produces the same codes, so a code is treated as single-use across the bench.
"""

from __future__ import annotations

import hmac
import time

import pyotp

from pilot.config import BenchConfig
from pilot.core.bench import Bench
from pilot.internal.atomic_file import exclusive_file_lock, replace_private_text_locked

# One step either side of now, so a phone whose clock drifts slightly still works.
DRIFT_STEPS = 1


class TwoFactorAlreadyEnabled(Exception):
    """Raised when enrollment is restarted while 2FA is already on."""


class TwoFactorAuthentication:
    """Issues and verifies this bench's TOTP codes.

    The secret is written once and never rotated implicitly: it lives on enrolled phones,
    so regenerating it silently would lock every one of them out.
    """

    TIMESTEP_FILENAME = ".totp-timestep"

    def __init__(self, bench: Bench) -> None:
        self.bench = bench
        self.admin_config = bench.config.admin
        self._timestep_path = bench.path / self.TIMESTEP_FILENAME

    @property
    def is_enabled(self) -> bool:
        """Whether a confirmed second factor is required to sign in."""
        return bool(self.admin_config.totp_enabled and self.admin_config.totp_secret)

    @property
    def has_secret(self) -> bool:
        """A secret exists, but nobody has proved they can produce a code from it yet."""
        return bool(self.admin_config.totp_secret)

    @property
    def provisioning_url(self) -> str:
        """The ``otpauth://`` URI an authenticator app consumes."""
        return self._totp.provisioning_uri(
            name="admin",
            issuer_name=f"Pilot - {self.bench.config.name}",
        )

    def start_enrollment(self) -> str:
        """Create the secret if absent and return its provisioning URI.

        Refuses once 2FA is on: handing the secret back to an already-authenticated
        session would let a stolen session clone the second factor onto another device.
        """
        if self.is_enabled:
            raise TwoFactorAlreadyEnabled("Two-factor authentication is already enabled.")
        self.ensure_totp_secret()
        return self.provisioning_url

    def confirm_enrollment(self, otp: str) -> bool:
        """Turn 2FA on, but only once a code proves the secret reached an authenticator."""
        if not self.has_secret or not self.verify_otp(otp):
            return False
        with BenchConfig.open(self.bench.path, mode="rw") as config:
            config.admin.totp_enabled = True
        self.admin_config.totp_enabled = True
        return True

    def disable(self) -> None:
        """Turn 2FA off and forget the secret, so re-enrolling starts clean."""
        with BenchConfig.open(self.bench.path, mode="rw") as config:
            config.admin.totp_enabled = False
            config.admin.totp_secret = ""
        self.admin_config.totp_enabled = False
        self.admin_config.totp_secret = ""
        self._timestep_path.unlink(missing_ok=True)

    def ensure_totp_secret(self) -> str:
        """This bench's base32 TOTP secret, generating and persisting one if absent.

        Re-checked under the config lock: gunicorn workers race here, and a loser that
        overwrote the winner's secret would break an already-scanned phone.
        """
        if not self.admin_config.totp_secret:
            with BenchConfig.open(self.bench.path, mode="rw") as config:
                if not config.admin.totp_secret:
                    config.admin.totp_secret = pyotp.random_base32()
                self.admin_config.totp_secret = config.admin.totp_secret
        return self.admin_config.totp_secret

    def verify_otp(self, otp: str) -> bool:
        """Check a code and burn its time step, so the same code cannot be used twice."""
        if not self.has_secret or not otp:
            return False
        timestep = self._matching_timestep(otp.strip())
        if timestep is None:
            return False
        return self._consume_timestep(timestep)

    @property
    def _totp(self) -> pyotp.TOTP:
        return pyotp.TOTP(self.ensure_totp_secret())

    def _matching_timestep(self, otp: str) -> int | None:
        """The time step whose code equals ``otp``, or None. Compared in constant time."""
        totp = self._totp
        now = int(time.time())
        for offset in range(-DRIFT_STEPS, DRIFT_STEPS + 1):
            moment = now + offset * totp.interval
            if hmac.compare_digest(totp.at(moment), otp):
                return moment // totp.interval
        return None

    def _consume_timestep(self, timestep: int) -> bool:
        """Record ``timestep`` as spent, rejecting any step already used."""
        with exclusive_file_lock(self._timestep_path):
            if timestep <= self._last_timestep():
                return False
            replace_private_text_locked(self._timestep_path, str(timestep))
        return True

    def _last_timestep(self) -> int:
        try:
            return int(self._timestep_path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return 0
