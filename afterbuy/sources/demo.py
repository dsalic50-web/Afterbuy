from __future__ import annotations

import hashlib
import random

from afterbuy.models import Listing
from afterbuy.sources.base import Source


class DemoSource(Source):
    """Lažni oglasi za isprobavanje aplikacije bez interneta (python -m afterbuy run --demo)."""

    name = "demo"
    currency = "KM"

    def __init__(self, *args, **kwargs):
        kwargs["request_delay"] = 0
        super().__init__(*args, **kwargs)

    def search(self, query, min_price=None, max_price=None):
        return self.fetch_page(query, 1, min_price, max_price)

    def fetch_page(self, query, page, min_price, max_price):
        seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
        rnd = random.Random(seed)
        lo = min_price or 0
        hi = max_price or float("inf")
        base = rnd.randint(int(max(lo * 1.5, 150)), int(max(min(hi * 0.8, 1200), lo * 1.5 + 1, 151)))
        out = []
        for i in range(25):
            if i < 2:  # par pravih "prilika"
                price = round(base * rnd.uniform(0.35, 0.5))
            else:
                price = round(base * rnd.uniform(0.85, 1.2))
            if not (lo <= price <= hi):
                continue
            out.append(
                Listing(
                    source=self.name,
                    ext_id=f"{seed}-{i}",
                    title=f"{query.title()} – oglas #{i + 1}",
                    price=float(price),
                    currency=self.currency,
                    url=f"https://example.com/oglas/{seed}-{i}",
                    location=rnd.choice(["Sarajevo", "Zagreb", "Tuzla", "Split", "Mostar"]),
                )
            )
        return out
