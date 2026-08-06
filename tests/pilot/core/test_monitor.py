import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import psutil
import pytest

from pilot.config import BenchConfig, MariaDBConfig, RedisConfig, WorkerConfig
from pilot.core.bench import Bench
from pilot.core.server.monitoring import Monitor, MonitorConfigurator
from pilot.core.server.monitoring_proc import CPU_STAT_FIELDS


@pytest.fixture(autouse=True)
def _confine_monitor_logs_to_tmp_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """log_path/system_log_path/etc. are computed from cli_root() with no
    override left - pin it to tmp_path so tests never touch the real host's
    system/logs/ directory."""
    monkeypatch.setattr("pilot.utils.cli_root", lambda: tmp_path)


def _make_bench(path: Path, name: str = "my-bench") -> Bench:
    config = BenchConfig(
        name=name,
        python_version="3.14",
        mariadb=MariaDBConfig(),
        redis=RedisConfig(),
        workers=WorkerConfig(),
    )
    return Bench(config, path)


def _make_monitor(bench: Bench) -> Monitor:
    with patch.object(MonitorConfigurator, "setup"):
        return Monitor(bench)


def _fake_proc_reads(monitor: Monitor) -> None:
    """Stub out /proc reads so tests don't depend on the host machine state."""
    monitor._load_average = lambda: (0.5, 0.4, 0.3)  # type: ignore[method-assign]
    monitor._system_cpu = 12.5
    monitor._memory_usage = lambda: {
        "total_bytes": 8192 * 1024**2,
        "used_bytes": 4096 * 1024**2,
        "available_bytes": 4096 * 1024**2,
        "percent": 50.0,
    }  # type: ignore[method-assign]
    monitor._storage_usage = lambda: {
        "disk": {
            "total_bytes": 51200 * 1024**2,
            "used_bytes": 20480 * 1024**2,
            "free_bytes": 30720 * 1024**2,
            "percent": 40.0,
        }
    }  # type: ignore[method-assign]


def test_collect_system_metrics_writes_to_system_log_file(tmp_path: Path) -> None:
    system_log_file = tmp_path / "system-stats.log"
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"))
    _fake_proc_reads(monitor)

    with patch.object(type(monitor), "system_log_path", new_callable=PropertyMock, return_value=system_log_file):
        monitor.collect_system_metrics()

    assert system_log_file.exists()
    entry = json.loads(system_log_file.read_text().splitlines()[-1])
    assert entry["load_avg"] == [0.5, 0.4, 0.3]
    assert entry["cpu_percent"] == 12.5
    assert entry["memory"]["percent"] == 50.0


def test_collect_system_metrics_does_not_write_app_log(tmp_path: Path) -> None:
    """System metrics must never bleed into the per-bench application log."""
    system_log_file = tmp_path / "system-stats.log"
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"))
    _fake_proc_reads(monitor)

    with patch.object(type(monitor), "system_log_path", new_callable=PropertyMock, return_value=system_log_file):
        monitor.collect_system_metrics()

    assert not monitor.log_path.exists()


def test_collect_system_metrics_includes_storage(tmp_path: Path) -> None:
    system_log_file = tmp_path / "system-stats.log"
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"))
    _fake_proc_reads(monitor)

    with patch.object(type(monitor), "system_log_path", new_callable=PropertyMock, return_value=system_log_file):
        monitor.collect_system_metrics()

    entry = json.loads(system_log_file.read_text().splitlines()[-1])
    assert "storage" in entry
    assert "disk" in entry["storage"]
    assert entry["storage"]["disk"]["percent"] == 40.0


def test_disk_usage_returns_expected_fields(tmp_path: Path) -> None:
    monitor = _make_monitor(_make_bench(tmp_path))
    result = monitor._disk_usage(tmp_path)
    assert result["total_bytes"] > 0
    assert result["used_bytes"] >= 0
    assert result["free_bytes"] >= 0
    assert 0.0 <= result["percent"] <= 100.0
    assert result["total_bytes"] == result["used_bytes"] + result["free_bytes"]


