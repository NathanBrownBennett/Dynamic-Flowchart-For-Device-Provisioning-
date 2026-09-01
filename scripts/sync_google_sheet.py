#!/usr/bin/env python3
"""Validate or import a published Google Sheets catalogue export.

The URL must point to a public, non-personal Google Sheets CSV export. The
default is validation-only; pass --import to replace the local SQLite
catalogue atomically after validation.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.google_sheet import fetch_catalogue_feed
from app import replace_catalogue, validate_catalogue_feed


def main():
    parser = argparse.ArgumentParser(description='Validate/import a public Google Sheets catalogue CSV')
    parser.add_argument('--url', default=os.environ.get('GOOGLE_SHEETS_CSV_URL', ''))
    parser.add_argument('--source', default=os.environ.get('GOOGLE_SHEETS_SOURCE_NAME', 'BStudioB reviewed catalogue'))
    parser.add_argument('--import', dest='do_import', action='store_true', help='Replace the configured SQLite catalogue')
    args = parser.parse_args()
    try:
        payload = fetch_catalogue_feed(args.url, args.source, args.url)
        products, source, source_url, retrieved_at = validate_catalogue_feed(payload)
        if any(str(product.get('source_state', '')).lower() in {'sample', 'fixture'} for product in products):
            raise ValueError('Google Sheet cannot import sample or fixture records')
        if args.do_import:
            replace_catalogue(products, source, source_url, retrieved_at)
        print(json.dumps({'status': 'imported' if args.do_import else 'validated',
                          'products': len(products), 'retrieved_at': retrieved_at}))
        return 0
    except (OSError, ValueError) as exc:
        print(f'Google Sheet sync failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
