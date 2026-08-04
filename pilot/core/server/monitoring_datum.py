from __future__ import annotations

from datetime import datetime

from pilot.config.datum import DatumConfig

try:
    from datum_client import Batch, Datum

    HAS_DATUM_CLIENT = True
except ImportError:
    # Shipping is opt-in (pip install pilot[metrics]); the logs are written regardless.
    HAS_DATUM_CLIENT = False

# Raw MariaDB counter -> the label that separates it from its siblings.
_QUERY_KINDS = {
    "Com_insert": "insert",
    "Com_update": "update",
    "Com_delete": "delete",
    "Com_select": "select",
}


class MetricShipper:
    """Turns one collection tick's records into Datum samples and posts them once.

    The records stay exactly what the JSON-Lines logs hold - the logs remain the
    Admin UI's source of truth, and Datum gets the same numbers as a time series.
    Without the datum_client package, or without an endpoint and token, every
    add_* call is a no-op.
    """

    def __init__(self, config: DatumConfig):
        self.config = config
        ships = HAS_DATUM_CLIENT and config.is_enabled
        self.client = Datum(config.endpoint, config.token) if ships else None
        self.batches: list[Batch] = []

    @property
    def is_enabled(self) -> bool:
        return self.client is not None

    def add_system(self, record: dict) -> None:
        if not self.is_enabled:
            return
        when = _read_time(record)
        cpu = Batch("pilot", "cpu")
        cpu.gauge("usage", record.get("cpu_percent", 0.0), "percent", ts=when)
        for mode, percent in (record.get("cpu_breakdown") or {}).items():
            cpu.gauge("", percent, "percent", ts=when, mode=mode)

        system = Batch("pilot", "system")
        for window, value in zip(("1m", "5m", "15m"), record.get("load_avg") or [], strict=False):
            system.gauge("load_average", value, ts=when, window=window)

        self.batches += [cpu, system, self._memory(record, when), *self._storage(record, when)]

    def add_application(self, record: dict) -> None:
        if not self.is_enabled:
            return
        when = _read_time(record)
        batch = Batch("pilot", "process", bench=record["bench"])
        for process in record.get("processes") or []:
            service = process["service"]
            batch.up("", not process.get("missing"), ts=when, service=service)
            if process.get("missing"):
                continue
            batch.gauge("cpu", process["cpu_percent"], "percent", ts=when, service=service)
            batch.gauge("memory_rss", process["memory_rss_bytes"], "bytes", ts=when, service=service)
            batch.counter("io_read", process["read_bytes"], "bytes", ts=when, service=service)
            batch.counter("io_write", process["write_bytes"], "bytes", ts=when, service=service)
            batch.gauge("state", 1, ts=when, service=service, state=process["state"])
            if process["open_fds"] >= 0:
                batch.gauge("open_fds", process["open_fds"], ts=when, service=service)
        self.batches.append(batch)

    def add_database(self, record: dict | None) -> None:
        if not self.is_enabled or record is None:
            return
        when = _read_time(record)
        batch = Batch("pilot", "database")
        for key, kind in _QUERY_KINDS.items():
            batch.counter("queries", record.get(key, 0), ts=when, kind=kind)
        batch.counter("questions", record.get("Questions", 0), ts=when)
        batch.counter("buffer_pool_reads", record.get("Innodb_buffer_pool_reads", 0), ts=when)
        batch.counter(
            "buffer_pool_read_requests", record.get("Innodb_buffer_pool_read_requests", 0), ts=when
        )
        batch.counter("row_lock_waits", record.get("Innodb_row_lock_waits", 0), ts=when)
        # MariaDB reports Innodb_row_lock_time in milliseconds.
        batch.counter("row_lock_wait", record.get("Innodb_row_lock_time", 0) / 1000, "seconds", ts=when)
        batch.gauge("connections", record.get("Threads_connected", 0), ts=when)
        batch.gauge("max_connections", record.get("max_connections", 0), ts=when)
        batch.gauge("buffer_pool_size", record.get("innodb_buffer_pool_size", 0), "bytes", ts=when)
        batch.gauge("host_memory_total", record.get("total_ram_bytes", 0), "bytes", ts=when)
        self.batches.append(batch)

    def send(self) -> int:
        """One tick, one POST. Returns the HTTP status, or 0 when nothing landed."""
        if not self.client or not self.batches:
            return 0
        status = self.client.send(*self.batches)
        self.batches = []
        return status

    @staticmethod
    def _memory(record: dict, when: datetime | None) -> Batch:
        memory = record.get("memory") or {}
        batch = Batch("pilot", "memory")
        for target in ("total", "used", "cached", "free"):
            batch.gauge(target, memory.get(f"{target}_bytes", 0), "bytes", ts=when)
        batch.gauge("swap_used", memory.get("swap_used_bytes", 0), "bytes", ts=when)
        batch.gauge("usage", memory.get("percent", 0.0), "percent", ts=when)
        return batch

    @staticmethod
    def _storage(record: dict, when: datetime | None) -> list[Batch]:
        disk = (record.get("storage") or {}).get("disk") or {}
        batch = Batch("pilot", "disk")
        for target in ("total", "used", "free"):
            batch.gauge(target, disk.get(f"{target}_bytes", 0), "bytes", ts=when)
        batch.gauge("usage", disk.get("percent", 0.0), "percent", ts=when)

        network, disk_io = record.get("network") or {}, record.get("disk_io") or {}
        throughput = Batch("pilot", "throughput")
        rates = {
            ("network", "receive"): network.get("rx_bytes_per_sec", 0.0),
            ("network", "transmit"): network.get("tx_bytes_per_sec", 0.0),
            ("disk", "read"): disk_io.get("read_bytes_per_sec", 0.0),
            ("disk", "write"): disk_io.get("write_bytes_per_sec", 0.0),
        }
        for (device, direction), value in rates.items():
            throughput.gauge("", value, "bytes_per_second", ts=when, device=device, direction=direction)
        return [batch, throughput]


def _read_time(record: dict) -> datetime | None:
    """Producer time from the record, so every sample in a tick lines up."""
    try:
        return datetime.fromisoformat(record["time"])
    except (KeyError, TypeError, ValueError):
        return None
