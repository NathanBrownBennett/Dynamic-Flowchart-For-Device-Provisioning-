import ipaddress
import json
import os
import socket
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

import requests

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
    ProviderDescriptor('serpapi_amazon', 'Amazon UK search offers and images via SerpApi'),
    ProviderDescriptor('amazon_paapi_uk', 'Amazon Associates product offers'),
    ProviderDescriptor('ebay_browse', 'eBay marketplace offers'),
    ProviderDescriptor('awin', 'affiliate network product feeds'),
    ProviderDescriptor('cj', 'affiliate network product feeds'),
    ProviderDescriptor('impact', 'affiliate network product catalogues'),
    ProviderDescriptor('nvd', 'CVE/CPE vulnerability evidence'),
    ProviderDescriptor('cisa_kev', 'known exploited vulnerability evidence', requires_credentials=False),
    ProviderDescriptor('osv', 'open-source package vulnerability evidence', requires_credentials=False),
    ProviderDescriptor('manufacturer_advisories', 'vendor support and security advisories', requires_credentials=False),
    ProviderDescriptor('benchmarks', 'licensed or independently published benchmark results'),
)


class ProviderAdapter:
    descriptor: ProviderDescriptor

    def fetch(self) -> Iterable[dict[str, Any]]:
        raise ProviderNotConfigured(
            f"provider '{self.descriptor.name}' is not configured; no network fallback is permitted"
        )


MAX_JSON_BYTES = 10 * 1024 * 1024


def _public_https_url(url, host, path_prefix):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != host or not parsed.path.startswith(path_prefix):
        raise ProviderNotConfigured('provider endpoint is not the fixed approved HTTPS endpoint')
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(
            ipaddress.ip_address(address).is_private or ipaddress.ip_address(address).is_loopback
            or ipaddress.ip_address(address).is_link_local or ipaddress.ip_address(address).is_reserved
            for address in addresses
        ):
            raise ProviderNotConfigured('provider endpoint did not resolve to a public address')
    except (OSError, ValueError) as exc:
        raise ProviderNotConfigured('provider endpoint could not be verified') from exc
    return parsed


def _get_json(url, host, path_prefix, params=None, headers=None):
    parsed = _public_https_url(url, host, path_prefix)
    response = requests.get(
        parsed.geturl(), params=params, headers=headers or {}, timeout=(3, 15),
        allow_redirects=False, stream=True,
    )
    try:
        response.raise_for_status()
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_JSON_BYTES:
            raise ValueError('provider response too large')
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > MAX_JSON_BYTES:
                raise ValueError('provider response too large')
        return json.loads(bytes(body))
    finally:
        response.close()


def _post_json(url, host, path_prefix, payload, headers=None, auth=None, form=None):
    """POST to a fixed HTTPS provider endpoint with bounded response handling."""
    parsed = _public_https_url(url, host, path_prefix)
    response = requests.post(
        parsed.geturl(), json=None if form is not None else payload, data=form,
        headers=headers or {}, auth=auth,
        timeout=(3, 15), allow_redirects=False, stream=True,
    )
    try:
        response.raise_for_status()
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_JSON_BYTES:
            raise ValueError('provider response too large')
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > MAX_JSON_BYTES:
                raise ValueError('provider response too large')
        return json.loads(bytes(body))
    finally:
        response.close()


def _safe_link(value, hosts):
    """Validate provider-returned links without fetching them."""
    parsed = urlparse(str(value or ''))
    hostname = (parsed.hostname or '').lower().rstrip('.')
    if parsed.scheme != 'https' or hostname not in hosts or parsed.username or parsed.password:
        return None
    return parsed.geturl()


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


