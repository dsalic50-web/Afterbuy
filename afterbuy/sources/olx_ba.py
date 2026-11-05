from __future__ import annotations

from afterbuy.models import Listing
from afterbuy.sources.base import Source, parse_price


class OlxBaSource(Source):
    """OLX.ba (BiH) – koristi JSON pretragu koju poziva i sama web stranica."""

    name = "olx_ba"
    currency = "KM"
    api_url = "https://olx.ba/api/search"

    def fetch_page(self, query, page, min_price, max_price):
        params: dict = {"q": query, "page": page, "per_page": 40}
        if min_price:
            params["price_from"] = int(min_price)
        if max_price:
            params["price_to"] = int(max_price)
        resp = self._get(self.api_url, params=params, headers={"Accept": "application/json"})
        return self.parse(resp.json())

    @classmethod
    def parse(cls, payload: dict | list) -> list[Listing]:
        items = payload.get("data", []) if isinstance(payload, dict) else payload
        out: list[Listing] = []
        for it in items or []:
            if not isinstance(it, dict) or not it.get("id"):
                continue
            price = parse_price(it.get("price")) or parse_price(it.get("display_price"))
            if price is None:
                continue  # "Po dogovoru" / bez cijene – ne može se računati marža
            ext_id = str(it["id"])
            loc = it.get("location") or it.get("city") or ""
            if isinstance(loc, dict):
                loc = loc.get("name") or loc.get("title") or ""
            image = it.get("image") or ""
            if not image and it.get("images"):
                first = it["images"][0]
                image = first.get("url", "") if isinstance(first, dict) else str(first)
            out.append(
                Listing(
                    source=cls.name,
                    ext_id=ext_id,
                    title=str(it.get("title", "")).strip(),
                    price=price,
                    currency=cls.currency,
                    url=f"https://olx.ba/artikal/{ext_id}",
                    location=str(loc),
                    image=str(image),
                    description=str(it.get("short_description") or it.get("description") or ""),
                )
            )
        return out
