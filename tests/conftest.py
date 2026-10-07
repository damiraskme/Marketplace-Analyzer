from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import oracledb
import pytest

from app.common.db import connect
from app.common.events import AlertMessage, PriceChange
from app.price_store.main import Recorded, evaluate, record_change, to_db_timestamp

START = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def cursor():
    with connect() as connection, connection.cursor() as cursor:
        yield cursor
        connection.rollback()


@dataclass
class Scenario:
    cursor: oracledb.Cursor
    product_id: int
    own: int
    competitors: dict[str, int]
    minutes: int = 0

    def set_rules(self, floor: str, ceiling: str, margin: str = "15", step: str = "10") -> None:
        self.cursor.execute(
            """
            UPDATE pricing_rules
               SET price_floor = :floor, price_ceiling = :ceiling,
                   min_margin_pct = :margin, undercut_step = :step, jump_threshold_pct = 20
             WHERE product_id = :id
            """,
            floor=Decimal(floor),
            ceiling=Decimal(ceiling),
            margin=Decimal(margin),
            step=Decimal(step),
            id=self.product_id,
        )

    def set_competitor(self, name: str, price: str, in_stock: bool = True) -> None:
        self.cursor.execute(
            "UPDATE listings SET last_price = :price, in_stock = :in_stock WHERE id = :id",
            price=Decimal(price),
            in_stock=int(in_stock),
            id=self.competitors[name],
        )

    def suggest_price(self) -> Decimal | None:
        return self.cursor.callfunc("pricing_pkg.suggest_price", oracledb.DB_TYPE_NUMBER, [self.product_id])

    def change(self, listing_id: int, price: str, in_stock: bool = True) -> tuple[Recorded, list[AlertMessage]]:
        self.minutes += 1
        change = PriceChange(
            listing_id=listing_id,
            marketplace="fake",
            price=Decimal(price),
            in_stock=in_stock,
            observed_at=START + timedelta(minutes=self.minutes),
        )
        result = record_change(self.cursor, change)
        alerts = evaluate(self.cursor, listing_id) if result.recorded else []
        return result, alerts

    def pending_suggestions(self) -> list[Decimal]:
        self.cursor.execute(
            "SELECT suggested_price FROM price_suggestions WHERE product_id = :id AND status = 'PENDING'",
            id=self.product_id,
        )
        return [row[0] for row in self.cursor]


@pytest.fixture
def scenario(cursor) -> Scenario:
    cursor.execute("SELECT id FROM products WHERE sku = 'OWN-1001'")
    product_id = cursor.fetchone()[0]
    cursor.execute("SELECT kind, sku, id FROM listings WHERE product_id = :id", id=product_id)
    listings = cursor.fetchall()
    own = next(listing_id for kind, _, listing_id in listings if kind == "OWN")
    competitors = {sku[-1]: listing_id for kind, sku, listing_id in listings if kind == "COMPETITOR"}

    cursor.execute(
        "DELETE FROM price_history WHERE listing_id IN (SELECT id FROM listings WHERE product_id = :id)",
        id=product_id,
    )
    cursor.execute(
        "UPDATE price_suggestions SET status = 'DISMISSED' WHERE product_id = :id AND status = 'PENDING'",
        id=product_id,
    )
    cursor.execute(
        "UPDATE products SET cost_price = 6000, current_price = 10000 WHERE id = :id", id=product_id
    )
    cursor.execute(
        """
        UPDATE listings
           SET last_price = CASE kind WHEN 'OWN' THEN 10000 ELSE 11000 END,
               in_stock = 1, active = 1, last_observed_at = :ts
         WHERE product_id = :id
        """,
        ts=to_db_timestamp(START),
        id=product_id,
    )

    scenario = Scenario(cursor=cursor, product_id=product_id, own=own, competitors=competitors)
    scenario.set_rules(floor="7000", ceiling="12000")
    return scenario
