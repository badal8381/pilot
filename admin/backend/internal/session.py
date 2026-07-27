"""Bench session tokens: issuing, verifying (local HS256 + remote JWKS), and secret
management. Session is the single entry point -- construct it with a bench and call it.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import TYPE_CHECKING, ClassVar

import jwt
from jwt import PyJWKClient

from pilot.config import BenchConfig
from pilot.internal.atomic_file import exclusive_file_lock, replace_private_text_locked

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class _JtiStore:
    """A private, lock-guarded ``{jti: exp}`` file. Expired entries are dropped from disk
    on every read, and every gunicorn worker shares one view through an exclusive lock.

    Subclasses set ``FILENAME``.
    """

    FILENAME: ClassVar[str]

    def __init__(self, bench: Bench) -> None:
        self._path = bench.path / self.FILENAME

    def add(self, jti: str, exp: int) -> None:
        with exclusive_file_lock(self._path):
            entries = self._prune(self._load_raw())
            entries[jti] = int(exp)
            replace_private_text_locked(self._path, json.dumps(entries))

    def all(self) -> dict[str, int]:
        return self._read()

    def __contains__(self, jti: str) -> bool:
        return jti in self._read()

    def _read(self) -> dict[str, int]:
        """Live entries, purging any expired ones from disk when found."""
        entries = self._load_raw()
        live = self._prune(entries)
        if len(live) != len(entries):
            # Re-read under the lock so a concurrent add of a still-valid jti survives.
            with exclusive_file_lock(self._path):
                live = self._prune(self._load_raw())
                replace_private_text_locked(self._path, json.dumps(live))
        return live

    def _load_raw(self) -> dict[str, int]:
        """Raw ``{jti: exp}`` from disk; empty if missing or unreadable."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _prune(entries: dict[str, int]) -> dict[str, int]:
        now = int(time.time())
        return {jti: exp for jti, exp in entries.items() if isinstance(exp, int) and exp > now}


class ActiveTokens(_JtiStore):
    """Live token jtis this bench has issued or verified (a registry for listing/management)."""

    FILENAME = ".active-jtis.json"


class RevokedTokens(_JtiStore):
    """Token jtis revoked before their expiry; checked on every verification."""

    FILENAME = ".revoked-jtis.json"


