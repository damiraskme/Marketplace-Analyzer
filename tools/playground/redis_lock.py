import time

import redis

from app.common.config import get_settings

KEY = "playground:lock"
TTL_SECONDS = 10

client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)

print("First try:", client.set(KEY, "1", nx=True, ex=TTL_SECONDS))
print("Second try:", client.set(KEY, "1", nx=True, ex=TTL_SECONDS))
print("Seconds until the key expires:", client.ttl(KEY))

print(f"Waiting {TTL_SECONDS + 1} seconds...")
time.sleep(TTL_SECONDS + 1)

print("Try after expiry:", client.set(KEY, "1", nx=True, ex=TTL_SECONDS))
client.delete(KEY)
