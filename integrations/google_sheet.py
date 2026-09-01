"""Safe, read-only import of a deliberately published Google Sheets CSV.

The application never authenticates to Google and never stores a Google
credential. The sheet must contain public, non-personal catalogue data and be
published as CSV by an operator.
"""

import csv
import io
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests


DEFAULT_ALLOWED_HOSTS = {'docs.google.com'}
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_ROWS = 500
DEFAULT_MAX_COLUMNS = 64
DEFAULT_MAX_CELL_BYTES = 20_000
JSON_COLUMNS = {
    'offers_json': 'offers',
    'benchmarks_json': 'benchmarks',
    'security_evidence_json': 'security_evidence',
    'support_lifecycle_json': 'support_lifecycle',
}
REQUIRED_COLUMNS = {'name', 'brand', 'model', 'category'}


class GoogleSheetNotConfigured(ValueError):
    """Raised when the host has not configured a public sheet export."""


def _allowed_hosts(value=None):
    raw = value if value is not None else os.environ.get(
        'GOOGLE_SHEETS_ALLOWED_HOSTS', 'docs.google.com'
    )
    return {host.strip().lower().rstrip('.') for host in str(raw).split(',') if host.strip()}


def _sheet_export_url(value, allowed_hosts=None):
    parsed = urlparse(str(value or '').strip())
    hostname = (parsed.hostname or '').lower().rstrip('.')
    if (parsed.scheme != 'https' or hostname not in (allowed_hosts or _allowed_hosts()) or
            parsed.username or parsed.password or parsed.fragment or
            not parsed.path.startswith('/spreadsheets/')):
        raise GoogleSheetNotConfigured('Google Sheet URL must be an HTTPS published Sheets export')
    return parsed


def fetch_public_csv(url, max_bytes=DEFAULT_MAX_BYTES, allowed_hosts=None):
    """Fetch bounded CSV bytes without following redirects."""
    parsed = _sheet_export_url(url, allowed_hosts)
    try:
        limit = max(64 * 1024, min(int(max_bytes), 10 * 1024 * 1024))
    except (TypeError, ValueError) as exc:
        raise GoogleSheetNotConfigured('Google Sheet size limit is invalid') from exc
    response = requests.get(
        parsed.geturl(),
        headers={'User-Agent': 'BStudioB-Device-Provisioning-Toolkit/1.0'},
        timeout=(3, 15), allow_redirects=False, stream=True,
    )
    try:
        if 300 <= response.status_code < 400:
            raise ValueError('Google Sheet export must not redirect')
        response.raise_for_status()
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > limit:
            raise ValueError('Google Sheet export is too large')
        body = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if len(body) > limit:
                raise ValueError('Google Sheet export is too large')
        try:
            return bytes(body).decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('Google Sheet export must be UTF-8 CSV') from exc
    finally:
        response.close()


def _cell(row, key):
    value = row.get(key)
    return str(value).strip() if value is not None and str(value).strip() else None


def _number(row, key, default=None):
    value = _cell(row, key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f'Google Sheet column {key} must be numeric') from exc


def _json_cell(row, key, default):
    value = _cell(row, key)
    if value is None:
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f'Google Sheet column {key} must contain valid JSON') from exc
    if key == 'support_lifecycle_json':
        if not isinstance(parsed, dict):
            raise ValueError(f'Google Sheet column {key} must contain a JSON object')
        return parsed
    if not isinstance(parsed, list):
        raise ValueError(f'Google Sheet column {key} must contain a JSON array')
    return parsed


