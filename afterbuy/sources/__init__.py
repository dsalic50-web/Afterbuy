from __future__ import annotations

from afterbuy.sources.base import Source
from afterbuy.sources.demo import DemoSource
from afterbuy.sources.njuskalo import NjuskaloSource
from afterbuy.sources.olx_ba import OlxBaSource

REGISTRY: dict[str, type[Source]] = {
    OlxBaSource.name: OlxBaSource,
    NjuskaloSource.name: NjuskaloSource,
    DemoSource.name: DemoSource,
}


def get_source(name: str, **kwargs) -> Source:
    try:
        return REGISTRY[name](**kwargs)
    except KeyError:
        raise ValueError(f"Nepoznat izvor '{name}'. Dostupni: {', '.join(REGISTRY)}") from None
