#!/usr/bin/env python3
"""Read-only catalogue completeness and evidence-quality report."""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.quality import profile_catalogue_connection


def main():
    parser = argparse.ArgumentParser(description='Profile catalogue evidence without modifying the database')
    parser.add_argument('--database', default=os.environ.get('DATABASE_PATH', 'devices.db'))
    parser.add_argument('--json', action='store_true', dest='as_json')
    parser.add_argument('--strict', action='store_true', help='exit 2 if all release gates are not met')
    args = parser.parse_args()
    try:
        connection = sqlite3.connect(args.database)
        report = {
            'database': os.path.abspath(args.database),
            'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            **profile_catalogue_connection(connection),
        }
        connection.close()
    except (OSError, sqlite3.Error) as exc:
        print(f'Catalogue profile failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Catalogue: {report['database']}")
        print(f"Schema: {report['schema_state']} · release gates: {'PASS' if report['release_ready'] else 'NOT READY'}")
        for name, value in report.get('counts', {}).items():
            print(f'  {name}: {value}')
        for issue in report.get('issues', []):
            print(f'  issue: {issue}')
    return 2 if args.strict and not report['release_ready'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
