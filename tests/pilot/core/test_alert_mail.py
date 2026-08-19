"""Tests for the email sink on the alert fan-out."""

from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import pytest

from pilot.config import BenchConfig, MariaDBConfig, RedisConfig, WorkerConfig
from pilot.config.alert_limit import ResourceLimitConfig
from pilot.core.alerts import notify, send_mail
from pilot.core.bench import Bench

PAYLOAD = {
    "event": "site_down",
    "message": "my-bench: a.test unreachable",
    "context": {"bench": "my-bench", "sites": ["a.test"]},
}


class FakeSMTP:
    """Stands in for both smtplib transports and records what a send did."""

    sends: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in_as: tuple[str, str] | None = None
        self.messages: list = []
        FakeSMTP.sends.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *exception) -> bool:
        return False

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in_as = (username, password)

    def send_message(self, message) -> None:
        self.messages.append(message)


@pytest.fixture(autouse=True)
def _clear_sends():
    FakeSMTP.sends.clear()


def _limits(**overrides) -> ResourceLimitConfig:
    limits = ResourceLimitConfig(
        smtp_url="smtp://alerts@test@smtp.test",
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


def test_the_login_name_is_also_the_sender() -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(), PAYLOAD)

    assert FakeSMTP.sends[0].messages[0]["From"] == "alerts@test"


def test_smtps_connects_over_ssl_on_465() -> None:
    with patch("smtplib.SMTP_SSL", FakeSMTP):
        send_mail(_limits(smtp_url="smtps://alerts@test@smtp.test"), PAYLOAD)

    sent = FakeSMTP.sends[0]
    assert (sent.host, sent.port) == ("smtp.test", 465)
    assert not sent.started_tls


def test_the_url_port_wins_over_the_scheme_default() -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(smtp_url="smtp://alerts@test@smtp.test:2525"), PAYLOAD)

    assert FakeSMTP.sends[0].port == 2525


def test_a_relay_without_a_login_name_sends_anonymously() -> None:
    with patch("smtplib.SMTP", FakeSMTP):
        send_mail(_limits(smtp_url="smtp://smtp.test"), PAYLOAD)

    assert FakeSMTP.sends[0].logged_in_as is None


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


def test_recipients_need_a_mail_server_and_an_address() -> None:
    with pytest.raises(ValueError, match="smtp_url is required"):
        _limits(smtp_url="").validate()

    with pytest.raises(ValueError, match="bad address"):
        _limits(email_recipients=["ops.test"]).validate()


def test_a_malformed_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="smtp:// or smtps://"):
        _limits(smtp_url="smtp.test:587").validate()

    with pytest.raises(ValueError, match="needs a mail server"):
        _limits(smtp_url="smtp://").validate()

    with pytest.raises(ValueError, match="invalid port"):
        _limits(smtp_url="smtp://smtp.test:abc").validate()


def test_the_password_may_not_hide_in_the_url() -> None:
    with pytest.raises(ValueError, match="not in smtp_url"):
        _limits(smtp_url="smtp://user:pw@smtp.test").validate()
