from __future__ import annotations

import os

import httpx

from ..digester import ConfigurationError
from ..types import Digest, Item
from . import SinkError


class SlackSink:
    def __init__(
        self,
        webhook_url: str | None = None,
        timeout: float = 10.0,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        if not url:
            raise ConfigurationError("SlackSink requires webhook_url or SLACK_WEBHOOK_URL env")
        if not url.startswith("https://"):
            raise ConfigurationError("SlackSink webhook_url must use https://")
        self._webhook_url = url
        self._timeout = timeout
        self._transport = _transport

    def write(self, digest: Digest, item: Item) -> None:
        payload = {"text": f"digestkit: {item.id}\n\n{digest.summary}"}
        try:
            with httpx.Client(transport=self._transport) as client:
                response = client.post(self._webhook_url, json=payload, timeout=self._timeout)
                response.raise_for_status()
        except httpx.HTTPError as e:
            raise SinkError(str(e)) from e
