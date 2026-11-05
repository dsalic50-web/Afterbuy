from afterbuy import bot
from afterbuy.config import Config, Search
from afterbuy.db import Database
from afterbuy.models import Listing


class FakeSource:
    def __init__(self, prices):
        self.prices = prices

    def search(self, query, min_price=None, max_price=None):
        return [Listing("fake", str(i), f"{query} {i}", p, "KM", f"https://x/{i}") for i, p in enumerate(self.prices)]


def test_run_once_finds_and_dedupes(tmp_path, monkeypatch):
    prices = [500, 520, 480, 510, 490, 505, 250, 400]
    monkeypatch.setattr(bot, "get_source", lambda name, **kw: FakeSource(prices))
    cfg = Config(searches=[Search(name="PS5", query="ps5")], sources=["fake"],
                 db_path=str(tmp_path / "t.db"), fixed_cost=0, sell_price_factor=0.9)
    db = Database(cfg.db_path)

    sent = []

    class N:
        def send(self, deals):
            sent.extend(deals)
            return deals

    res = bot.run_once(cfg, db, N())
    # medijan 497.5 * 0.9 = 447.75 -> 250 KM daje ~79 %, 400 KM samo ~12 %
    assert [d.listing.price for d in res.deals] == [250]
    assert len(sent) == 1

    res2 = bot.run_once(cfg, db, N())
    assert len(res2.deals) == 1 and res2.new_deals == []  # nema duplih obavijesti
    assert len(sent) == 1
    assert db.list_deals("novo")[0]["buy_price"] == 250


def test_source_error_does_not_crash(tmp_path, monkeypatch):
    def boom(name, **kw):
        raise RuntimeError("403")

    monkeypatch.setattr(bot, "get_source", boom)
    cfg = Config(searches=[Search(name="x", query="x")], db_path=str(tmp_path / "t.db"))
    res = bot.run_once(cfg, Database(cfg.db_path))
    assert res.errors and res.listings == 0