def test_storage_usage_always_includes_disk(tmp_path: Path) -> None:
    monitor = _make_monitor(_make_bench(tmp_path))
    result = monitor._storage_usage()
    assert "disk" in result
    assert result["disk"]["total_bytes"] > 0


def test_compute_cpu_breakdown_sums_to_100_percent(tmp_path: Path) -> None:
    monitor = _make_monitor(_make_bench(tmp_path))
    readings = iter(
        [
            {
                "user": 100,
                "nice": 0,
                "system": 50,
                "idle": 800,
                "iowait": 20,
                "irq": 10,
                "softirq": 10,
                "steal": 10,
            },
            {
                "user": 150,
                "nice": 0,
                "system": 70,
                "idle": 900,
                "iowait": 25,
                "irq": 12,
                "softirq": 12,
                "steal": 11,
            },
        ]
    )
    monitor._cpu_fields = lambda: next(readings)  # type: ignore[method-assign]
    monitor.sample_cpu()
    monitor.compute_cpu()

    breakdown = monitor._cpu_breakdown
    assert set(breakdown) == {"user", "system", "iowait", "irq", "other", "idle"}
    assert abs(sum(breakdown.values()) - 100.0) < 0.5
    assert monitor._system_cpu == round(100 - breakdown["idle"], 2)


def test_compute_cpu_breakdown_zero_delta_reports_idle(tmp_path: Path) -> None:
    """A stalled /proc/stat (identical before/after) must not divide by zero."""
    monitor = _make_monitor(_make_bench(tmp_path))
    fields = {
        "user": 100,
        "nice": 0,
        "system": 50,
        "idle": 800,
        "iowait": 20,
        "irq": 10,
        "softirq": 10,
        "steal": 10,
    }
    monitor._cpu_fields = lambda: dict(fields)  # type: ignore[method-assign]
    monitor.sample_cpu()
    monitor.compute_cpu()

    assert monitor._cpu_breakdown["idle"] == 100.0
    assert monitor._system_cpu == 0.0


def test_memory_usage_breakdown_sums_to_total(tmp_path: Path) -> None:
    monitor = _make_monitor(_make_bench(tmp_path))
    result = monitor._memory_usage()

    assert set(result) >= {
        "total_bytes",
        "used_bytes",
        "cached_bytes",
        "free_bytes",
        "swap_used_bytes",
        "percent",
    }
    assert (
        result["total_bytes"] == result["used_bytes"] + result["cached_bytes"] + result["free_bytes"]
    )


def test_compute_io_reports_bytes_per_sec(tmp_path: Path) -> None:
    monitor = _make_monitor(_make_bench(tmp_path))
    net_readings = iter([{"rx_bytes": 1000, "tx_bytes": 200}, {"rx_bytes": 3000, "tx_bytes": 700}])
    disk_readings = iter(
        [{"read_bytes": 5000, "write_bytes": 1000}, {"read_bytes": 6000, "write_bytes": 1500}]
    )
    monitor._net_fields = lambda: next(net_readings)  # type: ignore[method-assign]
    monitor._disk_io_fields = lambda: next(disk_readings)  # type: ignore[method-assign]

    monitor.sample_io()
    monitor.compute_io()

    assert monitor._network == {"rx_bytes_per_sec": 2000.0, "tx_bytes_per_sec": 500.0}
    assert monitor._disk_io == {"read_bytes_per_sec": 1000.0, "write_bytes_per_sec": 500.0}


def _disk_counter(read_bytes: int, write_bytes: int) -> SimpleNamespace:
    return SimpleNamespace(read_bytes=read_bytes, write_bytes=write_bytes)


