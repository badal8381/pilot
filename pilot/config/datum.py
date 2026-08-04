from dataclasses import dataclass


@dataclass
class DatumConfig:
    """Where the monitor ships metrics. Shipping is off until both are set."""

    endpoint: str = ""
    token: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "DatumConfig":
        return cls(endpoint=data.get("endpoint", ""), token=data.get("token", ""))

    @property
    def is_enabled(self) -> bool:
        return bool(self.endpoint and self.token)
