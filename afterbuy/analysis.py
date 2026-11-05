"""Procjena tržišne cijene i marže.

Logika:
  * tržišna cijena = medijan cijena usporedivih oglasa (ista pretraga + isti portal,
    zadnjih N dana), nakon izbacivanja ekstremnih vrijednosti (IQR metoda)
  * očekivana prodajna cijena = tržišna cijena * sell_price_factor (oglasi se realno
    prodaju malo ispod tražene cijene)
  * profit = prodajna * (1 - provizija) - fiksni trošak - kupovna cijena
  * marža = profit / kupovna cijena   -> prilika ako je >= min_margin (0.60 = 60 %)
"""
from __future__ import annotations

import statistics

from afterbuy.config import Config, Search
from afterbuy.models import Deal, Listing


def _quantile(sorted_vals: list[float], q: float) -> float:
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def remove_outliers(prices: list[float]) -> list[float]:
    if len(prices) < 4:
        return list(prices)
    s = sorted(prices)
    q1, q3 = _quantile(s, 0.25), _quantile(s, 0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return [p for p in s if lo <= p <= hi]


def estimate_market_price(prices: list[float], min_comparables: int) -> float | None:
    clean = remove_outliers([p for p in prices if p and p > 0])
    if len(clean) < min_comparables:
        return None
    return float(statistics.median(clean))


def matches_search(listing: Listing, search: Search, global_exclude: list[str]) -> bool:
    text = f"{listing.title} {listing.description}".lower()
    title = listing.title.lower()
    if any(word in text for word in global_exclude):
        return False
    if any(word in title for word in search.exclude):
        return False
    # svaki pojam mora biti u naslovu; "a|b" znači "a ili b"
    for term in search.must_include:
        if not any(alt.strip() in title for alt in term.split("|") if alt.strip()):
            return False
    if search.min_price is not None and listing.price < search.min_price:
        return False
    if search.max_price is not None and listing.price > search.max_price:
        return False
    return True


def evaluate(listing: Listing, search: Search, market_price: float, comparables: int, cfg: Config) -> Deal:
    sell = market_price * cfg.sell_price_factor
    profit = sell * (1 - cfg.fee_percent) - cfg.fixed_cost - listing.price
    margin = profit / listing.price if listing.price > 0 else 0.0
    notes: list[str] = []
    suspicious = listing.price < market_price * cfg.suspicious_ratio
    if suspicious:
        notes.append("Cijena je sumnjivo niska – provjeri da nije prevara ili neispravan artikl.")
    if comparables and comparables < cfg.min_comparables:
        notes.append("Malo usporedivih oglasa – procjena je manje pouzdana.")
    return Deal(
        listing=listing,
        search_name=search.name,
        market_price=round(market_price, 2),
        expected_sell_price=round(sell, 2),
        expected_profit=round(profit, 2),
        margin=round(margin, 4),
        comparables=comparables,
        suspicious=suspicious,
        notes=notes,
    )