def _net_counter(bytes_recv: int, bytes_sent: int) -> SimpleNamespace:
    return SimpleNamespace(bytes_recv=bytes_recv, bytes_sent=bytes_sent)


def test_disk_io_fields_ignores_partitions(tmp_path: Path) -> None:
    """Partitions and dm-/loop devices double-count the disk underneath them."""
    monitor = _make_monitor(_make_bench(tmp_path))
    counters = {
        "sda": _disk_counter(2000, 1000),
        "sda1": _disk_counter(800, 400),
        "nvme0n1": _disk_counter(200, 100),
        "dm-0": _disk_counter(9999, 9999),
        "loop0": _disk_counter(5555, 5555),
    }
    with patch("psutil.disk_io_counters", return_value=counters):
        result = monitor._disk_io_fields()

    assert result == {"read_bytes": 2000 + 200, "write_bytes": 1000 + 100}


def test_net_fields_excludes_loopback(tmp_path: Path) -> None:
    monitor = _make_monitor(_make_bench(tmp_path))
    counters = {
        "eth0": _net_counter(1000, 200),
        "lo": _net_counter(9999, 9999),
        "lo0": _net_counter(8888, 8888),
    }
    with patch("psutil.net_io_counters", return_value=counters):
        result = monitor._net_fields()

    assert result == {"rx_bytes": 1000, "tx_bytes": 200}


def test_cpu_fields_defaults_absent_states_to_zero(tmp_path: Path) -> None:
    """macOS reports no iowait/irq/softirq/steal; the sample must still complete."""
    monitor = _make_monitor(_make_bench(tmp_path))
    times = SimpleNamespace(user=100.0, nice=1.0, system=50.0, idle=800.0)
    with patch("psutil.cpu_times", return_value=times):
        fields = monitor._cpu_fields()

    assert set(fields) == set(CPU_STAT_FIELDS)
    assert fields["user"] == 100.0
    assert fields["iowait"] == 0.0
    assert fields["steal"] == 0.0


def test_proc_memory_falls_back_to_uss_without_pss(tmp_path: Path) -> None:
    """Linux reports PSS; platforms without it fall back to USS, not to zero."""
    monitor = _make_monitor(_make_bench(tmp_path))
    process = SimpleNamespace(memory_full_info=lambda: SimpleNamespace(uss=4 * 1024 * 1024))
    with patch("psutil.Process", return_value=process):
        assert monitor._proc_memory_bytes(1234) == 4 * 1024 * 1024

    process = SimpleNamespace(
        memory_full_info=lambda: SimpleNamespace(pss=2 * 1024 * 1024, uss=4 * 1024 * 1024)
    )
    with patch("psutil.Process", return_value=process):
        assert monitor._proc_memory_bytes(1234) == 2 * 1024 * 1024


def test_io_bytes_is_zero_where_the_platform_has_no_counters(tmp_path: Path) -> None:
    monitor = _make_monitor(_make_bench(tmp_path))
    with patch("psutil.Process", return_value=SimpleNamespace()):
        assert monitor._io_bytes(1234) == (0, 0)

    process = SimpleNamespace(
        io_counters=lambda: SimpleNamespace(read_bytes=500, write_bytes=250)
    )
    with patch("psutil.Process", return_value=process):
        assert monitor._io_bytes(1234) == (500, 250)


def test_collect_application_metrics_marks_a_vanished_process_missing(tmp_path: Path) -> None:
    """A pid that exits between resolution and reading must not kill the tick."""
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"))
    monitor._targets = {"web": 4242}
    app_log = tmp_path / "app.log"

    with (
        patch.object(type(monitor), "log_path", new_callable=PropertyMock, return_value=app_log),
        patch("psutil.Process", side_effect=psutil.NoSuchProcess(4242)),
    ):
        monitor.collect_application_metrics()

    entry = json.loads(app_log.read_text().splitlines()[-1])
    assert entry["processes"] == [{"service": "web", "pid": 4242, "missing": True}]
