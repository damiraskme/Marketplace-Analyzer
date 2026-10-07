import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

import oracledb

from app.common.config import get_settings
from app.common.db import connect
from app.common.events import AlertMessage, PriceChange
from app.common.kafka import run_consumer

logger = logging.getLogger(__name__)

GROUP_ID = "price-store"
UNKNOWN_LISTING = 20001


class Recorded(NamedTuple):
    recorded: bool
    change_pct: Decimal | None
    is_jump: bool


def to_db_timestamp(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def record_change(cursor: oracledb.Cursor, change: PriceChange) -> Recorded:
    observed_at = cursor.var(oracledb.DB_TYPE_TIMESTAMP)
    observed_at.setvalue(0, to_db_timestamp(change.observed_at))
    recorded = cursor.var(oracledb.DB_TYPE_NUMBER)
    change_pct = cursor.var(oracledb.DB_TYPE_NUMBER)
    is_jump = cursor.var(oracledb.DB_TYPE_NUMBER)

    cursor.callproc(
        "price_pkg.record_change",
        [change.listing_id, change.price, int(change.in_stock), observed_at, recorded, change_pct, is_jump],
    )

    pct = change_pct.getvalue()
    return Recorded(
        recorded=bool(recorded.getvalue()),
        change_pct=None if pct is None else Decimal(str(pct)),
        is_jump=bool(is_jump.getvalue()),
    )


def evaluate(cursor: oracledb.Cursor, listing_id: int) -> list[AlertMessage]:
    alerts = cursor.var(oracledb.DB_TYPE_CURSOR)
    cursor.callproc("alert_pkg.evaluate", [listing_id, alerts])
    return [
        AlertMessage(
            alert_id=alert_id,
            seller_id=seller_id,
            product_id=product_id,
            alert_type=alert_type,
            text=message,
            suggestion_id=suggestion_id,
            suggested_price=suggested_price,
            created_at=created_at.replace(tzinfo=UTC),
        )
        for (
            alert_id,
            seller_id,
            product_id,
            alert_type,
            message,
            suggestion_id,
            suggested_price,
            created_at,
        ) in alerts.getvalue()
    ]


def process(
    connection: oracledb.Connection, change: PriceChange
) -> tuple[Recorded, list[AlertMessage]] | None:
    with connection.cursor() as cursor:
        try:
            result = record_change(cursor, change)
            alerts = evaluate(cursor, change.listing_id) if result.recorded else []
        except oracledb.DatabaseError as error:
            connection.rollback()
            if error.args[0].code == UNKNOWN_LISTING:
                logger.warning("Dropped a change for listing %d, it is not in the database", change.listing_id)
                return None
            raise
    connection.commit()
    return result, alerts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    with connect() as connection:

        def handle(change: PriceChange) -> None:
            processed = process(connection, change)
            if processed is None:
                return
            result, alerts = processed
            if not result.recorded:
                logger.info("Listing %d: already recorded, skipped", change.listing_id)
                return
            logger.info(
                "Listing %d saved: price %s, in stock %s, %s%s",
                change.listing_id,
                change.price,
                change.in_stock,
                "first reading" if result.change_pct is None else f"change {result.change_pct}%",
                ", large jump" if result.is_jump else "",
            )
            for alert in alerts:
                logger.info("Alert %d (%s): %s", alert.alert_id, alert.alert_type, alert.text)

        logger.info("Price store started, reading %s", settings.kafka_topic_changes)
        run_consumer(GROUP_ID, settings.kafka_topic_changes, PriceChange, handle)
        logger.info("Price store stopped")


if __name__ == "__main__":
    main()