class Session:
    """Issues and verifies a single bench's session tokens.

    Locally issued tokens are HS256, signed with the bench's stored secret. Remotely
    issued tokens are verified against the bench's configured JWKS endpoint.
    """

    DEFAULT_TTL = 24 * 3600
    LOGIN_TTL = 5 * 60

    # Asymmetric only: a published JWKS public key must never be accepted as an HMAC secret.
    _JWKS_ALGORITHMS: ClassVar[list[str]] = [
        "RS256",
        "RS384",
        "RS512",
        "ES256",
        "ES384",
        "ES512",
        "PS256",
        "PS384",
        "PS512",
        "EdDSA",
    ]
    _jwks_clients: ClassVar[dict[str, PyJWKClient]] = {}

    def __init__(self, bench: Bench) -> None:
        self.bench = bench

    @property
    def admin_config(self):
        return self.bench.config.admin

    def ensure_jwt_secret(self) -> str:
        """Return this bench's JWT secret, generating and persisting one if absent."""
        if not self.admin_config.jwt_secret:
            with BenchConfig.open(self.bench.path, mode="rw") as config:
                if not config.admin.jwt_secret:
                    config.admin.jwt_secret = secrets.token_urlsafe(32)
                self.admin_config.jwt_secret = config.admin.jwt_secret
        return self.admin_config.jwt_secret

    def issue_session_token(
        self, scope: str = "bench", site: str | None = None, ttl: int = DEFAULT_TTL, via: str = "password"
    ) -> tuple[str, str]:
        """Mint an admin session token (with a jti) and audit-log its issuance."""
        jti = secrets.token_urlsafe(16)
        token = self._encode(ttl=ttl, scope=scope, jti=jti, site=site)
        self.bench.audit_action("session", {"event": "issued", "jti": jti, "scope": scope, "via": via})
        ActiveTokens(self.bench).add(jti, int(time.time()) + ttl)
        return token, jti

    def issue_login_token(self) -> str:
        """A short-lived, single-use token for the ?sid= sign-in link."""
        return self._encode(ttl=self.LOGIN_TTL, scope="bench", jti=secrets.token_urlsafe(8))

    def issue_site_token(self, site: str, ttl: int = DEFAULT_TTL) -> str:
        """A token scoped to a single site for site-to-bench API calls."""
        if not site:
            raise ValueError("Site name is required.")
        return self._encode(ttl=ttl, scope="site", site=site)

    def verify_token(self, token: str) -> dict | None:
        """Verify a token: local HS256 first, then the bench's JWKS keys if configured.

        A token whose jti has been revoked is rejected. A valid, previously unseen jti is
        recorded in the active tracker.
        """
        claims = self._decode(token)
        if claims is None:
            return None
        jti, exp = claims.get("jti"), claims.get("exp")
        if jti:
            if jti in RevokedTokens(self.bench):
                return None
            active = ActiveTokens(self.bench)
            if exp and jti not in active:
                active.add(jti, exp)
        return claims

    @staticmethod
    def has_scope(claims: dict | None, site: str) -> bool:
        if not claims:
            return False
        scope = claims.get("scope")
        if scope == "bench":
            return True
        return scope == "site" and claims.get("site") == site

    def revoke_jti(self, jti: str) -> bool:
        """Revoke an active session by its jti, using its tracked expiry.

        Returns False when the jti is not a known active session (nothing to revoke).
        """
        exp = ActiveTokens(self.bench).all().get(jti)
        if exp is None:
            return False
        RevokedTokens(self.bench).add(jti, exp)
        return True

    def active_jtis(self) -> dict[str, int]:
        """Issued session jtis that are still live: unexpired and not revoked."""
        revoked = RevokedTokens(self.bench)
        return {jti: exp for jti, exp in ActiveTokens(self.bench).all().items() if jti not in revoked}

    def _decode(self, token: str) -> dict | None:
        """Signature/expiry-checked claims: local HS256, then JWKS if configured."""
        claims = self._decode_local(token)
        if claims is None and self.admin_config.jwks_url:
            claims = self._decode_jwks(token)
        return claims

    def _encode(self, ttl: int, scope: str, jti: str | None = None, site: str | None = None) -> str:
        now = int(time.time())
        payload = {"sub": "admin", "iat": now, "exp": now + ttl, "scope": scope}
        if jti:
            payload["jti"] = jti
        if site:
            payload["site"] = site
        return jwt.encode(payload, self.ensure_jwt_secret(), algorithm="HS256")

    def _decode_local(self, token: str) -> dict | None:
        secret = self.admin_config.jwt_secret
        if not token or not secret:
            return None
        try:
            return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp"]})
        except jwt.InvalidTokenError:
            return None

    def _decode_jwks(self, token: str) -> dict | None:
        url, audience = self.admin_config.jwks_url, self.admin_config.jwks_audience
        if not token or not url or not audience:
            return None
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            if not isinstance(kid, str):
                return None
            # Unknown kids must not trigger attacker-controlled refetches.
            signing_key = PyJWKClient.match_kid(self._jwks_client(url).get_signing_keys(), kid)
            if signing_key is None:
                return None
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=self._JWKS_ALGORITHMS,
                audience=audience,
                options={"require": ["exp", "aud"], "verify_aud": True},
            )
        except jwt.PyJWTError:  # PyJWKClientError (fetch failures) subclasses this too
            return None

    @classmethod
    def _jwks_client(cls, url: str) -> PyJWKClient:
        client = cls._jwks_clients.get(url)
        if client is None:
            # A real User-Agent; urllib's default is blocked as a bot by Cloudflare
            # and similar WAFs fronting an issuer, which would fail every fetch.
            client = PyJWKClient(url, headers={"User-Agent": "bench-admin"})
            cls._jwks_clients[url] = client
        return client
