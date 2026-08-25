from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from pilot.exceptions import ConfigError
from pilot.utils import PRIVATE_FILE_MODE

KEY_FILENAME = ".secret_key"


def _key_path(benches_root: Path) -> Path:
    return Path(benches_root) / KEY_FILENAME


def _load_or_create_key(benches_root: Path) -> bytes:
    """Called under CommonConfig.write()'s file lock, but read by callers
    outside it - a reader must never be able to observe a partial key, so the
    new key is written to a temp file and moved into place with a single
    atomic rename rather than written in place."""
    path = _key_path(benches_root)
    if path.exists():
        return path.read_bytes()
    key = Fernet.generate_key()
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), PRIVATE_FILE_MODE)
            handle.write(key)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return key


def encrypt(benches_root: Path, plaintext: str) -> str:
    """Encrypt a secret for storage in common_config.toml. Empty stays empty,
    so an unset password round-trips without creating a key file."""
    if not plaintext:
        return ""
    fernet = Fernet(_load_or_create_key(benches_root))
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(benches_root: Path, ciphertext: str) -> str:
    """Decrypt a secret read from common_config.toml. smtp_password has never
    been stored any other way, so non-empty ciphertext with no matching key -
    whether the key file is missing or was replaced - means the secret is
    unreadable. Raise instead of quietly returning "", which a later
    unrelated save would persist as "cleared" and destroy it for good."""
    if not ciphertext:
        return ""
    path = _key_path(benches_root)
    if not path.exists():
        raise ConfigError(
            f"resource_limits.smtp_password could not be decrypted; {path} is missing."
        )
    fernet = Fernet(path.read_bytes())
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ConfigError(
            "resource_limits.smtp_password could not be decrypted; the key at "
            f"{path} does not match the stored value."
        ) from None
