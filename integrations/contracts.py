from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


class ContractError(ValueError):
    """Raised when an external record cannot be made unambiguous and safe."""


EVIDENCE_TYPES = {
    'measured',
    'independent_published',
    'vendor_claimed',
    'specification_estimate',
    'unknown',
}


@dataclass(frozen=True)
class ProductIdentity:
    brand: str
    model: str
    variant: Optional[str] = None
    mpn: Optional[str] = None
    gtin: Optional[str] = None
    sku: Optional[str] = None
    region: str = 'GB'

    def key(self) -> str:
        return '|'.join(value.strip().lower() for value in (
            self.brand, self.model, self.variant or '', self.mpn or '',
            self.gtin or '', self.region
        ))


@dataclass(frozen=True)
class OfferRecord:
    provider: str
    vendor: str
    url: str
    product_identifier: str
    currency: str = 'GBP'
    item_price: Optional[float] = None
    delivery_price: Optional[float] = None
    total_price: Optional[float] = None
    availability: str = 'unknown'
    checked_at: Optional[str] = None
    expires_at: Optional[str] = None
    affiliate_url: Optional[str] = None
    condition: str = 'new'


@dataclass(frozen=True)
class ProviderRun:
    provider: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    item_count: int = 0
    error_summary: Optional[str] = None
    source_url: Optional[str] = None


def normalise_identity(value: Any) -> ProductIdentity:
    if not isinstance(value, dict):
        raise ContractError('product identity must be an object')
    brand = str(value.get('brand') or '').strip()
    model = str(value.get('model') or '').strip()
    if not brand or not model or len(brand) > 80 or len(model) > 120:
        raise ContractError('brand and model are required for an unambiguous product identity')
    return ProductIdentity(
        brand=brand,
        model=model,
        variant=str(value.get('variant') or '').strip()[:120] or None,
        mpn=str(value.get('mpn') or '').strip()[:80] or None,
        gtin=str(value.get('gtin') or '').strip()[:32] or None,
        sku=str(value.get('sku') or '').strip()[:80] or None,
        region=str(value.get('region') or 'GB').strip()[:8].upper(),
    )


def evidence_type(value: Any) -> str:
    result = str(value or 'unknown').strip().lower()
    if result not in EVIDENCE_TYPES:
        raise ContractError(f'unsupported evidence type: {result}')
    return result
