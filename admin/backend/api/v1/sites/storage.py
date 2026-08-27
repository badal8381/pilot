from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from flask import current_app, jsonify, request

from admin.backend.api.v1.sites import sites_bp
from admin.backend.api.v1.sites.shared import internal_error
from pilot.core.bench import Bench


@sites_bp.get("/storage")
def get_storage():
    """Every site's files and database usage, from the report the site-storage
    timer refreshes. `refresh=true` measures instead, which walks the disk."""
    bench_root = Path(current_app.config["BENCH_ROOT"])
    refresh = request.args.get("refresh", "").lower() in ("1", "true")
    try:
        report = Bench(bench_root).site_storage.get_report(refresh=refresh)
    except Exception:
        return internal_error("Could not read site storage usage.")
    return jsonify(asdict(report))
