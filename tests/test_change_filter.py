import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.change_filter.main import process
from app.common import redis_client
from app.common.events import PriceChange, PriceReading
from app.common.kafka import make_producer
from tests.helpers import read_events

TEST_LISTING_ID = -7


@pytest.fixture(autouse=True)
def clean_last_price():
    key = f"price:last:{TEST_LISTING_ID}"
    redis_client.get_client().delete(key)
    yield
    redis_client.get_client().delete(key)


def reading(price: str, in_stock: bool = True) -> PriceReading:
    return PriceReading(
        listing_id=TEST_LISTING_ID,
        marketplace="fake",
        price=Decimal(price),
        in_stock=in_stock,
        observed_at=datetime.now(UTC),
    )


def test_only_real_changes_pass():
    topic = f"test.{uuid.uuid4().hex}"
    producer = make_producer()

    assert process(reading("1000.00"), producer, topic) is True
    assert process(reading("1000.00"), producer, topic) is False
    assert process(reading("1000"), producer, topic) is False
    assert process(reading("950.00"), producer, topic) is True
    assert process(reading("950.00", in_stock=False), producer, topic) is True
    assert process(reading("950.00", in_stock=False), producer, topic) is False

    changes = read_events(topic, PriceChange, 3)

    assert [(c.price, c.in_stock, c.previous_price, c.previous_in_stock) for c in changes] == [
        (Decimal("1000.00"), True, None, None),
        (Decimal("950.00"), True, Decimal("1000.00"), True),
        (Decimal("950.00"), False, Decimal("950.00"), True),
    ]
