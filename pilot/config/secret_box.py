from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from pilot.utils import open_private

KEY_FILENAME = ".secret_key"


def _key_path(benches_root: Path) -> Path:
    return Path(benches_root) / KEY_FILENAME


def _load_or_create_key(benches_root: Path) -> bytes:
    path = _key_path(benches_root)
    if path.exists():
        return path.read_bytes()
    key = Fernet.generate_key()
    with open_private(path, mode="wb") as handle:
        handle.write(key)
    return key


def encrypt(benches_root: Path, plaintext: str) -> str:
    """Encrypt a secret for storage in common_config.toml. Empty stays empty,
    so an unset password round-trips without creating a key file."""
    if not plaintext:
        return ""
    fernet = Fernet(_load_or_create_key(benches_root))
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(benches_root: Path, ciphertext: str) -> str:
    """Decrypt a secret read from common_config.toml. A missing key or a value
    written before encryption was added is treated as unreadable, not fatal."""
    if not ciphertext:
        return ""
    path = _key_path(benches_root)
    if not path.exists():
        return ""
    fernet = Fernet(path.read_bytes())
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ""
