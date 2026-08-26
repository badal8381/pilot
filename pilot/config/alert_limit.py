import re
from dataclasses import dataclass, field
from typing import NamedTuple

RESOURCE_LIMIT_FIELDS = ("cpu_usage_limit", "memory_usage_limit", "disk_space_limit")
_ADDRESS_RE = re.compile(r"^[^@\s]+@[^@\s]+$")

# Ports the two encryption modes listen on, when one is not given.
STARTTLS_PORT = 587
SSL_PORT = 465


class MailEndpoint(NamedTuple):
    host: str
    port: int
    is_ssl: bool
    username: str
    sender: str


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
    # Outgoing mail, field for field like the framework's Email Account: the
    # address alerts are sent as, the server that accepts them, and how the
    # connection is encrypted. `smtp_login` only when the login name differs
    # from the sender address.
    smtp_server: str = ""
    smtp_port: int = 0
    smtp_email: str = ""
    smtp_login: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = False
    email_recipients: list[str] = field(default_factory=list)

    @property
    def is_mail_configured(self) -> bool:
        """A hand-edited common_config.toml is never validated, so broken settings
        have to read as "no mail sink" rather than raise into the monitoring tick."""
        if not (self.smtp_server and self.smtp_email and self.email_recipients):
            return False
        try:
            self.get_mail_endpoint()
        except ValueError:
            return False
        return True

    def get_mail_endpoint(self) -> MailEndpoint:
        """Server, port, TLS mode and login name, as `send_mail` needs them."""
        host = self.smtp_server.strip()
        if not host:
            raise ValueError("resource_limits.smtp_server is required to send alert emails.")
        sender = self.smtp_email.strip()
        if not _ADDRESS_RE.match(sender):
            raise ValueError("resource_limits.smtp_email must be an email address.")
        port = self.smtp_port or (SSL_PORT if self.smtp_use_ssl else STARTTLS_PORT)
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("resource_limits.smtp_port must be a port number between 1 and 65535.")
        return MailEndpoint(
            host=host,
            port=port,
            is_ssl=bool(self.smtp_use_ssl),
            # An anonymous relay takes no login; the sender address is the default
            # login name, the way the framework treats a blank Alternative Email ID.
            username=(self.smtp_login.strip() or sender) if self.smtp_password else "",
            sender=sender,
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
        # Recipients are configured on their own page, so they are allowed to be
        # saved before a mailbox exists; `is_mail_configured` keeps them idle.
        if self.smtp_server:
            self.get_mail_endpoint()

        for recipient in self.email_recipients:
            # A stricter check than "has an @": a space or newline here would end up
            # in a To: header, where it splits the header rather than failing cleanly.
            if not _ADDRESS_RE.match(recipient):
                raise ValueError(f"resource_limits.email_recipients has a bad address: {recipient!r}.")
