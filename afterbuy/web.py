from __future__ import annotations

import json
import logging
import threading

from flask import Flask, flash, g, redirect, render_template, request, url_for

from afterbuy.bot import run_once
from afterbuy.config import Config
from afterbuy.db import STATUSES, Database
from afterbuy.notify import Notifier

log = logging.getLogger(__name__)


def create_app(cfg: Config, source_override: list[str] | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = "afterbuy-local"
    run_lock = threading.Lock()

    def get_db() -> Database:
        if "db" not in g:
            g.db = Database(cfg.db_path)
        return g.db

    @app.teardown_appcontext
    def _close(_exc):
        db = g.pop("db", None)
        if db:
            db.close()

    @app.template_filter("pct")
    def pct(v):
        return f"{v * 100:.0f} %"

    @app.template_filter("money")
    def money(v):
        return "–" if v is None else f"{v:,.0f}".replace(",", ".")

    @app.template_filter("reasons")
    def reasons(raw):
        try:
            return json.loads(raw or "[]")
        except ValueError:
            return []

    @app.template_filter("chance_class")
    def chance_class(p):
        if p is None:
            return "mid"
        return "high" if p >= 0.75 else ("mid" if p >= 0.5 else "low")

    @app.get("/")
    def index():
        status = request.args.get("status", "novo")
        search = request.args.get("search") or None
        db = get_db()
        deals = db.list_deals(None if status == "sve" else status, search)
        sort = request.args.get("sort", "margin")
        if sort == "margin":
            deals = sorted(deals, key=lambda d: d["margin"], reverse=True)
        elif sort == "profit":
            deals = sorted(deals, key=lambda d: d["expected_profit"], reverse=True)
        elif sort == "chance":
            deals = sorted(deals, key=lambda d: (d["sell_probability"] or 0, d["margin"]), reverse=True)
        return render_template(
            "index.html", deals=deals, status=status, statuses=STATUSES, search=search, sort=sort,
            searches=[s.name for s in cfg.searches], runs=db.last_runs(5), summary=db.profit_summary(),
            cfg=cfg, running=run_lock.locked(),
        )

    @app.post("/deal/<int:deal_id>")
    def update_deal(deal_id: int):
        def num(name):
            v = (request.form.get(name) or "").replace(",", ".").strip()
            return float(v) if v else None

        try:
            get_db().update_deal_status(deal_id, request.form["status"], num("bought_price"), num("sold_price"))
        except ValueError as exc:
            flash(str(exc))
        return redirect(request.referrer or url_for("index"))

    @app.post("/run")
    def run_now():
        if run_lock.locked():
            flash("Pretraga je već u tijeku.")
            return redirect(url_for("index"))

        def job():
            with run_lock:
                db = Database(cfg.db_path)
                try:
                    run_once(cfg, db, Notifier(cfg.telegram), source_override)
                finally:
                    db.close()

        threading.Thread(target=job, daemon=True).start()
        flash("Pretraga pokrenuta – osvježi stranicu za minutu-dvije.")
        return redirect(url_for("index"))

    app.config["RUN_LOCK"] = run_lock
    return app
