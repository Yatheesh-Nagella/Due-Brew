import logging
import smtplib

import pytest

from due_brew.config import get_settings
from due_brew.emails import sender as sender_module
from due_brew.emails.sender import DryRunSender, Email, FakeSender, SmtpSender, build_message, get_sender

EMAIL = Email(to="alice@example.com", subject="[due-brew] Rent", text="plain body", html="<p>html body</p>")


class StubSMTP:
    """Stands in for smtplib.SMTP and records what was called."""

    instances: list["StubSMTP"] = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout
        self.calls: list[str] = []
        self.messages = []
        StubSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("quit")

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(f"login {user}")

    def send_message(self, message):
        self.calls.append("send")
        self.messages.append(message)


@pytest.fixture
def stub_smtp(monkeypatch):
    StubSMTP.instances = []
    monkeypatch.setattr(sender_module.smtplib, "SMTP", StubSMTP)
    return StubSMTP


def test_message_is_multipart_text_and_html():
    message = build_message(EMAIL, "Due and Brew <house@example.com>")

    assert message["From"] == "Due and Brew <house@example.com>"
    assert message["To"] == "alice@example.com"
    assert message["Subject"] == "[due-brew] Rent"
    assert message.get_content_type() == "multipart/alternative"
    parts = {p.get_content_type(): p.get_content() for p in message.iter_parts()}
    assert parts["text/plain"].strip() == "plain body"
    assert parts["text/html"].strip() == "<p>html body</p>"


def test_gmail_style_starttls_then_login(env, stub_smtp):
    env(
        SMTP_HOST="smtp.gmail.com", SMTP_PORT="587", SMTP_USERNAME="house@example.com", SMTP_PASSWORD="app-pw"
    )

    SmtpSender(get_settings()).send(EMAIL)

    smtp = stub_smtp.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 587)
    assert smtp.calls == ["starttls", "login house@example.com", "send", "quit"]


def test_local_inbox_without_tls_or_login(env, stub_smtp):
    env(SMTP_HOST="mailpit", SMTP_PORT="1025", SMTP_STARTTLS="false", SMTP_USERNAME=None)

    SmtpSender(get_settings()).send(EMAIL)

    assert stub_smtp.instances[0].calls == ["send", "quit"]


def test_dry_run_logs_subject_not_body(env, caplog):
    env(NOTIFIER_DRY_RUN="true")
    sender = get_sender()

    with caplog.at_level(logging.INFO):
        sender.send(EMAIL)

    assert isinstance(sender, DryRunSender)
    assert "[due-brew] Rent" in caplog.text
    assert "plain body" not in caplog.text


def test_get_sender_defaults_to_smtp(env):
    env(NOTIFIER_DRY_RUN=None)

    assert isinstance(get_sender(), SmtpSender)


def test_smtp_password_never_logged(env, stub_smtp, caplog):
    env(SMTP_USERNAME="house@example.com", SMTP_PASSWORD="super-secret-app-pw")

    with caplog.at_level(logging.DEBUG):
        SmtpSender(get_settings()).send(EMAIL)

    assert "super-secret-app-pw" not in caplog.text


def test_fake_sender_records_and_fails_on_demand():
    fake = FakeSender()
    fake.send(EMAIL)
    fake.failing, fake.fail_times = True, 1

    with pytest.raises(smtplib.SMTPException):
        fake.send(EMAIL)
    fake.send(EMAIL)  # failed only once

    assert fake.subjects() == ["[due-brew] Rent", "[due-brew] Rent"]
