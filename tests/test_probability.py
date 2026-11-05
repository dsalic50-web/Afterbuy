import sqlite3
from datetime import datetime, timedelta, timezone

from afterbuy.analysis import Activity, evaluate, market_stats
from afterbuy.config import Config, Search
from afterbuy.db import Database
from afterbuy.models import Listing
from afterbuy.notify import format_deal

CFG = Config(searches=[], sell_price_factor=0.9, fixed_cost=10)
S = Search(name="PS5", query="ps5")


def L(price, title="PS5"):
    return Listing("olx_ba", str(price), title, price, "KM", "https://x")


def test_explanation_and_price_range():
    stats = market_stats([480, 490, 500, 500, 510, 520, 505, 495, 500, 500, 498, 502], 5)
    deal = evaluate(L(250), S, stats, cfg=CFG)
    assert deal.quick_sell_price < deal.expected_sell_price < deal.high_sell_price
    assert deal.quick_profit > 0
    assert "Prodavač traži 250 KM" in deal.explanation
    assert "Šansa uspješne preprodaje" in deal.explanation
    assert any("brzo" in r.text for r in deal.reasons)


def test_fast_market_increases_chance():
    prices = [500] * 12
    slow = market_stats(prices, 5, activity=Activity(tracked=20, gone=2, gone_days=[40, 45]))
    fast = market_stats(prices, 5, activity=Activity(tracked=20, gone=14, gone_days=[3, 4, 5]))
    p_slow = evaluate(L(250), S, slow, cfg=CFG).sell_probability
    p_fast = evaluate(L(250), S, fast, cfg=CFG).sell_probability
    assert p_fast > p_slow
    assert evaluate(L(250), S, fast, cfg=CFG).est_days_to_sell == 4


def test_suspicious_and_manual_lower_chance():
    stats = market_stats([500] * 12, 5)
    normal = evaluate(L(250), S, stats, cfg=CFG).sell_probability
    scam = evaluate(L(80), S, stats, cfg=CFG)
    assert scam.suspicious and scam.sell_probability < normal
    manual = market_stats([500, 510], 5, manual_price=500)
    assert manual.manual
    assert evaluate(L(250), S, manual, cfg=CFG).sell_probability < normal
    for p in (normal, scam.sell_probability):
        assert 0.05 <= p <= 0.95


def test_market_activity_detects_gone_listings(tmp_path):
    db = Database(str(tmp_path / "a.db"))
    now = datetime.now(timezone.utc)
    iso = lambda d: (now - timedelta(days=d)).isoformat(timespec="seconds")
    # 3 dana praćenja: oglas 1 i 2 su nestali, 3 je još aktivan, 4 je nov
    for ext, first, last in [("1", 3, 2), ("2", 3, 1), ("3", 3, 0), ("4", 0, 0)]:
        db.conn.execute(
            "INSERT INTO listings VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("olx_ba", ext, "PS5", "PS5", 500, "KM", "u", "", "", iso(first), iso(last)))
    act = db.market_activity("PS5", "olx_ba", 30)
    assert act.tracked == 3 and act.gone == 2
    assert sorted(round(d) for d in act.gone_days) == [2, 3]


def test_old_database_is_migrated(tmp_path):
    path = str(tmp_path / "old.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE deals (id INTEGER PRIMARY KEY, source TEXT, ext_id TEXT, search_name TEXT)")
    con.commit()
    con.close()
    db = Database(path)
    cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(deals)")}
    assert {"sell_probability", "explanation", "reasons"} <= cols


def test_telegram_message_contains_chance():
    stats = market_stats([500] * 12, 5)
    msg = format_deal(evaluate(L(250), S, stats, cfg=CFG), as_html=True)
    assert "Šansa prodaje" in msg and "Preprodaja" in msg and "Zašto takva šansa" in msg
