from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from pilot.config.secret_box import _key_path, decrypt, encrypt
from pilot.exceptions import ConfigError


def test_round_trips_a_secret(tmp_path: Path) -> None:
    ciphertext = encrypt(tmp_path, "s3cret")
    assert ciphertext != "s3cret"
    assert decrypt(tmp_path, ciphertext) == "s3cret"


def test_empty_secret_round_trips_without_a_key_file(tmp_path: Path) -> None:
    assert encrypt(tmp_path, "") == ""
    assert not _key_path(tmp_path).exists()


def test_ciphertext_with_no_key_file_reads_as_unset(tmp_path: Path) -> None:
    """A value written before encryption was added has no key file yet."""
    assert decrypt(tmp_path, "not-actually-ciphertext") == ""


def test_ciphertext_that_fails_against_an_existing_key_raises(tmp_path: Path) -> None:
    """Silently returning "" here would let a later unrelated save persist
    that as "the password was cleared" and destroy the real secret."""
    encrypt(tmp_path, "s3cret")  # creates the real key file
    foreign_ciphertext = Fernet(Fernet.generate_key()).encrypt(b"other").decode()

    with pytest.raises(ConfigError, match="could not be decrypted"):
        decrypt(tmp_path, foreign_ciphertext)


def test_key_file_never_appears_partially_written(tmp_path: Path, monkeypatch) -> None:
    """_load_or_create_key must write through a temp file and rename, not
    write the target path in place, so a concurrent unlocked reader can
    never observe a truncated key."""
    import os

    from pilot.config import secret_box

    real_replace = os.replace
    seen_sizes = []

    def _tracking_replace(src, dst):
        seen_sizes.append(Path(src).stat().st_size)
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _tracking_replace)
    secret_box._load_or_create_key(tmp_path)

    assert seen_sizes == [len(Fernet.generate_key())]
    assert _key_path(tmp_path).stat().st_size == len(Fernet.generate_key())
