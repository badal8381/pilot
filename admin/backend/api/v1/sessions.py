from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, g, jsonify

from admin.backend.api.responses import error_response, no_content_response
from admin.backend.internal.session import Session
from admin.backend.middleware import client_ip, rate_limit, set_session_cookie
from pilot.config import BenchConfig
from pilot.core.bench import Bench
from pilot.core.bench.settings import active_tokens_payload

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.get("")
def list_sessions():
    bench_root = Path(current_app.config["BENCH_ROOT"])
    try:
        config = BenchConfig.read(bench_root)
    except Exception:
        return error_response("settings_unavailable", "Could not read settings.", 500)
    return jsonify(
        {
            "active_tokens": active_tokens_payload(config, bench_root),
            "current_jti": (getattr(g, "jwt_claims", None) or {}).get("jti"),
        }
    )


@sessions_bp.post("/revoke/all")
@rate_limit(5, 60, user_ip=True)
def revoke_all_sessions():
    """Revoke every other live session and re-issue one for the caller."""
    bench = Bench(Path(current_app.config["BENCH_ROOT"]))
    session = Session(bench)
    revoked = session.revoke_all()
    token, jti = session.issue_session_token(ip=client_ip())
    bench.audit_action(
        "session",
        {"event": "other_sessions_revoked", "jti": jti, "revoked_sessions": revoked},
    )

    response = jsonify({"revoked_sessions": revoked})
    set_session_cookie(response, token, current_app.config["SESSION_COOKIE_SECURE"])
    return response


@sessions_bp.post("/revoke/<jti>")
def revoke_session(jti: str):
    """Revoke an active session by its jti. Requires an authenticated bench session."""
    bench = Bench(Path(current_app.config["BENCH_ROOT"]))
    if not Session(bench).revoke_jti(jti):
        return error_response("unknown_session", "No such active session.", 404)
    bench.audit_action("session", {"event": "revoked", "jti": jti})
    return no_content_response()
