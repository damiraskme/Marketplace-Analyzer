from decimal import Decimal

import httpx

from app.marketplaces.base import ListingNotFound, ListingSnapshot, Marketplace

TIMEOUT_SECONDS = 5


class FakeMarketplace(Marketplace):
    name = "fake"

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS)

    def fetch_listing(self, sku: str) -> ListingSnapshot:
        response = self._client.get(f"/items/{sku}")
        return self._parse_item(response, sku)

    def fetch_own_products(self, shop: str) -> list[ListingSnapshot]:
        response = self._client.get("/items", params={"shop": shop})
        response.raise_for_status()
        return [ListingSnapshot.model_validate(item) for item in response.json()]

    def update_price(self, sku: str, price: Decimal) -> ListingSnapshot:
        response = self._client.put(f"/items/{sku}/price", json={"price": str(price)})
        return self._parse_item(response, sku)

    @staticmethod
    def _parse_item(response: httpx.Response, sku: str) -> ListingSnapshot:
        if response.status_code == httpx.codes.NOT_FOUND:
            raise ListingNotFound(sku)
        response.raise_for_status()
        return ListingSnapshot.model_validate(response.json())
