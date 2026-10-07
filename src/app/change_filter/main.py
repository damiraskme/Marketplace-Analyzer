import logging

from confluent_kafka import Producer

from app.common import redis_client
from app.common.config import get_settings
from app.common.events import PriceChange, PriceReading
from app.common.kafka import make_producer, publish, run_consumer

logger = logging.getLogger(__name__)

GROUP_ID = "change-filter"


def process(reading: PriceReading, producer: Producer, topic: str) -> bool:
    last = redis_client.get_last_price(reading.listing_id)
    if last is not None and last.price == reading.price and last.in_stock == reading.in_stock:
        return False

    change = PriceChange(
        **reading.model_dump(),
        previous_price=last.price if last else None,
        previous_in_stock=last.in_stock if last else None,
    )
    publish(producer, topic, change)
    producer.flush()
    redis_client.set_last_price(reading.listing_id, reading.price, reading.in_stock, reading.observed_at)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    producer = make_producer()

    def handle(reading: PriceReading) -> None:
        if process(reading, producer, settings.kafka_topic_changes):
            logger.info(
                "Listing %d changed: price %s, in stock %s",
                reading.listing_id,
                reading.price,
                reading.in_stock,
            )

    logger.info("Change filter started, reading %s", settings.kafka_topic_readings)
    run_consumer(GROUP_ID, settings.kafka_topic_readings, PriceReading, handle)
    logger.info("Change filter stopped")


if __name__ == "__main__":
    main()
