from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> Self:
        return cls.model_validate_json(raw)


class PriceReading(Event):
    listing_id: int
    marketplace: str
    price: Decimal
    in_stock: bool
    observed_at: AwareDatetime

    def key(self) -> bytes:
        return str(self.listing_id).encode("utf-8")


class PriceChange(PriceReading):
    previous_price: Decimal | None = None
    previous_in_stock: bool | None = None


class AlertType(StrEnum):
    COMPETITOR_PRICE_DROP = "COMPETITOR_PRICE_DROP"
    COMPETITOR_OUT_OF_STOCK = "COMPETITOR_OUT_OF_STOCK"
    LARGE_JUMP = "LARGE_JUMP"
    NEW_SUGGESTION = "NEW_SUGGESTION"


class AlertMessage(Event):
    alert_id: int
    seller_id: int
    product_id: int
    alert_type: AlertType
    text: str
    suggestion_id: int | None = None
    suggested_price: Decimal | None = None
    created_at: AwareDatetime

    def key(self) -> bytes:
        return str(self.seller_id).encode("utf-8")
