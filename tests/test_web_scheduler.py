from datetime import datetime

from afterbuy.config import Config, Search
from afterbuy.db import Database
from afterbuy.models import Deal, Listing
from afterbuy.scheduler import next_run_time
from afterbuy.web import create_app


def test_next_run_time():
    now = datetime(2026, 11, 5, 9, 0)
    assert next_run_time("08:00", now) == datetime(2026, 11, 6, 8, 0)
    assert next_run_time("10:30", now) == datetime(2026, 11, 5, 10, 30)


def test_dashboard_and_status_update(tmp_path):
    cfg = Config(searches=[Search(name="PS5", query="ps5")], db_path=str(tmp_path / "w.db"))
    db = Database(cfg.db_path)
    l = Listing("demo", "1", "PS5 disk", 300, "KM", "https://x/1")
    db.upsert_deal(Deal(l, "PS5", 600, 540, 240, 0.8, 9))
    db.conn.commit()
    client = create_app(cfg).test_client()
    html = client.get("/").get_data(as_text=True)
    assert "PS5 disk" in html and "+80 %" in html
    deal_id = db.list_deals()[0]["id"]
    client.post(f"/deal/{deal_id}", data={"status": "prodano", "bought_price": "300", "sold_price": "550"})
    assert db.profit_summary()["profit"] == 250
