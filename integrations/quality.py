"""Quality profile for the evidence used by the public catalogue.

This module is deliberately read-only. It measures coverage and freshness but
does not turn incomplete records into scores or modify the database.
"""

from collections import Counter
from datetime import datetime, timezone


SUPPORTED_OPERATING_SYSTEMS = {'Windows 11', 'macOS', 'ChromeOS', 'Android', 'iPadOS', 'Linux'}


def _table_exists(connection, table):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _current(value, now):
    if not value:
        return True
    parsed = _parse_timestamp(value)
    return parsed is not None and parsed > now


def profile_catalogue_connection(connection, now=None):
    """Return a compact, JSON-serialisable coverage and release-gate profile."""
    now = now or datetime.now(timezone.utc)
    required_tables = (
        'devices', 'device_catalogue_metadata', 'device_offers',
        'benchmark_results', 'security_evidence', 'support_lifecycle',
    )
    missing_tables = [table for table in required_tables if not _table_exists(connection, table)]
    if missing_tables:
        return {
            'schema_state': 'incomplete',
            'missing_tables': missing_tables,
            'release_ready': False,
            'gates': {},
            'issues': ['Catalogue evidence tables are missing; run the application schema migration first.'],
        }

    devices = connection.execute(
        'SELECT id, brand, model, variant, mpn, gtin, region, operating_system FROM devices'
    ).fetchall()
    device_ids = {row[0] for row in devices}
    identity_keys = [tuple(str(value or '').strip().lower() for value in row[1:7]) for row in devices]
    duplicate_identity_count = sum(count - 1 for count in Counter(identity_keys).values() if count > 1)

    metadata = connection.execute(
        '''SELECT device_id, source_url, evidence_url, source_state, confidence,
                          expires_at, image_license FROM device_catalogue_metadata'''
    ).fetchall()
    metadata_by_id = {row[0]: row for row in metadata}
    offers = connection.execute(
        '''SELECT device_id, vendor, price, total_price, checked_at, expires_at
           FROM device_offers'''
    ).fetchall()
    current_offers = [row for row in offers if _current(row[5], now)]
    current_vendors = {}
    for row in current_offers:
        current_vendors.setdefault(row[0], set()).add(str(row[1] or '').strip().lower())

    benchmarks = connection.execute(
        '''SELECT device_id, score, evidence_type, source_url, tested_at
           FROM benchmark_results'''
    ).fetchall()
    valid_benchmarks = [
        row for row in benchmarks
        if row[1] is not None and row[2] in {'measured', 'independent_published'}
        and str(row[3] or '').startswith('https://') and _parse_timestamp(row[4]) is not None
    ]
    security = connection.execute(
        '''SELECT device_id, cve_id, cpe, source_url, checked_at
           FROM security_evidence'''
    ).fetchall()
    valid_security = [
        row for row in security
        if (row[1] or row[2]) and str(row[3] or '').startswith('https://')
        and _parse_timestamp(row[4]) is not None
    ]
    support = connection.execute(
        '''SELECT device_id, operating_system, support_until, source_url, checked_at
           FROM support_lifecycle'''
    ).fetchall()
    valid_support = [
        row for row in support
        if row[1] in SUPPORTED_OPERATING_SYSTEMS and _parse_timestamp(row[2]) is not None
        and str(row[3] or '').startswith('https://') and _parse_timestamp(row[4]) is not None
    ]

    product_count = len(devices)
    identity_complete = sum(bool(row[1] and row[2] and row[6]) for row in devices)
    explicit_os = sum(row[7] in SUPPORTED_OPERATING_SYSTEMS for row in devices)
    source_attributed = sum(bool(row[1] and row[2]) for row in metadata if row[0] in device_ids)
    current_metadata = sum(_current(row[5], now) for row in metadata if row[0] in device_ids)
    image_licensed = sum(bool(row[6]) for row in metadata if row[0] in device_ids)

    def distinct_devices(rows):
        return len({row[0] for row in rows if row[0] in device_ids})

    counts = {
        'products': product_count,
        'identity_complete': identity_complete,
        'identity_duplicates': duplicate_identity_count,
        'explicit_operating_system': explicit_os,
        'source_attributed': source_attributed,
        'current_metadata': current_metadata,
        'image_license_recorded': image_licensed,
        'offers_total': len(offers),
        'current_offers': len(current_offers),
        'products_with_current_offer': len(current_vendors),
        'products_with_two_current_vendors': sum(len(vendors) >= 2 for vendors in current_vendors.values()),
        'valid_benchmark_records': len(valid_benchmarks),
        'products_with_valid_benchmark': distinct_devices(valid_benchmarks),
        'valid_security_records': len(valid_security),
        'products_with_valid_security_evidence': distinct_devices(valid_security),
        'valid_support_records': len(valid_support),
        'products_with_valid_support': distinct_devices(valid_support),
    }
    gates = {
        'product_identity_complete': product_count > 0 and identity_complete == product_count and duplicate_identity_count == 0,
        'catalogue_source_attributed': product_count > 0 and source_attributed == product_count,
        'current_offer_coverage': product_count > 0 and len(current_vendors) == product_count,
        'multi_vendor_coverage': product_count > 0 and counts['products_with_two_current_vendors'] == product_count,
        'explicit_os_coverage': product_count > 0 and explicit_os == product_count,
        'security_evidence_coverage': product_count > 0 and counts['products_with_valid_security_evidence'] == product_count,
        'support_lifecycle_coverage': product_count > 0 and counts['products_with_valid_support'] == product_count,
        'benchmark_coverage': product_count > 0 and counts['products_with_valid_benchmark'] == product_count,
    }
    issues = []
    if duplicate_identity_count:
        issues.append(f'{duplicate_identity_count} duplicate product identity record(s) detected.')
    if counts['products_with_current_offer'] < product_count:
        issues.append('Some products have no current offer; they must not be shown as live purchasable results.')
    if not gates['multi_vendor_coverage']:
        issues.append('Multi-vendor price comparison is incomplete; one vendor is not a market comparison.')
    if not gates['security_evidence_coverage'] or not gates['support_lifecycle_coverage']:
        issues.append('Security ratings must remain withheld until model-linked evidence and support lifecycle records cover the product.')
    if not gates['benchmark_coverage']:
        issues.append('Performance ratings must remain withheld until measured or independently published benchmark records cover the product.')
    return {
        'schema_state': 'complete',
        'missing_tables': [],
        'counts': counts,
        'gates': gates,
        'release_ready': all(gates.values()),
        'issues': issues,
    }
