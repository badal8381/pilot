from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from pilot.core.site.storage import SiteStorageCollector, SiteStorageReport, SiteStorageUsage
from tests.admin.backend.test_admin_app import _client


def _report(collected_at: str | None = None) -> SiteStorageReport:
    collected_at = collected_at or datetime.now(UTC).isoformat()
    return SiteStorageReport(
        collected_at=collected_at,
        sites=[
            SiteStorageUsage(
                name="s.localhost",
                private_bytes=100,
                public_bytes=20,
                database_bytes=500,
                total_bytes=620,
            )
        ],
    )


def _write_report(bench_root: Path, report: SiteStorageReport) -> None:
    from dataclasses import asdict

    logs = bench_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "site-storage.json").write_text(json.dumps(asdict(report)))


def test_storage_is_served_from_the_collected_report(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    report = _report()
    _write_report(bench_root, report)

    with patch.object(SiteStorageCollector, "collect") as collect:
        response = client.get("/api/v1/sites/storage")

    collect.assert_not_called()
    assert response.status_code == 200
    body = response.get_json()
    assert body["collected_at"] == report.collected_at
    assert body["sites"] == [
        {
            "name": "s.localhost",
            "private_bytes": 100,
            "public_bytes": 20,
            "database_bytes": 500,
            "total_bytes": 620,
        }
    ]


def test_storage_route_is_not_shadowed_by_the_site_detail_route(tmp_path: Path) -> None:
    """`/sites/storage` sits under the same prefix as `/sites/<name>`."""
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_report(bench_root, _report())

    response = client.get("/api/v1/sites/storage")

    assert response.status_code == 200
    assert "sites" in response.get_json()


def test_storage_is_collected_on_demand_when_no_report_exists(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)

    with patch.object(SiteStorageCollector, "collect", return_value=_report()) as collect:
        response = client.get("/api/v1/sites/storage")

    collect.assert_called_once()
    assert response.status_code == 200
    assert response.get_json()["sites"][0]["total_bytes"] == 620


def test_refresh_measures_instead_of_reading_the_report(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_report(bench_root, _report())

    with patch.object(SiteStorageCollector, "collect", return_value=_report()) as collect:
        response = client.get("/api/v1/sites/storage?refresh=true")

    collect.assert_called_once()
    assert response.status_code == 200


def test_storage_reports_an_error_when_it_cannot_be_measured(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)

    with patch.object(SiteStorageCollector, "collect", side_effect=RuntimeError("db is down")):
        response = client.get("/api/v1/sites/storage")

    assert response.status_code == 500
    assert response.get_json()["error"]["message"] == "Could not read site storage usage."
