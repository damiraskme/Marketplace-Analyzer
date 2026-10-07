import sys

from confluent_kafka import Consumer

from app.common.config import get_settings

TOPIC = "playground.test"

group = sys.argv[1] if len(sys.argv) > 1 else "playground"

consumer = Consumer(
    {
        "bootstrap.servers": get_settings().kafka_bootstrap_servers,
        "group.id": group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
)
consumer.subscribe([TOPIC])
print(f"Reading {TOPIC} as group '{group}'. Press Ctrl+C to stop.")

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Error: {msg.error()}")
            continue
        print(
            f"partition={msg.partition()} offset={msg.offset()} "
            f"key={msg.key().decode()} value={msg.value().decode()}"
        )
        consumer.commit(msg)
except KeyboardInterrupt:
    pass
finally:
    consumer.close()
