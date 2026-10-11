"""Every email leaves through an EmailSender, so tests can swap in a fake.

SmtpSender    real delivery (Gmail: smtp.gmail.com:587, STARTTLS, app password)
DryRunSender  NOTIFIER_DRY_RUN=true: logs who and what, sends nothing
FakeSender    tests: records emails, can be told to fail
"""

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from due_brew.config import Settings, get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str


class EmailSender(Protocol):
    def send(self, email: Email) -> None:
        """Deliver or raise. Returning normally means the server accepted it."""


def build_message(email: Email, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = email.to
    message["Subject"] = email.subject
    message.set_content(email.text)
    message.add_alternative(email.html, subtype="html")
    return message


class SmtpSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, email: Email) -> None:
        s = self.settings
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password or "")
            smtp.send_message(build_message(email, s.email_from))
        log.info("sent %r to %s", email.subject, email.to)


class DryRunSender:
    def send(self, email: Email) -> None:
        log.info("DRY RUN: would send %r to %s", email.subject, email.to)
        # Bodies only at debug level: they can hold amounts and names.
        log.debug("DRY RUN body:\n%s", email.text)


@dataclass
class FakeSender:
    sent: list[Email] = field(default_factory=list)
    # Raise for this many upcoming sends (or forever when None) once `failing` is set.
    failing: bool = False
    fail_times: int | None = None
    error: str = "SMTP unavailable"

    def send(self, email: Email) -> None:
        if self.failing and (self.fail_times is None or self.fail_times > 0):
            if self.fail_times is not None:
                self.fail_times -= 1
            raise smtplib.SMTPException(self.error)
        self.sent.append(email)

    def subjects(self) -> list[str]:
        return [e.subject for e in self.sent]


def get_sender() -> EmailSender:
    settings = get_settings()
    if settings.notifier_dry_run:
        return DryRunSender()
    return SmtpSender(settings)
