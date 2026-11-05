from __future__ import annotations

import logging
from dataclasses import dataclass, field

from afterbuy.analysis import evaluate, market_stats, matches_search
from afterbuy.config import Config
from afterbuy.db import Database, now_iso
from afterbuy.models import Deal, Listing
from afterbuy.notify import Notifier
from afterbuy.sources import get_source

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    listings: int = 0
    deals: list[Deal] = field(default_factory=list)
    new_deals: list[Deal] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_once(cfg: Config, db: Database, notifier: Notifier | None = None,
             source_override: list[str] | None = None) -> RunResult:
    """Jedan prolaz bota: skupi oglase, procijeni tržišnu cijenu, pronađi prilike, javi nove."""
    result = RunResult()
    run_id = db.start_run()
    sources_cache: dict = {}

    for search in cfg.searches:
        source_names = source_override or search.sources or cfg.sources
        for source_name in source_names:
            try:
                src = sources_cache.get(source_name) or get_source(
                    source_name, request_delay=cfg.request_delay, max_pages=cfg.max_pages)
                sources_cache[source_name] = src
                raw = src.search(search.query, search.min_price, search.max_price)
            except Exception as exc:  # jedan neispravan izvor ne smije srušiti cijeli prolaz
                msg = f"{source_name} / {search.name}: {exc}"
                log.error(msg)
                result.errors.append(msg)
                continue

            ts = now_iso()
            matched: list[Listing] = [l for l in raw if matches_search(l, search, cfg.exclude_words)]
            for l in matched:
                db.upsert_listing(l, search.name, ts)
            db.conn.commit()
            result.listings += len(matched)

            prices = db.comparable_prices(search.name, source_name, cfg.history_days)
            activity = db.market_activity(search.name, source_name, cfg.history_days)
            stats = market_stats(prices, cfg.min_comparables, search.market_price, activity)
            if stats is None:
                log.info("%s / %s: premalo usporedivih oglasa (%d) za procjenu cijene",
                         source_name, search.name, len(prices))
                continue

            for l in matched:
                deal = evaluate(l, search, stats, cfg=cfg)
                if deal.margin >= cfg.min_margin and deal.sell_probability >= cfg.min_sell_probability:
                    result.deals.append(deal)
                    if db.upsert_deal(deal):
                        result.new_deals.append(deal)
            db.conn.commit()

    if notifier and result.new_deals:
        for deal in notifier.send(sorted(result.new_deals, key=lambda d: (d.sell_probability, d.margin), reverse=True)):
            db.mark_notified(deal)

    db.finish_run(run_id, result.listings, len(result.deals), len(result.new_deals), result.errors)
    log.info("Gotovo: %d oglasa, %d prilika (%d novih), %d grešaka",
             result.listings, len(result.deals), len(result.new_deals), len(result.errors))
    return result
