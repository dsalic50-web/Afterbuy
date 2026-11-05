import json
from pathlib import Path

import pytest

from afterbuy.sources import get_source
from afterbuy.sources.base import parse_price
from afterbuy.sources.njuskalo import NjuskaloSource
from afterbuy.sources.olx_ba import OlxBaSource

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("text,expected", [
    ("1.299,00 KM", 1299.0), ("450 €", 450.0), ("1,299.50", 1299.5), ("1.150 KM", 1150.0),
    ("12,5", 12.5), ("Po dogovoru", None), (0, None), (199, 199.0), (None, None), ("2.5", 2.5),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_olx_parse():
    items = OlxBaSource.parse(json.loads((FIX / "olx_ba_search.json").read_text()))
    assert [i.ext_id for i in items] == ["111", "113"]
    assert items[0].price == 450 and items[0].location == "Sarajevo"
    assert items[0].url == "https://olx.ba/artikal/111"
    assert items[1].price == 1150 and items[1].image.endswith("3.jpg") and items[1].location == "Tuzla"


def test_njuskalo_parse():
    items = NjuskaloSource.parse((FIX / "njuskalo_search.html").read_text())
    assert [i.ext_id for i in items] == ["40001", "40002"]
    assert items[0].price == 390 and items[0].url.startswith("https://www.njuskalo.hr/")
    assert items[1].price == 1099.99


def test_unknown_source():
    with pytest.raises(ValueError):
        get_source("nepostojeci")
