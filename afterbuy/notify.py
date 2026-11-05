from __future__ import annotations

import html
import logging

import requests

from afterbuy.config import TelegramConfig
from afterbuy.models import Deal

log = logging.getLogger(__name__)


def probability_label(p: float) -> str:
    if p >= 0.75:
        return "🟢 visoka"
    if p >= 0.5:
        return "🟡 srednja"
    return "🔴 niska"


def format_deal(deal: Deal, as_html: bool = False) -> str:
    l = deal.listing
    esc = html.escape if as_html else (lambda s: s)
    b = (lambda s: f"<b>{s}</b>") if as_html else (lambda s: s)
    cur = l.currency
    lines = [
        b(f"{'⚠️ ' if deal.suspicious else '🔥 '}{esc(l.title)}"),
        f"{esc(deal.search_name)} · {l.source}" + (f" · {esc(l.location)}" if l.location else ""),
        "",
        f"💰 Cijena oglasa: {l.price:.0f} {cur}",
        f"📈 Preprodaja: ~{deal.expected_sell_price:.0f} {cur} "
        f"(brzo ~{deal.quick_sell_price:.0f}, uz strpljenje ~{deal.high_sell_price:.0f})",
        f"✅ Zarada: ~{deal.expected_profit:.0f} {cur} (+{deal.margin * 100:.0f} %)",
        b(f"🎯 Šansa prodaje: {deal.sell_probability * 100:.0f} % ({probability_label(deal.sell_probability)})"),
    ]
    if deal.est_days_to_sell is not None:
        lines.append(f"⏱ Prodaja za ~{deal.est_days_to_sell:.0f} dana")
    if deal.explanation:
        lines += ["", esc(deal.explanation)]
    if deal.reasons:
        lines += ["", "Zašto takva šansa:"] + [esc(str(r)) for r in deal.reasons]
    lines += [esc(n) for n in deal.notes if "sumnjivo" not in n.lower()]
    lines += ["", l.url]
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