def csv_to_feed(csv_text, source, source_url, retrieved_at=None,
                max_rows=DEFAULT_MAX_ROWS, max_columns=DEFAULT_MAX_COLUMNS,
                max_cell_bytes=DEFAULT_MAX_CELL_BYTES):
    """Convert a bounded, operator-maintained CSV into catalogue feed JSON."""
    if not str(source or '').strip() or len(str(source).strip()) > 160:
        raise ValueError('Google Sheet source name is required')
    if not str(csv_text or '').strip():
        raise ValueError('Google Sheet export is empty')
    try:
        row_limit = max(1, min(int(max_rows), 5000))
        column_limit = max(1, min(int(max_columns), 128))
        cell_limit = max(1024, min(int(max_cell_bytes), 100_000))
    except (TypeError, ValueError) as exc:
        raise ValueError('Google Sheet limits are invalid') from exc
    stream = io.StringIO(str(csv_text), newline='')
    try:
        reader = csv.DictReader(stream, strict=True)
        headers = reader.fieldnames or []
    except csv.Error as exc:
        raise ValueError('Google Sheet header row is invalid CSV') from exc
    normalised_headers = [str(header or '').strip().lower().replace(' ', '_') for header in headers]
    if len(normalised_headers) > column_limit or len(set(normalised_headers)) != len(normalised_headers):
        raise ValueError('Google Sheet has too many or duplicate columns')
    if not REQUIRED_COLUMNS.issubset(normalised_headers):
        missing = ', '.join(sorted(REQUIRED_COLUMNS - set(normalised_headers)))
        raise ValueError(f'Google Sheet is missing required columns: {missing}')

    products = []
    for index, raw_row in enumerate(reader, start=2):
        if index > row_limit + 1:
            raise ValueError(f'Google Sheet has more than {row_limit} data rows')
        if None in raw_row:
            raise ValueError(f'Google Sheet row {index} has more columns than its header')
        row = {normalised_headers[i]: value for i, value in enumerate(raw_row.values())}
        if not any(_cell(row, key) for key in normalised_headers):
            continue
        if any(len(str(value or '').encode('utf-8')) > cell_limit for value in row.values()):
            raise ValueError(f'Google Sheet row {index} contains an oversized cell')
        product = {
            'name': _cell(row, 'name'), 'brand': _cell(row, 'brand'),
            'model': _cell(row, 'model'), 'variant': _cell(row, 'variant'),
            'mpn': _cell(row, 'mpn'), 'gtin': _cell(row, 'gtin'),
            'sku': _cell(row, 'sku'), 'region': _cell(row, 'region') or 'GB',
            'category': _cell(row, 'category'), 'cpu_speed': _number(row, 'cpu_speed', 0),
            'ram': _number(row, 'ram', 0), 'storage': _number(row, 'storage', 0),
            'screen_size': _number(row, 'screen_size', 0), 'price': _number(row, 'price'),
            'availability': _cell(row, 'availability') or 'unknown',
            'source': _cell(row, 'source') or str(source).strip(),
            'source_url': _cell(row, 'source_url') or source_url,
            'price_checked_at': _cell(row, 'price_checked_at') or retrieved_at,
            'expires_at': _cell(row, 'expires_at'), 'support_until': _cell(row, 'support_until'),
            'warranty': _cell(row, 'warranty'), 'image_license': _cell(row, 'image_license'),
            'evidence_url': _cell(row, 'evidence_url'),
            'evidence_quality': _cell(row, 'evidence_quality') or 'reviewed',
            'source_license': _cell(row, 'source_license'),
            'confidence': _cell(row, 'confidence') or 'medium',
            'freshness_hours': _number(row, 'freshness_hours'),
            'release_date': _cell(row, 'release_date'),
            'operating_system': _cell(row, 'operating_system'),
            'image_url': _cell(row, 'image_url'),
            'source_state': _cell(row, 'source_state') or 'reviewed',
        }
        for column, target in JSON_COLUMNS.items():
            product[target] = _json_cell(row, column, None if target == 'support_lifecycle' else [])
        products.append(product)
    if not products:
        raise ValueError('Google Sheet contains no catalogue rows')
    return {
        'source': str(source).strip(), 'source_url': str(source_url).strip(),
        'retrieved_at': retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'products': products,
    }


def fetch_catalogue_feed(url, source, source_url, max_bytes=DEFAULT_MAX_BYTES,
                         max_rows=DEFAULT_MAX_ROWS, allowed_hosts=None):
    """Fetch and parse a public sheet; app validation remains authoritative."""
    if not url:
        raise GoogleSheetNotConfigured('GOOGLE_SHEETS_CSV_URL is not configured')
    return csv_to_feed(fetch_public_csv(url, max_bytes=max_bytes, allowed_hosts=allowed_hosts), source, source_url,
                       max_rows=max_rows)