class SerpApiAmazonAdapter(ProviderAdapter):
    """Optional Amazon UK search adapter using SerpApi's structured endpoint.

    This is deliberately a search/offer adapter, not a product-truth engine.
    It never runs without an operator-provided key and bounded search term.
    """
    descriptor = next(item for item in PROVIDER_CATALOGUE if item.name == 'serpapi_amazon')
    endpoint = 'https://serpapi.com/search'
    source_url = 'https://serpapi.com/amazon-search-api'

    def fetch(self) -> Iterable[dict[str, Any]]:
        api_key = os.environ.get('SERPAPI_API_KEY', '').strip()
        keyword = os.environ.get('SERPAPI_AMAZON_SEARCH_TERM', '').strip()
        if not api_key or not keyword:
            raise ProviderNotConfigured(
                'set SERPAPI_API_KEY and SERPAPI_AMAZON_SEARCH_TERM in the host environment'
            )
        try:
            limit = max(1, min(int(os.environ.get('SERPAPI_RESULT_LIMIT', '20')), 20))
        except ValueError as exc:
            raise ProviderNotConfigured('SERPAPI_RESULT_LIMIT is invalid') from exc
        payload = _get_json(
            self.endpoint, 'serpapi.com', '/search',
            params={
                'engine': 'amazon', 'amazon_domain': 'amazon.co.uk',
                'language': 'en_GB', 'k': keyword[:120], 'page': '1',
                'api_key': api_key, 'output': 'json',
            },
        )
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        expires_at = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=6)).isoformat()
        records = []
        for result in (payload.get('organic_results') or [])[:limit]:
            asin = str(result.get('asin') or '').strip()[:20]
            title = str(result.get('title') or '').strip()[:160]
            link = _safe_link(result.get('link_clean') or result.get('link'),
                              {'amazon.co.uk', 'www.amazon.co.uk'})
            image_url = _safe_link(result.get('thumbnail'), {'m.media-amazon.com'})
            price = _number(result.get('extracted_price'))
            if not asin or not title or not link:
                continue
            # Search results do not reliably identify exact brand/model/OS. Keep
            # these records as offers only until an operator resolves identity.
            brand = str(result.get('brand') or '').strip()[:80]
            if not brand:
                continue
            stock = str(result.get('stock') or '').strip()[:120]
            availability = 'in_stock' if stock and 'out' not in stock.lower() else (
                'out_of_stock' if stock else 'unknown'
            )
            records.append({
                'name': title, 'brand': brand, 'model': title,
                'category': 'Computers', 'cpu_speed': 0, 'ram': 0,
                'storage': 0, 'screen_size': 0, 'price': price,
                'availability': availability, 'source': 'SerpApi Amazon UK search',
                'source_url': self.source_url, 'evidence_url': link,
                'evidence_quality': 'vendor', 'source_license': 'SerpApi terms and applicable Amazon terms; verify before publication',
                'confidence': 'low', 'freshness_hours': 6,
                'price_checked_at': checked_at, 'expires_at': expires_at,
                'image_url': image_url,
                'image_license': 'Amazon-hosted thumbnail returned by SerpApi; verify permitted use before publication',
                'source_state': 'observed', 'operating_system': None,
                'offers': [{
                    'provider': 'serpapi_amazon', 'vendor': 'Amazon UK',
                    'seller': None, 'url': link, 'product_identifier': asin,
                    'price': price, 'item_price': price, 'total_price': price,
                    'currency': 'GBP', 'availability': availability,
                    'stock_message': stock or None, 'checked_at': checked_at,
                    'expires_at': expires_at, 'source_url': self.source_url,
                    'source_license': 'SerpApi terms and applicable Amazon terms; verify before publication',
                    'is_affiliate': False, 'is_sponsored': bool(result.get('sponsored')),
                }],
            })
        return records


