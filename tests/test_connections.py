import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.common import redis_client
from app.common.config import get_settings
from app.common.events import PriceReading
from app.common.kafka import make_consumer, make_producer, publish

TEST_LISTING_ID = -1
TEST_SELLER_ID = -1
TEST_PRODUCT_ID = -1


def test_last_price_round_trip():
    client = redis_client.get_client()
    client.delete(f"price:last:{TEST_LISTING_ID}")

    assert redis_client.get_last_price(TEST_LISTING_ID) is None

    redis_client.set_last_price(TEST_LISTING_ID, Decimal("1499.00"), True, datetime.now(UTC))
    last = redis_client.get_last_price(TEST_LISTING_ID)

    assert last == redis_client.LastPrice(Decimal("1499.00"), True)
    client.delete(f"price:last:{TEST_LISTING_ID}")


def test_lock_is_taken_once():
    client = redis_client.get_client()
    client.delete(f"lock:collect:{TEST_LISTING_ID}")

    assert redis_client.try_lock(TEST_LISTING_ID) is True
    assert redis_client.try_lock(TEST_LISTING_ID) is False
    client.delete(f"lock:collect:{TEST_LISTING_ID}")


def test_cooldown_blocks_second_alert():
    client = redis_client.get_client()
    key = f"cooldown:{TEST_SELLER_ID}:{TEST_PRODUCT_ID}:LARGE_JUMP"
    client.delete(key)

    assert redis_client.try_cooldown(TEST_SELLER_ID, TEST_PRODUCT_ID, "LARGE_JUMP") is True
    assert redis_client.try_cooldown(TEST_SELLER_ID, TEST_PRODUCT_ID, "LARGE_JUMP") is False
    client.delete(key)


def test_rate_limit_trips_after_limit():
    marketplace = f"test-{uuid.uuid4().hex}"
    limit = get_settings().rate_limit_per_minute

    results = [redis_client.within_rate_limit(marketplace) for _ in range(limit + 1)]

    assert all(results[:limit])
    assert results[limit] is False


def test_kafka_publish_and_consume():
    topic = f"test.{uuid.uuid4().hex}"
    reading = PriceReading(
        listing_id=42,
        marketplace="fake",
        price=Decimal("1499.00"),
        in_stock=True,
        observed_at=datetime.now(UTC),
    )

    producer = make_producer()
    publish(producer, topic, reading)
    producer.flush(10)

    consumer = make_consumer(f"test-{uuid.uuid4().hex}")
    consumer.subscribe([topic])
    try:
        message = None
        for _ in range(30):
            message = consumer.poll(1.0)
            if message is not None and message.error() is None:
                break
        assert message is not None and message.error() is None
        assert message.key() == b"42"
        assert PriceReading.from_bytes(message.value()) == reading
    finally:
        consumer.close()
