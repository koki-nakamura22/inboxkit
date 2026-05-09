from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

from ..types import Digest, Item
from . import SinkError


class EmailSink:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        sender: str,
        recipients: list[str],
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._sender = sender
        self._recipients = recipients
        self._username = username or os.environ.get("EMAIL_USERNAME")
        self._password = password or os.environ.get("EMAIL_PASSWORD")
        self._use_tls = use_tls

    def write(self, digest: Digest, item: Item) -> None:
        msg = MIMEText(digest.summary)
        msg["Subject"] = f"digestkit: {item.id}"
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._recipients)
        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username and self._password:
                    smtp.login(self._username, self._password)
                smtp.send_message(msg)
        except smtplib.SMTPException as e:
            raise SinkError(str(e)) from e
