#!/usr/bin/env python3
"""Run one explicitly enabled provider and optionally write a reviewed feed draft.

This command never imports data into the application database. It is intended
for an operator-controlled job after provider terms, credentials, fields,
retention and refresh limits have been approved.

Examples:
    python scripts/fetch_provider.py --provider serpapi_amazon --output /tmp/amazon-feed.json
    python scripts/fetch_provider.py --provider cisa_kev --output /tmp/kev-records.json
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.providers import ProviderNotConfigured, get_provider


OFFER_PROVIDERS = {'serpapi_amazon', 'ebay_browse'}


def main():
    parser = argparse.ArgumentParser(description='Fetch one approved provider without importing it')
    parser.add_argument('--provider', required=True)
    parser.add_argument('--output', required=True, help='Output path for a local, uncommitted draft JSON file')
    args = parser.parse_args()
    try:
        adapter = get_provider(args.provider, enabled=True)
        records = list(adapter.fetch())
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if args.provider in OFFER_PROVIDERS:
            # Importing app initialises the local pilot schema, so keep that
            # side effect out of evidence-only provider runs.
            from app import validate_catalogue_feed
            payload = {
                'source': f'{args.provider} provider draft',
                'source_url': getattr(adapter, 'source_url', None),
                'retrieved_at': retrieved_at,
                'products': records,
            }
            products, source, source_url, normalised_retrieved_at = validate_catalogue_feed(payload)
            payload = {
                'source': source, 'source_url': source_url,
                'retrieved_at': normalised_retrieved_at, 'products': products,
            }
        else:
            payload = {
                'provider': args.provider, 'retrieved_at': retrieved_at,
                'records': records,
            }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(json.dumps({'provider': args.provider, 'status': 'completed',
                          'records': len(records), 'output': str(output)}))
        return 0
    except (ProviderNotConfigured, OSError, ValueError) as exc:
        print(f'Provider fetch failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
