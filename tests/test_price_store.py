from datetime import UTC, datetime, timedelta
from decimal import Decimal

import oracledb
import pytest

from app.common.events import PriceChange
from app.price_store.main import UNKNOWN_LISTING, record_change, to_db_timestamp

START = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def listing_id_for(cursor, sku: str) -> int:
    cursor.execute("SELECT id FROM listings WHERE sku = :sku", sku=sku)
    return cursor.fetchone()[0]


@pytest.fixture
def competitor(cursor) -> int:
    listing_id = listing_id_for(cursor, "COMP-1001-A")
    cursor.execute("DELETE FROM price_history WHERE listing_id = :id", id=listing_id)
    cursor.execute(
        "UPDATE listings SET last_price = 1000, in_stock = 1, last_observed_at = :ts WHERE id = :id",
        ts=to_db_timestamp(START),
        id=listing_id,
    )
    return listing_id


def change(listing_id: int, price: str, in_stock: bool = True, minutes: int = 1) -> PriceChange:
    return PriceChange(
        listing_id=listing_id,
        marketplace="fake",
        price=Decimal(price),
        in_stock=in_stock,
        observed_at=START + timedelta(minutes=minutes),
    )


def test_change_is_saved_with_previous_price(cursor, competitor):
    result = record_change(cursor, change(competitor, "950.00"))

    assert result.recorded is True
    assert result.change_pct == Decimal("-5")
    assert result.is_jump is False

    cursor.execute(
        "SELECT price, prev_price, change_pct, is_large_jump FROM price_history WHERE listing_id = :id",
        id=competitor,
    )
    assert cursor.fetchall() == [(Decimal("950"), Decimal("1000"), Decimal("-5"), 0)]

    cursor.execute("SELECT last_price FROM listings WHERE id = :id", id=competitor)
    assert cursor.fetchone()[0] == Decimal("950")


def test_same_message_twice_is_saved_once(cursor, competitor):
    assert record_change(cursor, change(competitor, "950.00")).recorded is True
    assert record_change(cursor, change(competitor, "950.00")).recorded is False

    cursor.execute("SELECT COUNT(*) FROM price_history WHERE listing_id = :id", id=competitor)
    assert cursor.fetchone()[0] == 1


def test_unchanged_price_is_not_saved(cursor, competitor):
    assert record_change(cursor, change(competitor, "1000.00")).recorded is False


def test_older_reading_is_not_saved(cursor, competitor):
    assert record_change(cursor, change(competitor, "950.00", minutes=-5)).recorded is False


def test_large_jump_is_flagged(cursor, competitor):
    result = record_change(cursor, change(competitor, "1500.00"))

    assert result.change_pct == Decimal("50")
    assert result.is_jump is True


def test_stock_change_alone_is_saved(cursor, competitor):
    result = record_change(cursor, change(competitor, "1000.00", in_stock=False))

    assert result.recorded is True
    assert result.change_pct == Decimal("0")
    assert result.is_jump is False


def test_own_listing_updates_product_price(cursor):
    listing_id = listing_id_for(cursor, "OWN-1001")
    cursor.execute("UPDATE listings SET last_observed_at = NULL WHERE id = :id", id=listing_id)

    record_change(cursor, change(listing_id, "8888.00"))

    cursor.execute("SELECT current_price FROM products WHERE sku = 'OWN-1001'")
    assert cursor.fetchone()[0] == Decimal("8888")


def test_unknown_listing_raises(cursor):
    with pytest.raises(oracledb.DatabaseError) as raised:
        record_change(cursor, change(-999, "100.00"))

    assert raised.value.args[0].code == UNKNOWN_LISTING
