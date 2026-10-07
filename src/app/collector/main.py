import logging
import time
from datetime import UTC, datetime

import httpx
import oracledb
from confluent_kafka import Producer

from app.common import redis_client
from app.common.config import get_settings
from app.common.db import connect
from app.common.events import PriceReading
from app.common.kafka import make_producer, publish
from app.marketplaces import get_marketplace
from app.marketplaces.base import ListingNotFound, Marketplace

logger = logging.getLogger(__name__)

SELECT_DUE = """
SELECT id, sku
  FROM listings
 WHERE active = 1
   AND marketplace = :marketplace
   AND next_check_at <= SYS_EXTRACT_UTC(SYSTIMESTAMP)
 ORDER BY next_check_at
"""

SCHEDULE_NEXT = """
UPDATE listings
   SET next_check_at = SYS_EXTRACT_UTC(SYSTIMESTAMP) + NUMTODSINTERVAL(check_interval_seconds, 'SECOND')
 WHERE id = :id
"""


def collect_once(
    connection: oracledb.Connection, producer: Producer, marketplace: Marketplace, topic: str
) -> int:
    published = 0
    with connection.cursor() as cursor:
        cursor.execute(SELECT_DUE, marketplace=marketplace.name)
        due = cursor.fetchall()

        for listing_id, sku in due:
            if not redis_client.within_rate_limit(marketplace.name):
                logger.warning("Rate limit reached for %s, the rest waits for the next round", marketplace.name)
                break
            if not redis_client.try_lock(listing_id):
                continue

            try:
                snapshot = marketplace.fetch_listing(sku)
            except ListingNotFound:
                logger.warning("Listing %s (%s) no longer exists on %s", listing_id, sku, marketplace.name)
                snapshot = None
            except httpx.HTTPError as error:
                logger.error("Could not fetch listing %s (%s): %s", listing_id, sku, error)
                continue

            if snapshot is not None:
                reading = PriceReading(
                    listing_id=listing_id,
                    marketplace=marketplace.name,
                    price=snapshot.price,
                    in_stock=snapshot.in_stock,
                    observed_at=datetime.now(UTC),
                )
                publish(producer, topic, reading)
                published += 1

            cursor.execute(SCHEDULE_NEXT, id=listing_id)
            connection.commit()

    producer.flush()
    return published


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    marketplace = get_marketplace()
    producer = make_producer()

    logger.info("Collector started, checking every %d seconds", settings.collect_interval_seconds)
    with connect() as connection:
        try:
            while True:
                published = collect_once(connection, producer, marketplace, settings.kafka_topic_readings)
                logger.info("Published %d readings", published)
                time.sleep(settings.collect_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Collector stopped")


if __name__ == "__main__":
    main()
