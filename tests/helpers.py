import uuid

from app.common.events import Event
from app.common.kafka import make_consumer


def read_events[T: Event](topic: str, event_type: type[T], expected: int) -> list[T]:
    consumer = make_consumer(f"test-{uuid.uuid4().hex}")
    consumer.subscribe([topic])
    events = []
    try:
        for _ in range(30):
            message = consumer.poll(1.0)
            if message is None or message.error() is not None:
                continue
            events.append(event_type.from_bytes(message.value()))
            if len(events) == expected:
                break
    finally:
        consumer.close()
    return events
