from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod

import requests

from afterbuy.models import Listing

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


def parse_price(text: str | float | int | None) -> float | None:
    """'1.299,00 KM' -> 1299.0, '450 €' -> 450.0, 'Po dogovoru' -> None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text) if text > 0 else None
    s = re.sub(r"[^\d.,]", "", str(text))
    if not s:
        return None
    if "," in s and "." in s:
        # zadnji separator je decimalni
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else s.replace(",", "")
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) == 3:  # 1.299 -> tisućice
            s = s.replace(".", "")
    try:
        value = float(s)
    except ValueError:
        return None
    return value if value > 0 else None


class Source(ABC):
    name: str = "base"
    currency: str = ""

    def __init__(self, request_delay: float = 2.0, max_pages: int = 3, session: requests.Session | None = None):
        self.request_delay = request_delay
        self.max_pages = max_pages
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.session.headers.setdefault("Accept-Language", "hr,bs;q=0.9,en;q=0.8")

    def _get(self, url: str, **kwargs) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=20, **kwargs)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(self.request_delay * (2 ** attempt))
        raise last_exc  # type: ignore[misc]

    def search(self, query: str, min_price: float | None = None, max_price: float | None = None) -> list[Listing]:
        results: list[Listing] = []
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            page_items = self.fetch_page(query, page, min_price, max_price)
            new = [it for it in page_items if it.ext_id not in seen]
            if not new:
                break
            for it in new:
                seen.add(it.ext_id)
            results.extend(new)
            if page < self.max_pages:
                time.sleep(self.request_delay)
        log.info("%s: '%s' -> %d oglasa", self.name, query, len(results))
        return results

    @abstractmethod
    def fetch_page(self, query: str, page: int, min_price: float | None, max_price: float | None) -> list[Listing]:
        ...
