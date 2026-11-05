from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Listing:
    """Jedan oglas s nekog portala."""

    source: str
    ext_id: str
    title: str
    price: float
    currency: str
    url: str
    location: str = ""
    image: str = ""
    description: str = ""


@dataclass
class Deal:
    """Oglas koji je prošao analizu profitabilnosti."""

    listing: Listing
    search_name: str
    market_price: float
    expected_sell_price: float
    expected_profit: float
    margin: float
    comparables: int
    suspicious: bool = False
    notes: list[str] = field(default_factory=list)
