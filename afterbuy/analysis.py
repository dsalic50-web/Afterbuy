"""Procjena tržišne cijene, marže i šanse uspješne preprodaje.

Cijena:
  * tržišna cijena = medijan cijena usporedivih oglasa (ista pretraga + isti portal,
    zadnjih N dana), nakon izbacivanja ekstremnih vrijednosti (IQR metoda)
  * realna prodaja = medijan * sell_price_factor; brza prodaja = donji kvartil * faktor;
    prodaja uz strpljenje = gornji kvartil * faktor
  * profit = prodaja * (1 - provizija) - fiksni trošak - kupovna cijena
  * marža = profit / kupovna cijena   -> prilika ako je >= min_margin (0.60 = 60 %)

Šansa prodaje (heuristika, 5–95 %): kreće od 50 % i pomiče se prema
  * brzini prodaje na tržištu – koliko oglasa nestane s portala (vjerojatno prodano)
    i za koliko dana,
  * količini podataka (broj usporedivih oglasa),
  * ujednačenosti cijena (raspršene cijene = nepredvidiva prodaja),
  * sigurnosnoj zalihi – zarađuješ li i kad prodaš jeftinije,
  * sumnjivo niskoj cijeni i ručno upisanoj tržišnoj cijeni.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from afterbuy.config import Config, Search
from afterbuy.models import Deal, Listing, Reason


@dataclass
class MarketStats:
    median: float
    q1: float
    q3: float
    count: int
    manual: bool = False             # tržišna cijena ručno upisana u config
    sell_through: float | None = None  # udio oglasa koji su nestali (vjerojatno prodani)
    median_days: float | None = None   # medijan dana koliko je nestali oglas bio objavljen
    tracked: int = 0                   # koliko oglasa je praćeno za brzinu prodaje

    @property
    def dispersion(self) -> float:
        return (self.q3 - self.q1) / self.median if self.median else 0.0


@dataclass
class Activity:
    """Povijest oglasa iz baze: koliko ih je nestalo i nakon koliko dana."""

    tracked: int = 0
    gone: int = 0
    gone_days: list[float] | None = None


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
    stats = market_stats(prices, min_comparables)
    return stats.median if stats else None


MIN_TRACKED_FOR_SPEED = 5


def market_stats(prices: list[float], min_comparables: int, manual_price: float | None = None,
                 activity: Activity | None = None) -> MarketStats | None:
    clean = sorted(remove_outliers([p for p in prices if p and p > 0]))
    if len(clean) >= min_comparables:
        stats = MarketStats(median=float(statistics.median(clean)), q1=_quantile(clean, 0.25),
                            q3=_quantile(clean, 0.75), count=len(clean))
    elif manual_price:
        m = float(manual_price)
        stats = MarketStats(median=m, q1=m * 0.85, q3=m * 1.10, count=len(clean), manual=True)
    else:
        return None
    if activity and activity.tracked >= MIN_TRACKED_FOR_SPEED:
        stats.tracked = activity.tracked
        stats.sell_through = activity.gone / activity.tracked
        if activity.gone_days:
            stats.median_days = float(statistics.median(activity.gone_days))
    return stats


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


def _profit(sell: float, buy: float, cfg: Config) -> float:
    return sell * (1 - cfg.fee_percent) - cfg.fixed_cost - buy


def sell_probability(listing: Listing, stats: MarketStats, quick_profit: float, suspicious: bool,
                     cfg: Config) -> tuple[float, list[Reason]]:
    reasons: list[Reason] = []
    cur = listing.currency

    # 1) Brzina prodaje na tržištu (iz povijesti oglasa)
    if stats.sell_through is not None:
        pct = stats.sell_through * 100
        if stats.sell_through >= 0.5:
            reasons.append(Reason(20, f"Traženo: {pct:.0f} % praćenih oglasa nestalo je s portala (vjerojatno prodano)."))
        elif stats.sell_through >= 0.25:
            reasons.append(Reason(8, f"Solidna potražnja: {pct:.0f} % praćenih oglasa nestalo je s portala."))
        else:
            reasons.append(Reason(-15, f"Slaba potražnja: samo {pct:.0f} % praćenih oglasa je nestalo, većina stoji."))
        if stats.median_days is not None:
            d = stats.median_days
            if d <= 7:
                reasons.append(Reason(10, f"Slični artikli nestanu u prosjeku za ~{d:.0f} dana."))
            elif d <= 21:
                reasons.append(Reason(3, f"Slični artikli nestanu u prosjeku za ~{d:.0f} dana."))
            else:
                reasons.append(Reason(-8, f"Sporo se prodaje – oglasi stoje ~{d:.0f} dana."))
    else:
        reasons.append(Reason(0, "Brzina prodaje još nije poznata – bot skuplja povijest oglasa (par dana)."))

    # 2) Količina podataka / veličina tržišta
    if stats.manual:
        reasons.append(Reason(-10, f"Premalo usporedivih oglasa ({stats.count}) – koristi se ručno upisana cijena iz postavki."))
    elif stats.count >= 20:
        reasons.append(Reason(10, f"Veliko tržište (usporedivih oglasa: {stats.count}), procjena cijene je pouzdana."))
    elif stats.count >= 10:
        reasons.append(Reason(5, f"Dovoljno usporedivih oglasa ({stats.count}) – procjena cijene je dobra."))
    else:
        reasons.append(Reason(-5, f"Malo usporedivih oglasa ({stats.count}) – procjena je grublja."))

    # 3) Ujednačenost cijena
    disp = stats.dispersion
    if not stats.manual:
        if disp < 0.2:
            reasons.append(Reason(10, "Cijene sličnih oglasa su ujednačene – lako je pogoditi prodajnu cijenu."))
        elif disp > 0.5:
            reasons.append(Reason(-10, "Cijene sličnih oglasa jako variraju (stanje/model?) – provjeri što točno kupuješ."))

    # 4) Sigurnosna zaliha
    if quick_profit > 0:
        reasons.append(Reason(15, f"Zarađuješ i ako prodaš brzo i jeftinije (~{quick_profit:.0f} {cur})."))
    else:
        reasons.append(Reason(-10, "Za zaradu trebaš prodati po punoj cijeni – nema puno prostora za popust."))

    # 5) Rizici
    if suspicious:
        reasons.append(Reason(-25, "Cijena je sumnjivo niska – moguća prevara, kvar ili krivi model."))

    score = 50 + sum(r.points for r in reasons)
    return max(5, min(95, score)) / 100, reasons


def estimate_days_to_sell(stats: MarketStats) -> float | None:
    return stats.median_days


def build_explanation(deal: Deal, stats: MarketStats, cfg: Config) -> str:
    l = deal.listing
    cur = l.currency
    if stats.manual:
        market_txt = f"Za ovaj artikl nema dovoljno oglasa, pa koristim tvoju cijenu iz postavki ({stats.median:.0f} {cur})."
    else:
        market_txt = (f"Usporedio sam ga sa sličnim oglasima ({stats.count}): većina traži između "
                      f"{stats.q1:.0f} i {stats.q3:.0f} {cur} (medijan {stats.median:.0f} {cur}).")
    costs = []
    if cfg.fixed_cost:
        costs.append(f"trošak {cfg.fixed_cost:.0f} {cur}")
    if cfg.fee_percent:
        costs.append(f"proviziju {cfg.fee_percent * 100:.0f} %")
    cost_txt = f" (nakon što odbiješ {' i '.join(costs)})" if costs else ""
    parts = [
        f"Prodavač traži {l.price:.0f} {cur}.",
        market_txt,
        f"Realno ga možeš preprodati za ~{deal.expected_sell_price:.0f} {cur}; za brzu prodaju "
        f"~{deal.quick_sell_price:.0f} {cur}, a uz strpljenje i do ~{deal.high_sell_price:.0f} {cur}.",
        f"Zarada{cost_txt}: ~{deal.expected_profit:.0f} {cur} (+{deal.margin * 100:.0f} %), "
        f"a i kod brze prodaje ~{deal.quick_profit:.0f} {cur}.",
    ]
    if deal.est_days_to_sell is not None:
        parts.append(f"Slični oglasi obično nestanu za ~{deal.est_days_to_sell:.0f} dana.")
    parts.append(f"Šansa uspješne preprodaje: {deal.sell_probability * 100:.0f} %.")
    return " ".join(parts)


def evaluate(listing: Listing, search: Search, stats: MarketStats | float, comparables: int | None = None,
             cfg: Config | None = None) -> Deal:
    if not isinstance(stats, MarketStats):  # kompatibilnost: evaluate(l, s, cijena, broj, cfg)
        m = float(stats)
        stats = MarketStats(median=m, q1=m, q3=m, count=comparables or 0)
    assert cfg is not None

    f = cfg.sell_price_factor
    sell, quick, high = stats.median * f, min(stats.q1, stats.median) * f, max(stats.q3, stats.median) * f
    profit = _profit(sell, listing.price, cfg)
    quick_profit = _profit(quick, listing.price, cfg)
    margin = profit / listing.price if listing.price > 0 else 0.0

    notes: list[str] = []
    suspicious = listing.price < stats.median * cfg.suspicious_ratio
    if suspicious:
        notes.append("Cijena je sumnjivo niska – provjeri da nije prevara ili neispravan artikl.")
    if stats.count < cfg.min_comparables:
        notes.append("Malo usporedivih oglasa – procjena je manje pouzdana.")

    prob, reasons = sell_probability(listing, stats, quick_profit, suspicious, cfg)
    deal = Deal(
        listing=listing,
        search_name=search.name,
        market_price=round(stats.median, 2),
        expected_sell_price=round(sell, 2),
        expected_profit=round(profit, 2),
        margin=round(margin, 4),
        comparables=stats.count,
        suspicious=suspicious,
        notes=notes,
        quick_sell_price=round(quick, 2),
        high_sell_price=round(high, 2),
        quick_profit=round(quick_profit, 2),
        sell_probability=prob,
        est_days_to_sell=estimate_days_to_sell(stats),
        reasons=reasons,
    )
    deal.explanation = build_explanation(deal, stats, cfg)
    return deal
