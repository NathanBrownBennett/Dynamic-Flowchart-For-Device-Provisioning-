import os
import json
import unittest
from unittest.mock import patch


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {'Content-Length': str(len(payload))}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.payload

    def close(self):
        return None


class ProviderAdapterTests(unittest.TestCase):
    def test_serpapi_adapter_requires_server_side_configuration(self):
        from integrations.providers import ProviderNotConfigured, SerpApiAmazonAdapter
        with patch.dict(os.environ, {'SERPAPI_API_KEY': '', 'SERPAPI_AMAZON_SEARCH_TERM': ''}, clear=False):
            with self.assertRaises(ProviderNotConfigured):
                list(SerpApiAmazonAdapter().fetch())

    def test_serpapi_adapter_normalises_only_safe_amazon_results(self):
        from integrations.providers import SerpApiAmazonAdapter
        payload = b'''{"organic_results":[
            {"asin":"B000000001","title":"Example Secure Laptop","brand":"Example",
             "link":"https://www.amazon.co.uk/dp/B000000001","thumbnail":"https://m.media-amazon.com/images/I/test.jpg",
             "extracted_price":799.99,"stock":"In stock","sponsored":false},
            {"asin":"B000000002","title":"Unsafe link","brand":"Example",
             "link":"http://evil.example/item","extracted_price":1}
        ]}'''
        with patch.dict(os.environ, {'SERPAPI_API_KEY': 'test-only', 'SERPAPI_AMAZON_SEARCH_TERM': 'business laptop'}, clear=False):
            with patch('integrations.providers._public_https_url'), patch(
                'integrations.providers.requests.get', return_value=FakeResponse(payload)
            ):
                records = list(SerpApiAmazonAdapter().fetch())
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['offers'][0]['product_identifier'], 'B000000001')
        self.assertEqual(records[0]['offers'][0]['currency'], 'GBP')
        self.assertNotIn('test-only', json.dumps(records))

    def test_ebay_adapter_uses_oauth_and_normalises_brand_matched_items(self):
        from integrations.providers import EbayBrowseAdapter
        token = FakeResponse(b'{"access_token":"server-token"}')
        results = FakeResponse(b'''{"itemSummaries":[
            {"itemId":"v1|123","title":"Example Laptop","brand":"Example",
             "itemWebUrl":"https://www.ebay.co.uk/itm/123",
             "image":{"imageUrl":"https://i.ebayimg.com/images/g/test/s-l500.jpg"},
             "price":{"value":"499.00","currency":"GBP"},"condition":"New",
             "seller":{"username":"seller-1"}}
        ]}''')
        with patch.dict(os.environ, {'EBAY_CLIENT_ID': 'id-only', 'EBAY_CLIENT_SECRET': 'secret-only',
                                     'EBAY_SEARCH_TERM': 'business laptop'}, clear=False):
            with patch('integrations.providers._public_https_url'), patch(
                'integrations.providers.requests.post', return_value=token
            ) as post, patch('integrations.providers.requests.get', return_value=results):
                records = list(EbayBrowseAdapter().fetch())
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['offers'][0]['seller'], 'seller-1')
        self.assertEqual(records[0]['offers'][0]['price'], 499.0)
        self.assertTrue(post.called)

    def test_osv_adapter_requires_package_identity(self):
        from integrations.providers import OsvAdapter, ProviderNotConfigured
        with patch.dict(os.environ, {'OSV_PACKAGE_NAME': '', 'OSV_ECOSYSTEM': ''}, clear=False):
            with self.assertRaises(ProviderNotConfigured):
                list(OsvAdapter().fetch())

    def test_cisa_adapter_normalises_kev_records_without_credentials(self):
        from integrations.providers import CisaKevAdapter
        payload = b'{"vulnerabilities":[{"cveID":"CVE-2030-0001","vendorProject":"Example","product":"Example OS","shortDescription":"Test issue","dateAdded":"2030-01-01","dueDate":"2030-02-01"}]}'
        with patch('integrations.providers._public_https_url'), patch('integrations.providers.requests.get', return_value=FakeResponse(payload)):
            records = list(CisaKevAdapter().fetch())
        self.assertEqual(records[0]['cve_id'], 'CVE-2030-0001')
        self.assertEqual(records[0]['kev_status'], 'known_exploited')
        self.assertEqual(records[0]['evidence_type'], 'independent_published')
        self.assertNotIn('token', records[0])

    def test_nvd_adapter_requires_one_exact_query(self):
        from integrations.providers import NvdCveAdapter, ProviderNotConfigured
        with patch.dict(os.environ, {'NVD_CPE_NAME': '', 'NVD_KEYWORD_SEARCH': ''}, clear=False):
            with self.assertRaises(ProviderNotConfigured):
                list(NvdCveAdapter().fetch())
        with patch.dict(os.environ, {'NVD_CPE_NAME': 'cpe:2.3:o:example:os:1:*:*:*:*:*:*:*', 'NVD_KEYWORD_SEARCH': 'example'}, clear=False):
            with self.assertRaises(ProviderNotConfigured):
                list(NvdCveAdapter().fetch())


if __name__ == '__main__':
    unittest.main()
