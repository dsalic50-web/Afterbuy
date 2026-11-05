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
class Reason:
    """Jedan razlog koji podiže (+) ili spušta (-) šansu prodaje."""

    points: int
    text: str

    def __str__(self) -> str:
        sign = "+" if self.points > 0 else ("−" if self.points < 0 else "•")
        return f"{sign} {self.text}"


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
    quick_sell_price: float = 0.0       # cijena za brzu prodaju (donji kvartil)
    high_sell_price: float = 0.0        # cijena uz strpljenje (gornji kvartil)
    quick_profit: float = 0.0           # zarada i kad prodaš brzo/jeftinije
    sell_probability: float = 0.5       # procijenjena šansa uspješne preprodaje (0–1)
    est_days_to_sell: float | None = None
    reasons: list[Reason] = field(default_factory=list)
    explanation: str = ""
