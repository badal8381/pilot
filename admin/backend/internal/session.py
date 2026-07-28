from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from typing import TYPE_CHECKING, ClassVar

import jwt
from jwt import PyJWKClient

from pilot.config import BenchConfig
from pilot.internal.atomic_file import replace_private_text_locked

if TYPE_CHECKING:
    from pathlib import Path

    from pilot.core.bench import Bench


class _JtiStore:
    """A private ``{jti: record}`` file, cached in-process by mtime: a cheap ``stat()``
    decides whether the cached dict still matches disk, so a single gunicorn worker
    handling many threads avoids re-reading and re-parsing on every request while still
    picking up a change written by anyone else (another worker, a restart). Subclasses
    set FILENAME and may override ``_prune`` for a richer record shape than a plain
    ``exp`` int.
    """

    FILENAME: ClassVar[str]
    _cache: ClassVar[dict[Path, tuple[float | None, dict]]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, bench: Bench) -> None:
        self._path = bench.path / self.FILENAME

    def add(self, jti: str, exp: int) -> None:
        self._update(lambda entries: entries.__setitem__(jti, int(exp)))

    def extend(self, entries: dict[str, int]) -> None:
        """Add many ``{jti: exp}`` entries in one update."""
        if not entries:
            return
        self._update(lambda live: live.update({jti: int(exp) for jti, exp in entries.items()}))

    def all(self) -> dict:
        with self._lock:
            return dict(self._entries())

    def __contains__(self, jti: str) -> bool:
        with self._lock:
            return jti in self._entries()

    def _update(self, mutate) -> None:
        with self._lock:
            entries = self._entries()
            mutate(entries)
            entries = self._prune(entries)
            replace_private_text_locked(self._path, json.dumps(entries))
            self._cache[self._path] = (self._mtime(), entries)

    def _entries(self) -> dict:
        """This file's entries, from cache if the file hasn't changed since, else disk.

        Re-pruned against the current time either way, so entries that expired since the
        last write still disappear even without a fresh disk read (pruning is a cheap
        dict filter - it's the read/parse that the cache is skipping)."""
        mtime = self._mtime()
        cached = self._cache.get(self._path)
        raw = cached[1] if cached is not None and cached[0] == mtime else self._load_raw()
        entries = self._prune(raw)
        if len(entries) != len(raw):  # garbage-collect expired entries from disk too
            replace_private_text_locked(self._path, json.dumps(entries))
            mtime = self._mtime()
        self._cache[self._path] = (mtime, entries)
        return entries

    def _mtime(self) -> float | None:
        try:
            return self._path.stat().st_mtime
        except FileNotFoundError:
            return None

    def _load_raw(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _prune(entries: dict) -> dict:
        now = int(time.time())
        return {jti: exp for jti, exp in entries.items() if isinstance(exp, int) and exp > now}


class ActiveTokens(_JtiStore):
    """Live sessions this bench has issued or verified, each with its most recent IP and
    last-seen time - refreshed on every request."""

    FILENAME = ".active-jtis.json"

    def touch(self, jti: str, exp: int, ip: str) -> None:
        record = {"exp": int(exp), "ip": ip, "last_seen": int(time.time())}
        self._update(lambda entries: entries.__setitem__(jti, record))

    @staticmethod
    def _prune(entries: dict) -> dict:
        now = int(time.time())
        return {
            jti: record
            for jti, record in entries.items()
            if isinstance(record, dict) and isinstance(record.get("exp"), int) and record["exp"] > now
        }


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
        self, scope: str = "bench", site: str | None = None, ttl: int = DEFAULT_TTL, ip: str = "unknown"
    ) -> tuple[str, str]:
        """Mint an admin session token (with a jti) and register it as active."""
        jti = secrets.token_urlsafe(16)
        token = self._encode(ttl=ttl, scope=scope, jti=jti, site=site)
        ActiveTokens(self.bench).touch(jti, int(time.time()) + ttl, ip)
        return token, jti

    def issue_login_token(self) -> str:
        """A short-lived, single-use token for the ?sid= sign-in link."""
        return self._encode(ttl=self.LOGIN_TTL, scope="bench", jti=secrets.token_urlsafe(8))

    def issue_site_token(self, site: str, ttl: int = DEFAULT_TTL) -> str:
        """A token scoped to a single site for site-to-bench API calls."""
        if not site:
            raise ValueError("Site name is required.")
        return self._encode(ttl=ttl, scope="site", site=site)

    def verify_token(self, token: str, ip: str = "unknown") -> dict | None:
        """Verify a token: local HS256 first, then the bench's JWKS keys if configured.

        A token whose jti has been revoked is rejected. Otherwise its entry in the active
        tracker is refreshed with this request's IP and time.
        """
        claims = self._decode(token)
        if claims is None:
            logging.warning("Rejected unknown or invalid session token from %s", ip)
            return None
        jti, exp = claims.get("jti"), claims.get("exp")
        if jti:
            if jti in RevokedTokens(self.bench):
                return None
            if exp:
                ActiveTokens(self.bench).touch(jti, exp, ip)
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
        record = ActiveTokens(self.bench).all().get(jti)
        if record is None:
            return False
        RevokedTokens(self.bench).add(jti, record["exp"])
        return True

    def revoke_all(self) -> int:
        """Revoke every live session. Returns how many were revoked."""
        live = self.active_jtis()
        RevokedTokens(self.bench).extend(live)
        return len(live)

    def active_jtis(self) -> dict[str, int]:
        """Issued session jtis that are still live: unexpired and not revoked. Maps jti to exp."""
        revoked = RevokedTokens(self.bench)
        return {
            jti: record["exp"] for jti, record in ActiveTokens(self.bench).all().items() if jti not in revoked
        }

    def active_sessions(self) -> dict[str, dict]:
        """Issued sessions still live: unexpired and not revoked. Maps jti to its exp/ip/last_seen."""
        revoked = RevokedTokens(self.bench)
        return {jti: record for jti, record in ActiveTokens(self.bench).all().items() if jti not in revoked}

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
