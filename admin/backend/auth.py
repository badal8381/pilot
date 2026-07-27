"""Backwards-compatible shims over admin.backend.internal.session.

All token logic now lives in admin.backend.internal.session (both the primitives and the
bench-aware Session). Prefer Session for anything with a bench in hand; these re-exports
keep secret-parameterized call sites and their tests working.
"""

from __future__ import annotations

from admin.backend.internal.session import (
    DEFAULT_TTL,
    LOGIN_TTL,
    decode_token,
    has_scope,
    is_token_valid,
    issue_login_token,
    issue_site_token,
    issue_token,
)

__all__ = [
    "DEFAULT_TTL",
    "LOGIN_TTL",
    "decode_token",
    "ensure_jwt_secret",
    "has_scope",
    "is_token_valid",
    "issue_login_token",
    "issue_site_token",
    "issue_token",
]


def ensure_jwt_secret(toml_path) -> str:
    from admin.backend.internal.session import Session
    from pilot.core.bench import Bench

    return Session(Bench(toml_path.parent)).ensure_jwt_secret()
