from confluent_kafka import Producer

from app.common.config import get_settings

TOPIC = "playground.test"

producer = Producer({"bootstrap.servers": get_settings().kafka_bootstrap_servers})

for i in range(5):
    producer.produce(TOPIC, key=str(i % 2), value=f"message {i}")

producer.flush()
print(f"Sent 5 messages to {TOPIC}")
