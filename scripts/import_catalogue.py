#!/usr/bin/env python3
"""Import an approved product feed without fetching any remote URL.

Usage:
    python scripts/import_catalogue.py --feed catalogue-feed.example.json
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import replace_catalogue, validate_catalogue_feed


def main():
    parser = argparse.ArgumentParser(description='Import a validated product catalogue feed')
    parser.add_argument('--feed', required=True, help='Path to a JSON feed file')
    args = parser.parse_args()
    try:
        with open(args.feed, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
        products, source, source_url, retrieved_at = validate_catalogue_feed(payload)
        replace_catalogue(products, source, source_url, retrieved_at)
        print(json.dumps({'imported': len(products), 'source': source, 'retrieved_at': retrieved_at}))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f'Catalogue import failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
