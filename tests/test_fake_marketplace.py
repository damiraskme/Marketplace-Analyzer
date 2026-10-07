from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.common.db import connect
from app.marketplaces.base import ListingNotFound
from app.marketplaces.fake import FakeMarketplace
from fake_marketplace.main import ITEMS, OWN_SHOP, app, change_random_competitor


@pytest.fixture
def marketplace():
    return FakeMarketplace("http://testserver", client=TestClient(app))


def test_fetch_listing(marketplace):
    snapshot = marketplace.fetch_listing("OWN-1001")

    assert snapshot.title == "Wireless Earbuds X1"
    assert isinstance(snapshot.price, Decimal)


def test_unknown_sku_raises(marketplace):
    with pytest.raises(ListingNotFound):
        marketplace.fetch_listing("NOPE")


def test_fetch_own_products(marketplace):
    products = marketplace.fetch_own_products(OWN_SHOP)

    assert sorted(p.sku for p in products) == ["OWN-1001", "OWN-1002", "OWN-1003"]


def test_update_price_is_visible_on_next_fetch(marketplace):
    original = marketplace.fetch_listing("OWN-1002").price

    marketplace.update_price("OWN-1002", Decimal("1790.00"))

    assert marketplace.fetch_listing("OWN-1002").price == Decimal("1790.00")
    marketplace.update_price("OWN-1002", original)


def test_random_change_touches_only_competitors():
    own_before = {sku: item.model_copy() for sku, item in ITEMS.items() if item.shop == OWN_SHOP}

    for _ in range(200):
        before = {sku: item.model_copy() for sku, item in ITEMS.items()}
        changed = change_random_competitor()
        assert changed != before[changed.sku]
        assert changed.price > 0

    assert {sku: ITEMS[sku] for sku in own_before} == own_before


def test_catalog_matches_seeded_listings():
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT sku, title FROM listings WHERE marketplace = 'fake'")
        seeded = dict(cursor.fetchall())

    assert seeded == {sku: item.title for sku, item in ITEMS.items()}
