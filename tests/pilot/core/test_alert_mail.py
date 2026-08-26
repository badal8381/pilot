"""Tests for the email sink on the alert fan-out."""

import smtplib
import ssl
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import pytest

from pilot.config import BenchConfig, MariaDBConfig, RedisConfig, WorkerConfig
from pilot.config.alert_limit import ResourceLimitConfig
from pilot.core.alerts import check_mail_credentials, notify, send_mail
from pilot.core.bench import Bench

PAYLOAD = {
    "event": "site_down",
    "message": "my-bench: a.test unreachable",
    "context": {"bench": "my-bench", "sites": ["a.test"]},
}


class FakeSMTP:
    """Stands in for both smtplib transports and records what a send did."""

    sends: ClassVar[list["FakeSMTP"]] = []
    refuse: ClassVar[dict] = {}  # recipients smtplib reports back as refused

    def __init__(self, host: str, port: int, timeout: float | None = None, context=None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.started_tls = False
        self.logged_in_as: tuple[str, str] | None = None
        self.messages: list = []
        FakeSMTP.sends.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *exception) -> bool:
        return False

    def starttls(self, context=None) -> None:
        self.started_tls = True
        self.context = context

    def login(self, username: str, password: str) -> None:
        self.logged_in_as = (username, password)

    def send_message(self, message) -> dict:
        self.messages.append(message)
        return dict(FakeSMTP.refuse)


@pytest.fixture(autouse=True)
def _clear_sends():
    FakeSMTP.sends.clear()


def _limits(**overrides) -> ResourceLimitConfig:
    limits = ResourceLimitConfig(
        smtp_server="smtp.test",
        smtp_email="alerts@test",
        smtp_password="secret",
        email_recipients=["ops@test"],
    )
    for name, value in overrides.items():
        setattr(limits, name, value)
    return limits


def _bench(tmp_path: Path, limits: ResourceLimitConfig) -> Bench:
    config = BenchConfig(
        name="my-bench",
        python_version="3.14",
        mariadb=MariaDBConfig(),
        redis=RedisConfig(),
        workers=WorkerConfig(),
    )
    config.resource_limits = limits
    return Bench(config, tmp_path / "my-bench")


def test_the_alert_is_mailed_over_starttls() -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(email_recipients=["ops@test", "oncall@test"]), PAYLOAD)

    sent = FakeSMTP.sends[0]
    message = sent.messages[0]
    assert (sent.host, sent.port) == ("smtp.test", 587)
    assert sent.started_tls
    assert sent.logged_in_as == ("alerts@test", "secret")
    assert message["To"] == "ops@test, oncall@test"
    assert message["Subject"] == "[Pilot] my-bench: a.test unreachable"
    assert "a.test" in message.get_content()


def test_both_transports_verify_the_server_certificate() -> None:
    """smtplib's own default context skips verification, which would hand the
    password to whoever answers on an intercepted connection."""
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(), PAYLOAD)
    with patch("smtplib.SMTP_SSL", FakeSMTP):
        send_mail(_limits(smtp_use_ssl=True), PAYLOAD)

    for send in FakeSMTP.sends:
        assert send.context is not None
        assert send.context.verify_mode == ssl.CERT_REQUIRED
        assert send.context.check_hostname


def test_the_address_is_the_sender_and_the_default_login_name() -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(), PAYLOAD)

    sent = FakeSMTP.sends[0]
    assert sent.messages[0]["From"] == "alerts@test"
    assert sent.logged_in_as == ("alerts@test", "secret")


def test_a_separate_login_name_does_not_change_the_sender() -> None:
    """The framework's Email Account allows a login that is not the address; the
    mail still has to come from the address the operator configured."""
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(smtp_login="alerts"), PAYLOAD)

    sent = FakeSMTP.sends[0]
    assert sent.logged_in_as == ("alerts", "secret")
    assert sent.messages[0]["From"] == "alerts@test"


def test_ssl_connects_on_465() -> None:
    with patch("smtplib.SMTP_SSL", FakeSMTP):
        send_mail(_limits(smtp_use_ssl=True), PAYLOAD)

    sent = FakeSMTP.sends[0]
    assert (sent.host, sent.port) == ("smtp.test", 465)
    assert not sent.started_tls


