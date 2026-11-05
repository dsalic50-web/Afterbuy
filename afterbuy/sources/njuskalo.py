from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from afterbuy.models import Listing
from afterbuy.sources.base import Source, parse_price


class NjuskaloSource(Source):
    """Njuškalo.hr (HR) – parsira HTML rezultate pretrage.

    Napomena: Njuškalo često blokira automatizirane zahtjeve (anti-bot zaštita).
    Ako dobivaš HTTP 403, smanji učestalost ili koristi samo OLX.ba.
    """

    name = "njuskalo"
    currency = "EUR"
    base_url = "https://www.njuskalo.hr"

    def fetch_page(self, query, page, min_price, max_price):
        params: dict = {"keywords": query, "page": page}
        if min_price:
            params["price[min]"] = int(min_price)
        if max_price:
            params["price[max]"] = int(max_price)
        resp = self._get(f"{self.base_url}/search/", params=params)
        return self.parse(resp.text)

    @classmethod
    def parse(cls, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Listing] = []
        for li in soup.select("li.EntityList-item--Regular, li.EntityList-item--VauVau"):
            link = li.select_one("h3.entity-title a, .entity-title a")
            price_el = li.select_one(".price--eur, .price-item .price, strong.price, .price")
            if not link or not price_el:
                continue
            href = link.get("href") or li.get("data-href") or ""
            m = re.search(r"oglas-(\d+)", href)
            ext_id = m.group(1) if m else href
            price = parse_price(price_el.get_text(" ", strip=True))
            if not ext_id or price is None:
                continue
            img = li.select_one("img")
            image = ""
            if img:
                image = img.get("data-src") or img.get("src") or ""
            desc_el = li.select_one(".entity-description-main, .entity-description")
            out.append(
                Listing(
                    source=cls.name,
                    ext_id=str(ext_id),
                    title=link.get_text(" ", strip=True),
                    price=price,
                    currency=cls.currency,
                    url=urljoin(cls.base_url, href),
                    image=urljoin(cls.base_url, image) if image else "",
                    description=desc_el.get_text(" ", strip=True) if desc_el else "",
                )
            )
        return out
