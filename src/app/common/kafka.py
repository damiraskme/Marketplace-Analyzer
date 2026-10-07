import logging
from collections.abc import Callable

from confluent_kafka import Consumer, Producer
from pydantic import ValidationError

from app.common.config import get_settings
from app.common.events import Event

logger = logging.getLogger(__name__)

POLL_TIMEOUT_SECONDS = 1.0


def make_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": get_settings().kafka_bootstrap_servers,
            "enable.idempotence": True,
        }
    )


def make_consumer(group_id: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": get_settings().kafka_bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def _on_delivery(error, message) -> None:
    if error is not None:
        logger.error("Delivery to %s failed: %s", message.topic(), error)


def publish(producer: Producer, topic: str, event: Event) -> None:
    producer.produce(topic, key=event.key(), value=event.to_bytes(), on_delivery=_on_delivery)
    producer.poll(0)


def run_consumer[T: Event](
    group_id: str, topic: str, event_type: type[T], handle: Callable[[T], None]
) -> None:
    consumer = make_consumer(group_id)
    consumer.subscribe([topic])
    try:
        while True:
            message = consumer.poll(POLL_TIMEOUT_SECONDS)
            if message is None:
                continue
            if message.error():
                logger.error("Kafka error: %s", message.error())
                continue

            try:
                event = event_type.from_bytes(message.value())
            except ValidationError as error:
                logger.error("Skipped an unreadable message at offset %d: %s", message.offset(), error)
            else:
                handle(event)

            consumer.commit(message=message, asynchronous=False)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
