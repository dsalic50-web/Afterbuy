from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_EXCLUDE = [
    "kupujem", "tražim", "trazim", "zamjena", "mijenjam", "neispravan", "neispravno",
    "za dijelove", "dijelovi", "oštećen", "ostecen", "razbijen", "blokiran",
    "icloud lock", "samo kutija", "kutija od", "maska", "futrola", "replika", "kopija",
]


@dataclass
class Search:
    name: str
    query: str
    must_include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    sources: list[str] | None = None
    # Ručno postavljena prodajna (tržišna) cijena – koristi se ako nema dovoljno usporedivih oglasa.
    market_price: float | None = None


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass
class Config:
    searches: list[Search]
    min_margin: float = 0.60
    run_at: str = "08:00"
    history_days: int = 30
    min_comparables: int = 5
    sell_price_factor: float = 0.90
    fee_percent: float = 0.0
    fixed_cost: float = 0.0
    suspicious_ratio: float = 0.25
    max_pages: int = 3
    request_delay: float = 2.0
    sources: list[str] = field(default_factory=lambda: ["olx_ba"])
    exclude_words: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    db_path: str = "afterbuy.db"
    telegram: TelegramConfig = field(default_factory=TelegramConfig)


def _search_from_dict(d: dict) -> Search:
    if "query" not in d:
        raise ValueError(f"Pretraga mora imati 'query': {d}")
    return Search(
        name=str(d.get("name") or d["query"]),
        query=str(d["query"]),
        must_include=[str(x).lower() for x in d.get("must_include", [])],
        exclude=[str(x).lower() for x in d.get("exclude", [])],
        min_price=d.get("min_price"),
        max_price=d.get("max_price"),
        sources=d.get("sources"),
        market_price=d.get("market_price"),
    )


def load_config(path: str | os.PathLike) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    searches = [_search_from_dict(s) for s in data.get("searches", [])]
    if not searches:
        raise ValueError("Konfiguracija nema nijednu pretragu ('searches').")

    tg = data.get("notify", {}).get("telegram", {}) or {}
    telegram = TelegramConfig(
        bot_token=os.environ.get("AFTERBUY_TELEGRAM_TOKEN", tg.get("bot_token", "")) or "",
        chat_id=str(os.environ.get("AFTERBUY_TELEGRAM_CHAT_ID", tg.get("chat_id", "")) or ""),
    )

    cfg = Config(searches=searches, telegram=telegram)
    for key in (
        "min_margin", "run_at", "history_days", "min_comparables", "sell_price_factor",
        "fee_percent", "fixed_cost", "suspicious_ratio", "max_pages", "request_delay",
        "sources", "db_path",
    ):
        if key in data:
            setattr(cfg, key, data[key])
    if "exclude_words" in data:
        cfg.exclude_words = [str(x).lower() for x in data["exclude_words"]]
    cfg.run_at = str(cfg.run_at)
    return cfg
