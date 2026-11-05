from __future__ import annotations

import html
import logging

import requests

from afterbuy.config import TelegramConfig
from afterbuy.models import Deal

log = logging.getLogger(__name__)


def format_deal(deal: Deal, as_html: bool = False) -> str:
    l = deal.listing
    esc = html.escape if as_html else (lambda s: s)
    lines = [
        f"{'⚠️ ' if deal.suspicious else '🔥 '}{esc(l.title)}",
        f"Pretraga: {esc(deal.search_name)} · {l.source}" + (f" · {esc(l.location)}" if l.location else ""),
        f"Cijena: {l.price:.0f} {l.currency} → prodaja ~{deal.expected_sell_price:.0f} {l.currency}",
        f"Zarada: ~{deal.expected_profit:.0f} {l.currency} (+{deal.margin * 100:.0f} %)",
        f"Tržišna cijena (medijan {deal.comparables} oglasa): {deal.market_price:.0f} {l.currency}",
    ]
    lines += [esc(n) for n in deal.notes]
    lines.append(l.url)
    return "\n".join(lines)


class Notifier:
    def __init__(self, telegram: TelegramConfig):
        self.telegram = telegram

    def send(self, deals: list[Deal]) -> list[Deal]:
        """Šalje obavijesti; vraća prilike za koje je slanje uspjelo."""
        sent: list[Deal] = []
        for deal in deals:
            print("\n" + format_deal(deal))
            if not self.telegram.enabled:
                sent.append(deal)
                continue
            try:
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.telegram.bot_token}/sendMessage",
                    json={
                        "chat_id": self.telegram.chat_id,
                        "text": format_deal(deal, as_html=True),
                        "parse_mode": "HTML",
                        "disable_web_page_preview": False,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                sent.append(deal)
            except requests.RequestException as exc:
                log.error("Telegram obavijest nije poslana: %s", exc)
        return sent
