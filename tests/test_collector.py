import uuid

import pytest
from fastapi.testclient import TestClient

from app.collector.main import collect_once
from app.common import redis_client
from app.common.db import connect
from app.common.events import PriceReading
from app.common.kafka import make_producer
from app.marketplaces.fake import FakeMarketplace
from fake_marketplace.main import ITEMS, app
from tests.helpers import read_events


@pytest.fixture
def connection():
    with connect() as connection:
        yield connection


@pytest.fixture
def marketplace():
    return FakeMarketplace("http://testserver", client=TestClient(app))


def make_all_due(connection) -> list[int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE listings SET next_check_at = SYS_EXTRACT_UTC(SYSTIMESTAMP) - INTERVAL '1' SECOND"
        )
        cursor.execute("SELECT id FROM listings")
        ids = [row[0] for row in cursor]
    connection.commit()
    return ids


def clear_redis(listing_ids: list[int]) -> None:
    client = redis_client.get_client()
    for listing_id in listing_ids:
        client.delete(f"lock:collect:{listing_id}")
    for key in client.scan_iter("ratelimit:fake:*"):
        client.delete(key)


def test_collects_every_due_listing_once(connection, marketplace):
    topic = f"test.{uuid.uuid4().hex}"
    listing_ids = make_all_due(connection)
    clear_redis(listing_ids)
    producer = make_producer()

    assert collect_once(connection, producer, marketplace, topic) == len(ITEMS)
    assert collect_once(connection, producer, marketplace, topic) == 0

    readings = read_events(topic, PriceReading, len(ITEMS))
    assert sorted(r.listing_id for r in readings) == sorted(listing_ids)
    assert all(r.marketplace == "fake" for r in readings)


def test_locked_listings_are_skipped(connection, marketplace):
    topic = f"test.{uuid.uuid4().hex}"
    listing_ids = make_all_due(connection)
    clear_redis(listing_ids)
    for listing_id in listing_ids:
        assert redis_client.try_lock(listing_id)

    assert collect_once(connection, make_producer(), marketplace, topic) == 0

    clear_redis(listing_ids)
