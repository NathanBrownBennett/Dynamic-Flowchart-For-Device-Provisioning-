from dataclasses import dataclass
from typing import Any, Iterable

from .contracts import ProviderRun


class ProviderNotConfigured(RuntimeError):
    """The provider needs operator approval/configuration before use."""


@dataclass(frozen=True)
class ProviderDescriptor:
    name: str
    purpose: str
    requires_credentials: bool = True
    enabled: bool = False


PROVIDER_CATALOGUE = (
    ProviderDescriptor('icecat', 'product specifications, images and manuals'),
    ProviderDescriptor('amazon_paapi_uk', 'Amazon Associates product offers'),
    ProviderDescriptor('ebay_browse', 'eBay marketplace offers'),
    ProviderDescriptor('awin', 'affiliate network product feeds'),
    ProviderDescriptor('cj', 'affiliate network product feeds'),
    ProviderDescriptor('impact', 'affiliate network product catalogues'),
    ProviderDescriptor('nvd', 'CVE/CPE vulnerability evidence'),
    ProviderDescriptor('cisa_kev', 'known exploited vulnerability evidence', requires_credentials=False),
    ProviderDescriptor('manufacturer_advisories', 'vendor support and security advisories', requires_credentials=False),
    ProviderDescriptor('benchmarks', 'licensed or independently published benchmark results'),
)


class ProviderAdapter:
    descriptor: ProviderDescriptor

    def fetch(self) -> Iterable[dict[str, Any]]:
        raise ProviderNotConfigured(
            f"provider '{self.descriptor.name}' is not configured; no network fallback is permitted"
        )


def provider_descriptors() -> list[dict[str, Any]]:
    return [descriptor.__dict__.copy() for descriptor in PROVIDER_CATALOGUE]


def get_provider(name: str, enabled: bool = False) -> ProviderAdapter:
    descriptor = next((item for item in PROVIDER_CATALOGUE if item.name == name), None)
    if not descriptor or not enabled:
        raise ProviderNotConfigured(f"provider '{name}' is not enabled")
    raise ProviderNotConfigured(
        f"provider '{name}' has no approved adapter implementation; use an operator-imported feed"
    )
