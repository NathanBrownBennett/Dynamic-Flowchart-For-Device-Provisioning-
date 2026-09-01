#!/usr/bin/env python3
"""Export the reviewed SQLite catalogue into the Google Sheet row contract.

This is a local, read-only export. It does not contact Google and never adds
credentials or private operator data to the output.
"""

import argparse
import csv
import json
import sqlite3


HEADERS = [
    'name', 'brand', 'model', 'variant', 'mpn', 'gtin', 'sku', 'region', 'category',
    'cpu_speed', 'ram', 'storage', 'screen_size', 'price', 'availability', 'source',
    'source_url', 'price_checked_at', 'expires_at', 'support_until', 'warranty',
    'image_url', 'image_license', 'evidence_url', 'evidence_quality', 'source_license',
    'confidence', 'freshness_hours', 'release_date', 'operating_system', 'source_state',
    'offers_json', 'benchmarks_json', 'security_evidence_json', 'support_lifecycle_json',
]


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def export_catalogue(database, output):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        required = {'devices', 'device_catalogue_metadata', 'device_offers',
                    'benchmark_results', 'security_evidence', 'support_lifecycle'}
        missing = sorted(required - tables)
        if missing:
            raise ValueError('database is missing catalogue tables: ' + ', '.join(missing))
        devices = connection.execute('''
            SELECT d.*, m.source, m.source_url, m.price_checked_at, m.availability,
                   m.expires_at, m.support_until, m.warranty, m.image_license,
                   m.evidence_url, m.evidence_quality, m.source_license,
                   m.confidence, m.freshness_hours
            FROM devices d
            LEFT JOIN device_catalogue_metadata m ON m.device_id = d.id
            ORDER BY d.id
        ''').fetchall()
        offers = {}
        for row in connection.execute('''
            SELECT device_id, provider, vendor, seller, url, affiliate_url,
                   product_identifier, condition, price, item_price, delivery_price,
                   total_price, currency, availability, stock_message, checked_at,
                   expires_at, source_url, source_license, is_affiliate, is_sponsored
            FROM device_offers ORDER BY device_id, total_price IS NULL, total_price, vendor
        '''):
            offers.setdefault(row['device_id'], []).append({
                'provider': row['provider'], 'vendor': row['vendor'], 'seller': row['seller'],
                'url': row['url'], 'affiliate_url': row['affiliate_url'],
                'product_identifier': row['product_identifier'], 'condition': row['condition'],
                'price': row['price'], 'item_price': row['item_price'],
                'delivery_price': row['delivery_price'], 'total_price': row['total_price'],
                'currency': row['currency'], 'availability': row['availability'],
                'stock_message': row['stock_message'], 'checked_at': row['checked_at'],
                'expires_at': row['expires_at'], 'source_url': row['source_url'],
                'source_license': row['source_license'], 'is_affiliate': bool(row['is_affiliate']),
                'is_sponsored': bool(row['is_sponsored']),
            })
        evidence = {'benchmarks': {}, 'security_evidence': {}, 'support_lifecycle': {}}
        for row in connection.execute('SELECT * FROM benchmark_results ORDER BY device_id, tested_at DESC'):
            evidence['benchmarks'].setdefault(row['device_id'], []).append({
                'suite': row['suite'], 'version': row['version'], 'workload': row['workload'],
                'score': row['score'], 'evidence_type': row['evidence_type'],
                'source_url': row['source_url'], 'licence': row['licence'],
                'tested_at': row['tested_at'], 'confidence': row['confidence'], 'notes': row['notes'],
            })
        for row in connection.execute('SELECT * FROM security_evidence ORDER BY device_id, checked_at DESC'):
            evidence['security_evidence'].setdefault(row['device_id'], []).append({
                'provider': row['provider'], 'cve_id': row['cve_id'], 'cpe': row['cpe'],
                'kev_status': row['kev_status'], 'affected_version': row['affected_version'],
                'fixed_version': row['fixed_version'], 'source_url': row['source_url'],
                'checked_at': row['checked_at'], 'evidence_type': row['evidence_type'],
                'confidence': row['confidence'], 'summary': row['summary'],
            })
        for row in connection.execute('SELECT * FROM support_lifecycle ORDER BY device_id, checked_at DESC'):
            evidence['support_lifecycle'].setdefault(row['device_id'], {
                'operating_system': row['operating_system'], 'support_until': row['support_until'],
                'patch_cadence': row['patch_cadence'], 'source_url': row['source_url'],
                'checked_at': row['checked_at'], 'confidence': row['confidence'],
            })
        with open(output, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS)
            writer.writeheader()
            for row in devices:
                item = dict(row)
                item.update({
                    'offers_json': _json(offers.get(row['id'], [])),
                    'benchmarks_json': _json(evidence['benchmarks'].get(row['id'], [])),
                    'security_evidence_json': _json(evidence['security_evidence'].get(row['id'], [])),
                    'support_lifecycle_json': _json(evidence['support_lifecycle'].get(row['id'], {})),
                })
                writer.writerow({header: item.get(header) if item.get(header) is not None else '' for header in HEADERS})
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description='Export SQLite catalogue to the Google Sheet CSV contract')
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        export_catalogue(args.database, args.output)
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'status': 'exported', 'output': args.output}))


if __name__ == '__main__':
    main()
