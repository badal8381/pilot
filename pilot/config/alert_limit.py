import re
from dataclasses import dataclass, field
from typing import NamedTuple
from urllib.parse import unquote, urlsplit

RESOURCE_LIMIT_FIELDS = ("cpu_usage_limit", "memory_usage_limit", "disk_space_limit")
# scheme -> (default port, connect over SSL instead of STARTTLS)
SMTP_SCHEMES = {"smtp": (587, False), "smtps": (465, True)}
_ADDRESS_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


class MailEndpoint(NamedTuple):
    host: str
    port: int
    is_ssl: bool
    username: str


@dataclass
class ResourceLimitConfig:
    """Usage percentages that raise a resource alert. Zero disables the alert.
    By defult we will be sending notifications to central however will let users add
    Their custom webhook urls and mail recipients to send notifications to.
    """

    cpu_usage_limit: int = 0
    memory_usage_limit: int = 0
    disk_space_limit: int = 0
    site_uptime: bool = (
        True  # This is boolean to check if site uptime alert is enabled or not. By default it is enabled.
    )
    webhook_endpoints: dict[str, str] = field(default_factory=dict)
    smtp_url: str = ""  # smtp://user@host:587 (STARTTLS) or smtps://user@host:465 (SSL)
    smtp_password: str = ""
    email_recipients: list[str] = field(default_factory=list)

    @property
    def is_mail_configured(self) -> bool:
        """A hand-edited common_config.toml is never validated, so a broken URL has
        to read as "no mail sink" rather than raise into the monitoring tick."""
        if not (self.smtp_url and self.email_recipients):
            return False
        try:
            self.get_mail_endpoint()
        except ValueError:
            return False
        return True

    def get_mail_endpoint(self) -> MailEndpoint:
        """Server, port, TLS mode and login name out of `smtp_url`."""
        parts = urlsplit(self.smtp_url)
        if parts.scheme not in SMTP_SCHEMES:
            raise ValueError("resource_limits.smtp_url must start with smtp:// or smtps://.")
        default_port, is_ssl = SMTP_SCHEMES[parts.scheme]
        if not parts.hostname:
            raise ValueError("resource_limits.smtp_url needs a mail server.")
        try:
            port = parts.port or default_port
        except ValueError:
            raise ValueError("resource_limits.smtp_url has an invalid port.") from None
        return MailEndpoint(
            host=parts.hostname,
            port=port,
            is_ssl=is_ssl,
            username=unquote(parts.username or ""),
        )

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

        self._validate_mail()

    def _validate_mail(self) -> None:
        if self.smtp_url:
            self._validate_smtp_url()
        elif self.email_recipients:
            raise ValueError("resource_limits.smtp_url is required to send alert emails.")

        for recipient in self.email_recipients:
            # A stricter check than "has an @": a space or newline here would end up
            # in a To: header, where it splits the header rather than failing cleanly.
            if not _ADDRESS_RE.match(recipient):
                raise ValueError(f"resource_limits.email_recipients has a bad address: {recipient!r}.")

    def _validate_smtp_url(self) -> None:
        if urlsplit(self.smtp_url).password:
            raise ValueError("Keep the mail password in resource_limits.smtp_password, not in smtp_url.")
        try:
            self.get_mail_endpoint()  # also rejects a port urlsplit cannot read
        except ValueError as error:
            raise ValueError(str(error) or "resource_limits.smtp_url is invalid.") from None
