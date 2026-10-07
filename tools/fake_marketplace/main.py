import asyncio
import random
from contextlib import asynccontextmanager
from decimal import Decimal
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.common.config import get_settings

OWN_SHOP = "Demo Seller"
COMPETITOR_SHOPS = {
    "A": ("TechnoMart", Decimal("1.05")),
    "B": ("GadgetHub", Decimal("1.02")),
    "C": ("SmartStore", Decimal("0.97")),
}
PRODUCTS = [
    ("1001", "Wireless Earbuds X1", Decimal("9990")),
    ("1002", "Slim Phone Case", Decimal("1990")),
    ("1003", "USB-C Cable 2 m", Decimal("1490")),
]

PRICE_STEP = Decimal("10")
MIN_PRICE_FACTOR = Decimal("0.5")
MAX_PRICE_FACTOR = Decimal("1.5")
STOCK_FLIP_CHANCE = 0.10
BIG_JUMP_CHANCE = 0.05


class Item(BaseModel):
    sku: str
    shop: str
    title: str
    price: Decimal
    in_stock: bool


class PriceUpdate(BaseModel):
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class StockUpdate(BaseModel):
    in_stock: bool


def round_to_step(price: Decimal) -> Decimal:
    return (price / PRICE_STEP).quantize(Decimal("1")) * PRICE_STEP


def build_catalog() -> tuple[dict[str, Item], dict[str, Decimal]]:
    items = {}
    base_prices = {}
    for number, title, price in PRODUCTS:
        own_sku = f"OWN-{number}"
        items[own_sku] = Item(sku=own_sku, shop=OWN_SHOP, title=title, price=price, in_stock=True)
        base_prices[own_sku] = price
        for suffix, (shop, factor) in COMPETITOR_SHOPS.items():
            sku = f"COMP-{number}-{suffix}"
            items[sku] = Item(
                sku=sku,
                shop=shop,
                title=f"{shop}: {title}",
                price=round_to_step(price * factor),
                in_stock=True,
            )
            base_prices[sku] = price
    return items, base_prices


ITEMS, BASE_PRICES = build_catalog()


def change_random_competitor() -> Item:
    item = random.choice([i for i in ITEMS.values() if i.shop != OWN_SHOP])
    roll = random.random()

    if roll < STOCK_FLIP_CHANCE:
        item.in_stock = not item.in_stock
        return item

    if roll < STOCK_FLIP_CHANCE + BIG_JUMP_CHANCE:
        spread = random.uniform(0.25, 0.40)
    else:
        spread = random.uniform(0.01, 0.08)
    direction = random.choice((1, -1))

    base = BASE_PRICES[item.sku]
    lowest = round_to_step(base * MIN_PRICE_FACTOR)
    highest = round_to_step(base * MAX_PRICE_FACTOR)
    new_price = round_to_step(item.price * (1 + Decimal(str(direction * spread))))
    new_price = min(max(new_price, lowest), highest)

    if new_price == item.price:
        new_price = item.price - PRICE_STEP if item.price > lowest else item.price + PRICE_STEP

    item.price = new_price
    return item


async def change_prices_forever(interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        change_random_competitor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    interval = get_settings().fake_change_interval_seconds
    task = asyncio.create_task(change_prices_forever(interval)) if interval > 0 else None
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="Fake Marketplace", lifespan=lifespan)


def find_item(sku: str) -> Item:
    item = ITEMS.get(sku)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {sku} not found")
    return item


@app.get("/items")
def list_items(shop: str | None = None) -> list[Item]:
    return [item for item in ITEMS.values() if shop is None or item.shop == shop]


@app.get("/items/{sku}")
def get_item(sku: str) -> Item:
    return find_item(sku)


@app.put("/items/{sku}/price")
def set_price(sku: str, update: PriceUpdate) -> Item:
    item = find_item(sku)
    item.price = update.price
    return item


@app.put("/items/{sku}/stock")
def set_stock(sku: str, update: StockUpdate) -> Item:
    item = find_item(sku)
    item.in_stock = update.in_stock
    return item


if __name__ == "__main__":
    url = urlsplit(get_settings().fake_marketplace_url)
    uvicorn.run(app, host=url.hostname, port=url.port)
