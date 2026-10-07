from functools import lru_cache

from app.common.config import get_settings
from app.marketplaces.base import Marketplace
from app.marketplaces.fake import FakeMarketplace


@lru_cache
def get_marketplace() -> Marketplace:
    return FakeMarketplace(get_settings().fake_marketplace_url)
