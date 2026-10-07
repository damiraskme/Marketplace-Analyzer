import time
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import NamedTuple

import redis

from app.common.config import get_settings

RATE_LIMIT_KEY_TTL_SECONDS = 120


class LastPrice(NamedTuple):
    price: Decimal
    in_stock: bool


@lru_cache
def get_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _last_price_key(listing_id: int) -> str:
    return f"price:last:{listing_id}"


def _lock_key(listing_id: int) -> str:
    return f"lock:collect:{listing_id}"


def _cooldown_key(seller_id: int, product_id: int, alert_type: str) -> str:
    return f"cooldown:{seller_id}:{product_id}:{alert_type}"


def _rate_limit_key(marketplace: str) -> str:
    return f"ratelimit:{marketplace}:{int(time.time() // 60)}"


def get_last_price(listing_id: int) -> LastPrice | None:
    data = get_client().hgetall(_last_price_key(listing_id))
    if not data:
        return None
    return LastPrice(price=Decimal(data["price"]), in_stock=data["in_stock"] == "1")


def set_last_price(listing_id: int, price: Decimal, in_stock: bool, observed_at: datetime) -> None:
    get_client().hset(
        _last_price_key(listing_id),
        mapping={
            "price": str(price),
            "in_stock": "1" if in_stock else "0",
            "ts": observed_at.isoformat(),
        },
    )


def try_lock(listing_id: int) -> bool:
    ttl = get_settings().collect_lock_ttl_seconds
    return bool(get_client().set(_lock_key(listing_id), "1", nx=True, ex=ttl))


def try_cooldown(seller_id: int, product_id: int, alert_type: str) -> bool:
    ttl = get_settings().alert_cooldown_seconds
    key = _cooldown_key(seller_id, product_id, alert_type)
    return bool(get_client().set(key, "1", nx=True, ex=ttl))


def within_rate_limit(marketplace: str) -> bool:
    key = _rate_limit_key(marketplace)
    pipeline = get_client().pipeline()
    pipeline.incr(key)
    pipeline.expire(key, RATE_LIMIT_KEY_TTL_SECONDS)
    count, _ = pipeline.execute()
    return count <= get_settings().rate_limit_per_minute