def test_a_configured_port_wins_over_the_default() -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(smtp_port=2525), PAYLOAD)

    assert FakeSMTP.sends[0].port == 2525


def test_a_relay_without_a_password_sends_anonymously() -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(smtp_password=""), PAYLOAD)

    sent = FakeSMTP.sends[0]
    assert sent.logged_in_as is None
    # An empty From becomes MAIL FROM:<>, which most relays refuse.
    assert sent.messages[0]["From"] == "alerts@test"


def test_a_refused_recipient_is_not_a_delivery(tmp_path: Path) -> None:
    """send_message reports per-recipient refusals by returning them; a partial
    send must not retire the alert for the mailbox that never got it."""
    refused = {"oncall@test": (550, b"No such user")}

    with patch("smtplib.SMTP", FakeSMTP), patch.object(FakeSMTP, "refuse", refused):
        delivered = notify(_bench(tmp_path, _limits()), PAYLOAD)

    assert not delivered


def test_broken_settings_disable_mail_instead_of_raising(tmp_path: Path) -> None:
    """common_config.toml can be hand-edited, and most config reads skip validation,
    so bad settings have to read as "no mail sink" rather than kill the monitor tick."""
    for overrides in ({"smtp_email": "not-an-address"}, {"smtp_port": 70000}, {"smtp_server": ""}):
        limits = _limits(**overrides)
        assert not limits.is_mail_configured
        with patch("smtplib.SMTP", FakeSMTP):
            assert notify(_bench(tmp_path, limits), PAYLOAD) is False
    assert FakeSMTP.sends == []


def test_mail_counts_as_delivery_when_every_webhook_fails(tmp_path: Path) -> None:
    limits = _limits(webhook_endpoints={"https://one.test": "token"})

    with (
        patch("smtplib.SMTP", FakeSMTP),
        patch("pilot.core.alerts.send_alert", side_effect=OSError("unreachable")),
    ):
        delivered = notify(_bench(tmp_path, limits), PAYLOAD)

    assert delivered
    assert len(FakeSMTP.sends) == 1


def test_an_unreachable_mail_server_is_not_a_delivery(tmp_path: Path) -> None:
    with patch("smtplib.SMTP", side_effect=OSError("unreachable")):
        assert not notify(_bench(tmp_path, _limits()), PAYLOAD)


def test_no_mail_goes_out_without_recipients(tmp_path: Path) -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        notify(_bench(tmp_path, _limits(email_recipients=[])), PAYLOAD)

    assert FakeSMTP.sends == []


def test_recipients_may_be_saved_before_a_mailbox_exists() -> None:
    """Recipients are configured on the notifications page, the mailbox on its
    own one, so neither order of setting them up may fail validation."""
    _limits(smtp_server="", smtp_email="", smtp_password="").validate()


def test_a_bad_recipient_is_rejected() -> None:
    with pytest.raises(ValueError, match="bad address"):
        _limits(email_recipients=["ops.test"]).validate()


def test_malformed_server_settings_are_rejected() -> None:
    with pytest.raises(ValueError, match="smtp_email must be an email address"):
        _limits(smtp_email="alerts").validate()

    with pytest.raises(ValueError, match="smtp_port must be a port number"):
        _limits(smtp_port=70000).validate()


def test_the_credential_check_opens_and_drops_a_session() -> None:
    """Settings are proved against the server while they are being saved, the
    way the framework's Email Account opens a session on save."""
    with patch("smtplib.SMTP", FakeSMTP):
        check_mail_credentials(_limits())

    sent = FakeSMTP.sends[0]
    assert sent.logged_in_as == ("alerts@test", "secret")
    assert sent.messages == []


def test_the_credential_check_raises_on_a_bad_password() -> None:
    error = smtplib.SMTPAuthenticationError(535, b"Bad credentials")
    with (
        patch("smtplib.SMTP", FakeSMTP),
        patch.object(FakeSMTP, "login", side_effect=error),
        pytest.raises(smtplib.SMTPAuthenticationError),
    ):
        check_mail_credentials(_limits())
