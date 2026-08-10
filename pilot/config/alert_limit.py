from dataclasses import dataclass, field

RESOURCE_LIMIT_FIELDS = ("cpu_usage_limit", "memory_usage_limit", "disk_space_limit")


@dataclass
class ResourceLimitConfig:
    """Usage percentages that raise a resource alert. Zero disables the alert.
    By defult we will be sending notifications to central however will let users add
    Their custom webhook urls to send notifications to.
    """

    cpu_usage_limit: int = 0
    memory_usage_limit: int = 0
    disk_space_limit: int = 0
    site_uptime: bool = (
        True  # This is boolean to check if site uptime alert is enabled or not. By default it is enabled.
    )
    webhook_endpoints: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        for name in RESOURCE_LIMIT_FIELDS:
            limit = getattr(self, name)
            if not isinstance(limit, int) or isinstance(limit, bool):
                raise ValueError(f"resource_limits.{name} must be a whole number.")
            if not 0 <= limit <= 100:
                raise ValueError(f"resource_limits.{name} must be a percentage between 0 and 100.")

        for url, token in self.webhook_endpoints.items():
            if not url or not token:
                raise ValueError("webhook_endpoints and token must be non-empty strings.")
