"""Create or migrate the configured database without deleting existing data.

Sample catalogue records are deliberately not inserted here. Tests can opt in to
fixtures with ALLOW_SAMPLE_DATA=true; hosted services must load reviewed data via
the protected catalogue import or retailer-observation worker.
"""

from app import app, ensure_database_schema


if __name__ == '__main__':
    ensure_database_schema()
    print(f"Database schema ready: {app.config['DATABASE_PATH']}")