class EbayBrowseAdapter(ProviderAdapter):
    """Optional eBay UK Browse API adapter using client-credentials OAuth."""
    descriptor = next(item for item in PROVIDER_CATALOGUE if item.name == 'ebay_browse')
    token_endpoint = 'https://api.ebay.com/identity/v1/oauth2/token'
    search_endpoint = 'https://api.ebay.com/buy/browse/v1/item_summary/search'
    source_url = 'https://developer.ebay.com/develop/api/buy/browse_api'

    def _token(self):
        client_id = os.environ.get('EBAY_CLIENT_ID', '').strip()
        client_secret = os.environ.get('EBAY_CLIENT_SECRET', '').strip()
        if not client_id or not client_secret:
            raise ProviderNotConfigured('set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in the host environment')
        encoded = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        payload = _post_json(
            self.token_endpoint, 'api.ebay.com', '/identity/v1/oauth2/token',
            {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'},
            headers={'Authorization': f'Basic {encoded}', 'Content-Type': 'application/x-www-form-urlencoded'},
            form={'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'},
        )
        token = str(payload.get('access_token') or '').strip()
        if not token:
            raise ProviderNotConfigured('eBay did not return an application access token')
        return token

    def fetch(self) -> Iterable[dict[str, Any]]:
        keyword = os.environ.get('EBAY_SEARCH_TERM', '').strip()
        if not keyword:
            raise ProviderNotConfigured('set EBAY_SEARCH_TERM in the host environment')
        try:
            limit = max(1, min(int(os.environ.get('EBAY_RESULT_LIMIT', '20')), 20))
        except ValueError as exc:
            raise ProviderNotConfigured('EBAY_RESULT_LIMIT is invalid') from exc
        payload = _get_json(
            self.search_endpoint, 'api.ebay.com', '/buy/browse/v1/item_summary/search',
            params={'q': keyword[:120], 'limit': str(limit), 'sort': 'price', 'filter': 'buyingOptions:{FIXED_PRICE}'},
            headers={'Authorization': f'Bearer {self._token()}', 'X-EBAY-C-MARKETPLACE-ID': 'EBAY_GB'},
        )
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        expires_at = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=6)).isoformat()
        records = []
        for result in (payload.get('itemSummaries') or [])[:limit]:
            title = str(result.get('title') or '').strip()[:160]
            link = _safe_link(result.get('itemWebUrl'), {'ebay.co.uk', 'www.ebay.co.uk'})
            image_url = _safe_link((result.get('image') or {}).get('imageUrl'), {'i.ebayimg.com'})
            price_data = result.get('price') or {}
            price = _number(price_data.get('value'))
            brand = str(result.get('brand') or '').strip()[:80]
            if not brand:
                aspects = result.get('localizedAspects') or []
                brand = next((str(item.get('value') or '').strip()[:80] for item in aspects
                              if str(item.get('name') or '').lower() in {'brand', 'manufacturer'}
                              and item.get('value')), '')
            if not title or not link or not brand:
                continue
            condition = str(result.get('condition') or 'new').strip()[:30]
            records.append({
                'name': title, 'brand': brand, 'model': title,
                'category': 'Computers', 'cpu_speed': 0, 'ram': 0,
                'storage': 0, 'screen_size': 0, 'price': price,
                'availability': 'in_stock', 'source': 'eBay Browse API UK',
                'source_url': self.source_url, 'evidence_url': link,
                'evidence_quality': 'vendor', 'source_license': 'eBay API terms; verify permitted display and retention before publication',
                'confidence': 'low', 'freshness_hours': 6,
                'price_checked_at': checked_at, 'expires_at': expires_at,
                'image_url': image_url,
                'image_license': 'eBay-hosted image returned by eBay API; verify permitted use before publication',
                'source_state': 'observed', 'operating_system': None,
                'offers': [{
                    'provider': 'ebay_browse', 'vendor': 'eBay UK',
                    'seller': str((result.get('seller') or {}).get('username') or '')[:80] or None,
                    'url': link, 'product_identifier': str(result.get('itemId') or '')[:80],
                    'price': price, 'item_price': price,
                    'delivery_price': None, 'total_price': price,
                    'currency': str(price_data.get('currency') or 'GBP')[:3],
                    'availability': 'in_stock', 'checked_at': checked_at,
                    'expires_at': expires_at, 'source_url': self.source_url,
                    'source_license': 'eBay API terms; verify permitted display and retention before publication',
                    'is_affiliate': False, 'is_sponsored': False, 'condition': condition,
                }],
            })
        return records


class CisaKevAdapter(ProviderAdapter):
    descriptor = next(item for item in PROVIDER_CATALOGUE if item.name == 'cisa_kev')
    endpoint = 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json'

    def fetch(self) -> Iterable[dict[str, Any]]:
        payload = _get_json(self.endpoint, 'www.cisa.gov', '/sites/default/files/feeds/')
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        records = []
        for item in payload.get('vulnerabilities', [])[:2000]:
            cve_id = str(item.get('cveID') or '').strip()
            if not cve_id:
                continue
            records.append({
                'provider': 'cisa_kev', 'cve_id': cve_id,
                'source_url': f'https://www.cisa.gov/known-exploited-vulnerabilities-catalog',
                'checked_at': checked_at, 'evidence_type': 'independent_published',
                'confidence': 'medium', 'kev_status': 'known_exploited',
                'summary': str(item.get('shortDescription') or item.get('vulnerabilityName') or cve_id)[:500],
                'vendor_project': str(item.get('vendorProject') or '')[:160],
                'product': str(item.get('product') or '')[:160],
                'date_added': str(item.get('dateAdded') or '')[:40],
                'due_date': str(item.get('dueDate') or '')[:40],
            })
        return records


