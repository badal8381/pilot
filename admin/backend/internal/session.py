"""All bench session-token logic: minting, local (HS256) and remote (JWKS) verification,
and the bench-aware Session facade. Backed by PyJWT.

Prefer Session for anything with a bench in hand; the module-level functions are the
secret-parameterized primitives it (and its shims/tests) build on.
"""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING

import jwt
from jwt import PyJWKClient

from pilot.config import BenchConfig

if TYPE_CHECKING:
    from pilot.core.bench import Bench

DEFAULT_TTL = 24 * 3600
LOGIN_TTL = 5 * 60

# Remote (JWKS) tokens must be asymmetric: a published public key must never be
# accepted as an HMAC secret.
_JWKS_ALGORITHMS = [
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

_jwks_clients: dict[str, PyJWKClient] = {}


def issue_token(
    secret: str,
    ttl: int = DEFAULT_TTL,
    issued_at: float | None = None,
    jti: str | None = None,
    scope: str = "bench",
    site: str | None = None,
) -> str:
    if not secret:
        raise ValueError("JWT secret is not configured.")
    now = int(issued_at or time.time())
    payload = {"sub": "admin", "iat": now, "exp": now + ttl, "scope": scope}
    if jti:
        payload["jti"] = jti
    if site:
        payload["site"] = site
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict | None:
    """Return the claims of a valid, unexpired HS256 token, else None."""
    if not token or not secret:
        return None
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp"]})
    except jwt.InvalidTokenError:
        return None


def is_token_valid(token: str, secret: str) -> bool:
    return decode_token(token, secret) is not None


def has_scope(claims: dict | None, site: str) -> bool:
    if not claims:
        return False
    token_scope = claims.get("scope")
    if token_scope == "bench":
        return True
    if token_scope == "site":
        return claims.get("site") == site
    return False


def issue_login_token(secret: str) -> str:
    """A short-lived, single-use token for the ?sid= sign-in link."""
    return issue_token(secret, ttl=LOGIN_TTL, jti=secrets.token_urlsafe(8), scope="bench")


def issue_site_token(secret: str, site: str, ttl: int = DEFAULT_TTL) -> str:
    """A token scoped to a single site for site-to-bench API calls."""
    if not site:
        raise ValueError("Site name is required.")
    return issue_token(secret, ttl=ttl, scope="site", site=site)


def verify_jwks_token(token: str, jwks_url: str, audience: str) -> dict | None:
    """Return verified claims for a remotely-issued token, or None on any auth failure."""
    if not token or not jwks_url or not audience:
        return None
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        if not isinstance(kid, str):
            return None
        # Unknown kids must not trigger attacker-controlled refetches.
        signing_key = PyJWKClient.match_kid(_jwks_client(jwks_url).get_signing_keys(), kid)
        if signing_key is None:
            return None
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=_JWKS_ALGORITHMS,
            audience=audience,
            options={"require": ["exp", "aud"], "verify_aud": True},
        )
    except jwt.PyJWTError:  # PyJWKClientError (fetch failures) subclasses this too
        return None


def _jwks_client(jwks_url: str) -> PyJWKClient:
    client = _jwks_clients.get(jwks_url)
    if client is None:
        # A real User-Agent; urllib's default is blocked as a bot by Cloudflare
        # and similar WAFs fronting an issuer, which would fail every fetch.
        client = PyJWKClient(jwks_url, headers={"User-Agent": "bench-admin"})
        _jwks_clients[jwks_url] = client
    return client


class Session:
    """Bench-owned facade for session tokens: issue, verify, and (later) revoke.

    Every bench token flows through here so the backend shares one code path. Local
    HS256 tokens are minted and verified here; remote tokens are verified against the
    bench's configured JWKS keys.
    """

    def __init__(self, bench: Bench) -> None:
        self.bench = bench

    @property
    def admin_config(self):
        return self.bench.config.admin

    def ensure_jwt_secret(self) -> str:
        """Return the bench JWT secret, generating and persisting one if absent."""
        if self.admin_config.jwt_secret:
            return self.admin_config.jwt_secret
        with BenchConfig.open(self.bench.path, mode="rw") as config:
            if not config.admin.jwt_secret:
                config.admin.jwt_secret = secrets.token_urlsafe(32)
            secret = config.admin.jwt_secret
        self.admin_config.jwt_secret = secret
        return secret

    def issue_session_token(
        self, scope: str = "bench", site: str | None = None, ttl: int = DEFAULT_TTL, via: str = "password"
    ) -> tuple[str, str]:
        """Mint an admin session token (with a jti) and audit-log its issuance."""
        jti = secrets.token_urlsafe(16)
        token = issue_token(self.ensure_jwt_secret(), ttl=ttl, jti=jti, scope=scope, site=site)
        self.bench.audit_action("session", {"event": "issued", "jti": jti, "scope": scope, "via": via})
        return token, jti

    def issue_login_token(self) -> str:
        """A short-lived, single-use token for the ?sid= sign-in link."""
        return issue_login_token(self.ensure_jwt_secret())

    def issue_site_token(self, site: str, ttl: int = DEFAULT_TTL) -> str:
        """A token scoped to a single site for site-to-bench API calls."""
        return issue_site_token(self.ensure_jwt_secret(), site, ttl=ttl)

    def verify_token(self, token: str) -> dict | None:
        """Verify a token: local HS256 first, then the bench's configured JWKS keys."""
        secret = self.admin_config.jwt_secret
        claims = decode_token(token, secret) if secret else None
        if claims is not None:
            return claims
        if self.admin_config.jwks_url:
            return verify_jwks_token(token, self.admin_config.jwks_url, self.admin_config.jwks_audience)
        return None

    def has_scope(self, claims: dict | None, site: str) -> bool:
        return has_scope(claims, site)

    def revoke_token(self, token: str) -> None:
        raise NotImplementedError("Token revocation is not yet supported.")
