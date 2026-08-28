import sqlite3
import unittest
from datetime import datetime, timezone

from integrations.quality import profile_catalogue_connection


class CatalogueQualityTests(unittest.TestCase):
    def test_profile_reports_coverage_and_multi_vendor_gap(self):
        connection = sqlite3.connect(':memory:')
        connection.executescript('''
            CREATE TABLE devices (id INTEGER PRIMARY KEY, brand TEXT, model TEXT, variant TEXT,
                mpn TEXT, gtin TEXT, region TEXT, operating_system TEXT);
            CREATE TABLE device_catalogue_metadata (device_id INTEGER, source_url TEXT,
                evidence_url TEXT, source_state TEXT, confidence TEXT, expires_at TEXT, image_license TEXT);
            CREATE TABLE device_offers (device_id INTEGER, vendor TEXT, price REAL, total_price REAL,
                checked_at TEXT, expires_at TEXT);
            CREATE TABLE benchmark_results (device_id INTEGER, score REAL, evidence_type TEXT,
                source_url TEXT, tested_at TEXT);
            CREATE TABLE security_evidence (device_id INTEGER, cve_id TEXT, cpe TEXT,
                source_url TEXT, checked_at TEXT);
            CREATE TABLE support_lifecycle (device_id INTEGER, operating_system TEXT,
                support_until TEXT, source_url TEXT, checked_at TEXT);
        ''')
        current = '2030-01-01T00:00:00+00:00'
        connection.execute('INSERT INTO devices VALUES (1, "Acme", "Model A", NULL, "A-1", NULL, NULL, "Windows 11")')
        connection.execute('INSERT INTO device_catalogue_metadata VALUES (1, "https://manufacturer.example/a", "https://manufacturer.example/a", "reviewed", "medium", ?, "licensed")', (current,))
        connection.executemany('INSERT INTO device_offers VALUES (1, ?, ?, ?, ?, ?)', [
            ('Vendor A', 900, 900, current, current), ('Vendor B', 950, 950, current, current),
        ])
        connection.execute('INSERT INTO benchmark_results VALUES (1, 80, "independent_published", "https://benchmark.example/a", ?)', (current,))
        connection.execute('INSERT INTO security_evidence VALUES (1, "CVE-2030-0001", NULL, "https://nvd.nist.gov/vuln/detail/CVE-2030-0001", ?)', (current,))
        connection.execute('INSERT INTO support_lifecycle VALUES (1, "Windows 11", "2032-01-01T00:00:00+00:00", "https://support.example/a", ?)', (current,))
        report = profile_catalogue_connection(connection, datetime(2029, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(report['schema_state'], 'complete')
        self.assertEqual(report['counts']['products_with_two_current_vendors'], 1)
        self.assertTrue(report['gates']['benchmark_coverage'])
        self.assertTrue(report['gates']['security_evidence_coverage'])
        self.assertTrue(report['gates']['support_lifecycle_coverage'])
        self.assertFalse(report['gates']['product_identity_complete'])
        self.assertFalse(report['release_ready'])
        connection.close()

    def test_profile_fails_closed_when_evidence_tables_are_missing(self):
        connection = sqlite3.connect(':memory:')
        connection.execute('CREATE TABLE devices (id INTEGER PRIMARY KEY)')
        report = profile_catalogue_connection(connection)
        self.assertEqual(report['schema_state'], 'incomplete')
        self.assertFalse(report['release_ready'])
        self.assertIn('benchmark_results', report['missing_tables'])
        connection.close()


if __name__ == '__main__':
    unittest.main()