class NvdCveAdapter(ProviderAdapter):
    descriptor = next(item for item in PROVIDER_CATALOGUE if item.name == 'nvd')
    endpoint = 'https://services.nvd.nist.gov/rest/json/cves/2.0'

    def fetch(self) -> Iterable[dict[str, Any]]:
        cpe_name = os.environ.get('NVD_CPE_NAME', '').strip()
        keyword = os.environ.get('NVD_KEYWORD_SEARCH', '').strip()
        if bool(cpe_name) == bool(keyword):
            raise ProviderNotConfigured('set exactly one of NVD_CPE_NAME or NVD_KEYWORD_SEARCH')
        try:
            limit = max(1, min(int(os.environ.get('NVD_RESULTS_LIMIT', '100')), 200))
        except ValueError as exc:
            raise ProviderNotConfigured('NVD_RESULTS_LIMIT is invalid') from exc
        params = {'resultsPerPage': str(limit)}
        if cpe_name:
            params['cpeName'] = cpe_name
        else:
            params['keywordSearch'] = keyword[:120]
        api_key = os.environ.get('NVD_API_KEY', '').strip()
        headers = {'User-Agent': 'BStudioB-Device-Provisioning-Toolkit/1.0'}
        if api_key:
            headers['apiKey'] = api_key
        payload = _get_json(self.endpoint, 'services.nvd.nist.gov', '/rest/json/cves/2.0', params, headers)
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        records = []
        for wrapper in payload.get('vulnerabilities', [])[:limit]:
            cve = wrapper.get('cve') or {}
            cve_id = str(cve.get('id') or '').strip()
            if not cve_id:
                continue
            description = next((item.get('value') for item in cve.get('descriptions', []) if item.get('lang') == 'en'), '')
            records.append({
                'provider': 'nvd', 'cve_id': cve_id,
                'cpe': cpe_name or None,
                'source_url': f'https://nvd.nist.gov/vuln/detail/{cve_id}',
                'checked_at': checked_at, 'evidence_type': 'independent_published',
                'confidence': 'medium', 'summary': str(description or cve_id)[:500],
            })
        return records


class OsvAdapter(ProviderAdapter):
    """Public OSV.dev package vulnerability lookup.

    OSV records are useful for software-package evidence, but are never treated
    as model-specific hardware evidence by the toolkit scoring rules.
    """
    descriptor = next(item for item in PROVIDER_CATALOGUE if item.name == 'osv')
    endpoint = 'https://api.osv.dev/v1/query'
    source_url = 'https://osv.dev/'

    def fetch(self) -> Iterable[dict[str, Any]]:
        package = os.environ.get('OSV_PACKAGE_NAME', '').strip()
        ecosystem = os.environ.get('OSV_ECOSYSTEM', '').strip()
        version = os.environ.get('OSV_PACKAGE_VERSION', '').strip()
        if not package or not ecosystem:
            raise ProviderNotConfigured(
                'set OSV_PACKAGE_NAME and OSV_ECOSYSTEM in the host environment'
            )
        query = {'package': {'name': package[:160], 'ecosystem': ecosystem[:80]}}
        if version:
            query['version'] = version[:80]
        payload = _post_json(
            self.endpoint, 'api.osv.dev', '/v1/query', query,
            headers={'Content-Type': 'application/json', 'User-Agent': 'BStudioB-Device-Provisioning-Toolkit/1.0'},
        )
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        records = []
        for vulnerability in (payload.get('vulns') or [])[:200]:
            osv_id = str(vulnerability.get('id') or '').strip()[:80]
            if not osv_id:
                continue
            aliases = [str(alias).strip() for alias in (vulnerability.get('aliases') or []) if alias]
            records.append({
                'provider': 'osv', 'cve_id': next((alias for alias in aliases if alias.startswith('CVE-')), osv_id),
                'source_url': f'https://osv.dev/vulnerability/{osv_id}',
                'checked_at': checked_at, 'evidence_type': 'independent_published',
                'confidence': 'medium', 'summary': str(vulnerability.get('summary') or osv_id)[:500],
                'osv_id': osv_id, 'package': package[:160], 'ecosystem': ecosystem[:80],
            })
        return records


def provider_descriptors() -> list[dict[str, Any]]:
    return [descriptor.__dict__.copy() for descriptor in PROVIDER_CATALOGUE]


def get_provider(name: str, enabled: bool = False) -> ProviderAdapter:
    descriptor = next((item for item in PROVIDER_CATALOGUE if item.name == name), None)
    if not descriptor or not enabled:
        raise ProviderNotConfigured(f"provider '{name}' is not enabled")
    if name == 'serpapi_amazon':
        return SerpApiAmazonAdapter()
    if name == 'ebay_browse':
        return EbayBrowseAdapter()
    if name == 'cisa_kev':
        return CisaKevAdapter()
    if name == 'nvd':
        return NvdCveAdapter()
    if name == 'osv':
        return OsvAdapter()
    raise ProviderNotConfigured(
        f"provider '{name}' has no approved adapter implementation; use an operator-imported feed"
    )
