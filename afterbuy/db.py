from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from afterbuy.analysis import Activity
from afterbuy.models import Deal, Listing

# Stupci dodani nakon prve verzije – dodaju se automatski u postojeću bazu.
DEAL_EXTRA_COLUMNS = {
    "quick_sell_price": "REAL",
    "high_sell_price": "REAL",
    "quick_profit": "REAL",
    "sell_probability": "REAL",
    "est_days_to_sell": "REAL",
    "reasons": "TEXT DEFAULT '[]'",
    "explanation": "TEXT DEFAULT ''",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    source TEXT NOT NULL,
    ext_id TEXT NOT NULL,
    search_name TEXT NOT NULL,
    title TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    url TEXT NOT NULL,
    location TEXT DEFAULT '',
    image TEXT DEFAULT '',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (source, ext_id, search_name)
);
CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    ext_id TEXT NOT NULL,
    search_name TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    image TEXT DEFAULT '',
    location TEXT DEFAULT '',
    currency TEXT NOT NULL,
    buy_price REAL NOT NULL,
    market_price REAL NOT NULL,
    expected_sell_price REAL NOT NULL,
    expected_profit REAL NOT NULL,
    margin REAL NOT NULL,
    comparables INTEGER NOT NULL,
    suspicious INTEGER NOT NULL DEFAULT 0,
    found_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'novo',
    bought_price REAL,
    sold_price REAL,
    notified INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source, ext_id, search_name)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    listings INTEGER DEFAULT 0,
    deals INTEGER DEFAULT 0,
    new_deals INTEGER DEFAULT 0,
    errors TEXT DEFAULT ''
);
"""

STATUSES = ("novo", "kupljeno", "prodano", "ignorirano")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        existing = {r["name"] for r in self.conn.execute("PRAGMA table_info(deals)")}
        for col, typ in DEAL_EXTRA_COLUMNS.items():
            if col not in existing:
                self.conn.execute(f"ALTER TABLE deals ADD COLUMN {col} {typ}")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- oglasi -----------------------------------------------------------
    def upsert_listing(self, listing: Listing, search_name: str, seen_at: str | None = None) -> None:
        ts = seen_at or now_iso()
        self.conn.execute(
            """
            INSERT INTO listings (source, ext_id, search_name, title, price, currency, url, location, image,
                                  first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, ext_id, search_name) DO UPDATE SET
                title=excluded.title, price=excluded.price, url=excluded.url,
                location=excluded.location, image=excluded.image, last_seen=excluded.last_seen
            """,
            (listing.source, listing.ext_id, search_name, listing.title, listing.price, listing.currency,
             listing.url, listing.location, listing.image, ts, ts),
        )

    def comparable_prices(self, search_name: str, source: str, days: int) -> list[float]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        rows = self.conn.execute(
            "SELECT price FROM listings WHERE search_name=? AND source=? AND last_seen>=?",
            (search_name, source, cutoff),
        ).fetchall()
        return [r["price"] for r in rows]

    def market_activity(self, search_name: str, source: str, days: int) -> Activity:
        """Koliko je praćenih oglasa nestalo s portala (vjerojatno prodano) i nakon koliko dana.

        Oglas je "praćen" ako je viđen prije zadnjeg pretraživanja, a "nestao" ako ga zadnje
        pretraživanje više nije našlo.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        rows = self.conn.execute(
            "SELECT first_seen, last_seen FROM listings WHERE search_name=? AND source=? AND last_seen>=?",
            (search_name, source, cutoff),
        ).fetchall()
        if not rows:
            return Activity()
        latest = max(datetime.fromisoformat(r["last_seen"]) for r in rows)
        margin = timedelta(hours=1)
        tracked = gone = 0
        gone_days: list[float] = []
        for r in rows:
            first, last = datetime.fromisoformat(r["first_seen"]), datetime.fromisoformat(r["last_seen"])
            if first >= latest - margin:
                continue  # prvi put viđen u zadnjoj pretrazi – još ne znamo ništa
            tracked += 1
            if last < latest - margin:
                gone += 1
                # nestao između zadnjeg viđenja i sljedeće pretrage (~1 dan)
                gone_days.append((last - first).total_seconds() / 86400 + 1)
        return Activity(tracked=tracked, gone=gone, gone_days=gone_days)

    # --- prilike ----------------------------------------------------------
    def upsert_deal(self, deal: Deal) -> bool:
        """Spremi priliku. Vraća True ako je nova (još nije poslana obavijest)."""
        l = deal.listing
        ts = now_iso()
        self.conn.execute(
            """
            INSERT INTO deals (source, ext_id, search_name, title, url, image, location, currency, buy_price,
                               market_price, expected_sell_price, expected_profit, margin, comparables,
                               suspicious, found_at, updated_at, quick_sell_price, high_sell_price,
                               quick_profit, sell_probability, est_days_to_sell, reasons, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, ext_id, search_name) DO UPDATE SET
                title=excluded.title, buy_price=excluded.buy_price, market_price=excluded.market_price,
                expected_sell_price=excluded.expected_sell_price, expected_profit=excluded.expected_profit,
                margin=excluded.margin, comparables=excluded.comparables, suspicious=excluded.suspicious,
                updated_at=excluded.updated_at, quick_sell_price=excluded.quick_sell_price,
                high_sell_price=excluded.high_sell_price, quick_profit=excluded.quick_profit,
                sell_probability=excluded.sell_probability, est_days_to_sell=excluded.est_days_to_sell,
                reasons=excluded.reasons, explanation=excluded.explanation
            """,
            (l.source, l.ext_id, deal.search_name, l.title, l.url, l.image, l.location, l.currency, l.price,
             deal.market_price, deal.expected_sell_price, deal.expected_profit, deal.margin,
             deal.comparables, int(deal.suspicious), ts, ts, deal.quick_sell_price, deal.high_sell_price,
             deal.quick_profit, deal.sell_probability, deal.est_days_to_sell,
             json.dumps([{"points": r.points, "text": r.text} for r in deal.reasons], ensure_ascii=False),
             deal.explanation),
        )
        row = self.conn.execute(
            "SELECT notified FROM deals WHERE source=? AND ext_id=? AND search_name=?",
            (l.source, l.ext_id, deal.search_name),
        ).fetchone()
        return not row["notified"]

    def mark_notified(self, deal: Deal) -> None:
        l = deal.listing
        self.conn.execute(
            "UPDATE deals SET notified=1 WHERE source=? AND ext_id=? AND search_name=?",
            (l.source, l.ext_id, deal.search_name),
        )
        self.conn.commit()

    def list_deals(self, status: str | None = None, search_name: str | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM deals WHERE 1=1"
        args: list = []
        if status:
            q += " AND status=?"
            args.append(status)
        if search_name:
            q += " AND search_name=?"
            args.append(search_name)
        q += " ORDER BY found_at DESC, margin DESC"
        return self.conn.execute(q, args).fetchall()

    def update_deal_status(self, deal_id: int, status: str, bought_price: float | None = None,
                           sold_price: float | None = None) -> None:
        if status not in STATUSES:
            raise ValueError(f"Nepoznat status: {status}")
        self.conn.execute(
            """UPDATE deals SET status=?, bought_price=COALESCE(?, bought_price),
               sold_price=COALESCE(?, sold_price), updated_at=? WHERE id=?""",
            (status, bought_price, sold_price, now_iso(), deal_id),
        )
        self.conn.commit()

    def profit_summary(self) -> dict:
        row = self.conn.execute(
            """SELECT COUNT(*) AS n, COALESCE(SUM(sold_price - COALESCE(bought_price, buy_price)), 0) AS profit,
                      COALESCE(SUM(COALESCE(bought_price, buy_price)), 0) AS invested
               FROM deals WHERE status='prodano' AND sold_price IS NOT NULL"""
        ).fetchone()
        return dict(row)

    # --- pokretanja -------------------------------------------------------
    def start_run(self) -> int:
        cur = self.conn.execute("INSERT INTO runs (started_at) VALUES (?)", (now_iso(),))
        self.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, listings: int, deals: int, new_deals: int, errors: list[str]) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, listings=?, deals=?, new_deals=?, errors=? WHERE id=?",
            (now_iso(), listings, deals, new_deals, "\n".join(errors), run_id),
        )
        self.conn.commit()

    def last_runs(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
