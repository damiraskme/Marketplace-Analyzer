from abc import ABC, abstractmethod
from decimal import Decimal

from pydantic import BaseModel


class ListingSnapshot(BaseModel):
    sku: str
    shop: str
    title: str
    price: Decimal
    in_stock: bool


class ListingNotFound(Exception):
    def __init__(self, sku: str) -> None:
        super().__init__(f"Listing {sku} was not found on the marketplace")
        self.sku = sku


class Marketplace(ABC):
    name: str

    @abstractmethod
    def fetch_listing(self, sku: str) -> ListingSnapshot: ...

    @abstractmethod
    def fetch_own_products(self, shop: str) -> list[ListingSnapshot]: ...

    @abstractmethod
    def update_price(self, sku: str, price: Decimal) -> ListingSnapshot: ...
