from __future__ import annotations

import httpx
import trafilatura

from digestkit_core.extractors.pdf import ExtractionError
from digestkit_core.types import Item


class WebPageExtractor:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def extract(self, item: Item) -> str:
        url = str(item.payload)
        try:
            response = httpx.get(url, timeout=self._timeout, follow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                raise ExtractionError(f"Non-HTML content-type: {content_type}")
            text = trafilatura.extract(response.text)
            if text is None:
                raise ExtractionError(f"trafilatura returned None for {url}")
            return text
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise ExtractionError(str(e)) from e
