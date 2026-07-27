"""Bench session tokens: issuing, verifying (local HS256 + remote JWKS), and secret
management. Session is the single entry point -- construct it with a bench and call it.
"""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING, ClassVar

import jwt
from jwt import PyJWKClient

from pilot.config import BenchConfig

if TYPE_CHECKING:
    from pilot.core.bench import Bench


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
        """Verify a token: local HS256 first, then the bench's JWKS keys if configured."""
        claims = self._decode_local(token)
        if claims is not None:
            return claims
        if self.admin_config.jwks_url:
            return self._decode_jwks(token)
        return None

    @staticmethod
    def has_scope(claims: dict | None, site: str) -> bool:
        if not claims:
            return False
        scope = claims.get("scope")
        if scope == "bench":
            return True
        return scope == "site" and claims.get("site") == site

    def revoke_token(self, token: str) -> None:
        raise NotImplementedError("Token revocation is not yet supported.")

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
