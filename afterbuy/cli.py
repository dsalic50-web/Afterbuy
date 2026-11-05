from __future__ import annotations

import argparse
import logging
import threading

from afterbuy.bot import run_once
from afterbuy.config import load_config
from afterbuy.db import Database
from afterbuy.notify import Notifier
from afterbuy.scheduler import run_daily


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="afterbuy", description="Bot za pronalazak oglasa za preprodaju.")
    parser.add_argument("-c", "--config", default="config.yaml", help="putanja do config.yaml")
    parser.add_argument("--demo", action="store_true", help="koristi lažne oglase (za isprobavanje bez interneta)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="jedna pretraga odmah")
    sub.add_parser("schedule", help="pretraga svaki dan u 'run_at'")
    p_serve = sub.add_parser("serve", help="web nadzorna ploča + dnevna pretraga")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=5000)
    p_serve.add_argument("--no-schedule", action="store_true", help="bez automatske dnevne pretrage")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    override = ["demo"] if args.demo else None
    if args.demo and cfg.db_path == "afterbuy.db":
        cfg.db_path = "afterbuy-demo.db"

    def job():
        db = Database(cfg.db_path)
        try:
            return run_once(cfg, db, Notifier(cfg.telegram), override)
        finally:
            db.close()

    if args.cmd == "run":
        res = job()
        print(f"\nPronađeno {len(res.deals)} prilika ({len(res.new_deals)} novih) u {res.listings} oglasa.")
        return 1 if res.errors and not res.listings else 0
    if args.cmd == "schedule":
        run_daily(cfg.run_at, job)
        return 0
    if args.cmd == "serve":
        from afterbuy.web import create_app

        app = create_app(cfg, override)
        if not args.no_schedule:
            lock = app.config["RUN_LOCK"]

            def locked_job():
                with lock:
                    job()

            threading.Thread(target=run_daily, args=(cfg.run_at, locked_job), daemon=True).start()
        app.run(host=args.host, port=args.port)
        return 0
    return 2
