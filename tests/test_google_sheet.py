import unittest
from unittest.mock import patch

from integrations.google_sheet import (
    GoogleSheetNotConfigured,
    csv_to_feed,
    fetch_public_csv,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.headers = {'Content-Length': str(len(payload))}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError('http error')

    def iter_content(self, chunk_size):
        yield self.payload

    def close(self):
        pass


class GoogleSheetTests(unittest.TestCase):
    def test_csv_to_feed_maps_catalogue_and_nested_evidence_columns(self):
        csv_text = '''name,brand,model,category,cpu_speed,ram,storage,screen_size,price,operating_system,source_state,source_url,offers_json,benchmarks_json,security_evidence_json,support_lifecycle_json
Secure Laptop,Example,Secure Laptop,Laptops,3.2,16,512,14,799,Windows 11,reviewed,https://vendor.example/product,"[{""vendor"":""Vendor A"",""url"":""https://vendor.example/product"",""price"":799}]","[{""suite"":""ExampleBench"",""score"":80}]",[],"{""operating_system"":""Windows 11""}"
'''
        feed = csv_to_feed(csv_text, 'BStudioB reviewed catalogue', 'https://docs.google.com/spreadsheets/d/id/export?format=csv')
        self.assertEqual(feed['products'][0]['brand'], 'Example')
        self.assertEqual(feed['products'][0]['offers'][0]['vendor'], 'Vendor A')
        self.assertEqual(feed['products'][0]['benchmarks'][0]['score'], 80)
        self.assertEqual(feed['products'][0]['support_lifecycle']['operating_system'], 'Windows 11')

    def test_fetch_rejects_non_google_hosts_before_network_call(self):
        with patch('integrations.google_sheet.requests.get') as get:
            with self.assertRaises(GoogleSheetNotConfigured):
                fetch_public_csv('https://example.invalid/spreadsheets/d/id/export?format=csv')
        get.assert_not_called()

    def test_fetch_does_not_follow_redirects_and_enforces_size(self):
        payload = b'name,brand,model,category\nLaptop,Example,Model,Laptops\n'
        with patch('integrations.google_sheet.requests.get', return_value=FakeResponse(payload)) as get:
            result = fetch_public_csv('https://docs.google.com/spreadsheets/d/id/export?format=csv')
        self.assertIn('Laptop', result)
        self.assertEqual(get.call_args.kwargs['allow_redirects'], False)
        self.assertEqual(get.call_args.kwargs['stream'], True)

        with patch('integrations.google_sheet.requests.get', return_value=FakeResponse(b'x' * 65537)):
            with self.assertRaises(ValueError):
                fetch_public_csv('https://docs.google.com/spreadsheets/d/id/export?format=csv', max_bytes=65536)

    def test_csv_rejects_duplicate_headers_and_missing_required_columns(self):
        with self.assertRaises(ValueError):
            csv_to_feed('name,name,brand,model,category\nA,A,B,C,D\n', 'Source', 'https://docs.google.com/spreadsheets/d/id/export')
        with self.assertRaises(ValueError):
            csv_to_feed('name,brand,model\nA,B,C\n', 'Source', 'https://docs.google.com/spreadsheets/d/id/export')

    def test_empty_optional_support_lifecycle_is_absent_not_invalid(self):
        csv_text = 'name,brand,model,category,source_url\nLaptop,Example,Model,Laptops,https://vendor.example/product\n'
        feed = csv_to_feed(csv_text, 'Source', 'https://docs.google.com/spreadsheets/d/id/export')
        self.assertIsNone(feed['products'][0]['support_lifecycle'])

if __name__ == '__main__':
    unittest.main()
