from __future__ import annotations

import time
from pathlib import Path

import pyotp
import pytest

from admin.backend.internal.two_factor_authentication import (
    TwoFactorAlreadyEnabled,
    TwoFactorAuthentication,
)
from pilot.config import BenchConfig
from pilot.core.bench import Bench


def _bench(tmp_path: Path) -> Bench:
    toml_path = tmp_path / "bench.toml"
    toml_path.write_text(BenchConfig.from_flat(tmp_path.name, {"admin_password": "secret"}).dumps())
    return Bench(BenchConfig.from_file(toml_path), tmp_path)


def _code(two_factor: TwoFactorAuthentication, at: int | None = None) -> str:
    totp = pyotp.TOTP(two_factor.admin_config.totp_secret)
    return totp.at(at) if at else totp.now()


def test_secret_is_valid_base32_and_usable(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    secret = two_factor.ensure_totp_secret()

    # pyotp only rejects a non-base32 secret when a code is generated, not at construction.
    assert pyotp.TOTP(secret).now()
    assert two_factor.verify_otp(_code(two_factor))


def test_secret_is_generated_once_and_persisted(tmp_path: Path) -> None:
    bench_root = tmp_path
    first = TwoFactorAuthentication(_bench(bench_root)).ensure_totp_secret()

    reread = BenchConfig.from_file(bench_root / "bench.toml")
    assert reread.admin.totp_secret == first
    # A second object must not mint a new secret; an enrolled phone would stop working.
    assert TwoFactorAuthentication(Bench(reread, bench_root)).ensure_totp_secret() == first


def test_constructing_does_not_write_a_secret(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))

    assert two_factor.has_secret is False
    assert two_factor.is_enabled is False
    assert BenchConfig.from_file(tmp_path / "bench.toml").admin.totp_secret == ""


def test_enrollment_is_idempotent(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))

    assert two_factor.start_enrollment() == two_factor.start_enrollment()


def test_two_factor_is_only_enabled_after_a_valid_code(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    two_factor.start_enrollment()

    assert two_factor.confirm_enrollment("000000") is False
    assert two_factor.is_enabled is False

    assert two_factor.confirm_enrollment(_code(two_factor)) is True
    assert two_factor.is_enabled is True
    assert BenchConfig.from_file(tmp_path / "bench.toml").admin.totp_enabled is True


def test_enrollment_cannot_be_restarted_once_enabled(tmp_path: Path) -> None:
    """Re-issuing the secret would let a stolen session clone the second factor."""
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    two_factor.start_enrollment()
    two_factor.confirm_enrollment(_code(two_factor))

    with pytest.raises(TwoFactorAlreadyEnabled):
        two_factor.start_enrollment()


def test_a_code_cannot_be_used_twice(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    two_factor.start_enrollment()
    code = _code(two_factor)

    assert two_factor.verify_otp(code) is True
    assert two_factor.verify_otp(code) is False


def test_an_earlier_code_is_rejected_after_a_later_one(tmp_path: Path) -> None:
    """Replay protection burns the time step, not just the code string."""
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    two_factor.start_enrollment()
    now = int(time.time())
    previous = _code(two_factor, at=now - 30)

    assert two_factor.verify_otp(_code(two_factor, at=now)) is True
    assert two_factor.verify_otp(previous) is False


def test_clock_drift_within_one_step_is_accepted(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    two_factor.start_enrollment()

    assert two_factor.verify_otp(_code(two_factor, at=int(time.time()) - 30)) is True


def test_codes_beyond_the_drift_window_are_rejected(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    two_factor.start_enrollment()

    assert two_factor.verify_otp(_code(two_factor, at=int(time.time()) - 120)) is False


def test_verification_without_a_secret_fails_closed(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))

    assert two_factor.verify_otp("000000") is False
    assert two_factor.verify_otp("") is False


def test_disable_clears_the_secret_and_replay_state(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    two_factor.start_enrollment()
    two_factor.confirm_enrollment(_code(two_factor))

    two_factor.disable()

    assert two_factor.is_enabled is False
    assert two_factor.has_secret is False
    assert not (tmp_path / TwoFactorAuthentication.TIMESTEP_FILENAME).exists()
    stored = BenchConfig.from_file(tmp_path / "bench.toml").admin
    assert stored.totp_secret == ""
    assert stored.totp_enabled is False


def test_re_enrolling_after_disable_issues_a_new_secret(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))
    original = two_factor.ensure_totp_secret()
    two_factor.confirm_enrollment(_code(two_factor))

    two_factor.disable()

    assert two_factor.ensure_totp_secret() != original


def test_provisioning_url_names_the_bench(tmp_path: Path) -> None:
    two_factor = TwoFactorAuthentication(_bench(tmp_path))

    url = two_factor.start_enrollment()

    assert url.startswith("otpauth://totp/")
    assert f"issuer=Pilot%20-%20{tmp_path.name}" in url
    assert two_factor.admin_config.totp_secret in url
