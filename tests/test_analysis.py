from afterbuy.analysis import estimate_market_price, evaluate, matches_search, remove_outliers
from afterbuy.config import Config, Search
from afterbuy.models import Listing


def L(title, price, desc=""):
    return Listing("demo", title, title, price, "KM", "u", description=desc)


def test_outliers_removed():
    assert 5000 not in remove_outliers([500, 520, 480, 510, 5000, 490])


def test_market_price_needs_enough_comparables():
    assert estimate_market_price([500, 510], 5) is None
    assert estimate_market_price([500, 510, 490, 505, 495, 20], 5) == 500


def test_matching():
    s = Search(name="x", query="iphone 13", must_include=["iphone 13", "128|256"], exclude=["pro"],
               min_price=100)
    ex = ["neispravan"]
    assert matches_search(L("iPhone 13 128GB", 400), s, ex)
    assert not matches_search(L("iPhone 13 Pro 128GB", 400), s, ex)
    assert not matches_search(L("iPhone 13 64GB", 400), s, ex)
    assert not matches_search(L("iPhone 13 128GB", 50), s, ex)
    assert not matches_search(L("iPhone 13 128GB", 400, "neispravan ekran"), s, ex)


def test_margin():
    cfg = Config(searches=[], sell_price_factor=0.9, fixed_cost=10, fee_percent=0.0)
    s = Search(name="x", query="x")
    deal = evaluate(L("a", 250), s, 500, 10, cfg)
    # prodaja 450 - 10 trošak - 250 = 190 profita -> 76 %
    assert deal.expected_profit == 190
    assert deal.margin == 0.76
    assert not deal.suspicious
    assert evaluate(L("b", 100), s, 500, 10, cfg).suspicious
