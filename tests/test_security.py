import os
import tempfile
import unittest
from unittest.mock import patch


class SecurityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        cls.database.close()
        os.environ['DATABASE_PATH'] = cls.database.name
        os.environ['ALLOW_SAMPLE_DATA'] = 'true'
        os.environ['LIVE_DATA_REQUIRED'] = 'false'
        from app import app
        cls.app = app
        cls.app.config.update(TESTING=True, ADMIN_TOKEN='test-token')

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.database.name)

    def test_health_and_baseline_headers(self):
        response = self.app.test_client().get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'ok')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')

    def test_operator_routes_require_bearer_token(self):
        client = self.app.test_client()
        for route in ('/async-refresh', '/refresh-devices', '/validate-links'):
            response = client.post(route, json={'device_name': 'test'})
            self.assertEqual(response.status_code, 401, route)
        response = client.post('/generate-hardening-script', data={'tasks': ['unknown']})
        self.assertEqual(response.status_code, 200)

    def test_image_proxy_rejects_non_allowlisted_urls(self):
        with patch('app.requests.get') as get:
            response = self.app.test_client().get('/api/image-proxy?url=https://127.0.0.1/image.png')
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()

    def test_image_proxy_enforces_content_limit(self):
        class FakeResponse:
            headers = {'Content-Type': 'image/png', 'Content-Length': '6'}

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                return [b'123456']

            def close(self):
                return None

        self.app.config['IMAGE_PROXY_MAX_BYTES'] = 5
        with patch('app._is_public_hostname', return_value=True), patch('app.requests.get', return_value=FakeResponse()):
            response = self.app.test_client().get(
                '/api/image-proxy?url=https://images.unsplash.com/image.png'
            )
        self.assertEqual(response.status_code, 413)

    def test_versioned_api_contract_and_frontend_mount(self):
        client = self.app.test_client()
        health = client.get('/api/v1/healthz')
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json['api_version'], 'v1')

        catalogue = client.get('/api/v1/devices?page_size=2')
        self.assertEqual(catalogue.status_code, 200)
        self.assertLessEqual(len(catalogue.json['items']), 2)
        self.assertIn('live_scraping', catalogue.json)
        self.assertIn('catalogue', catalogue.json['items'][0])
        self.assertIn('source', catalogue.json['items'][0]['catalogue'])
        scores = [item['security']['score'] for item in catalogue.json['items']]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn('ratings', catalogue.json['items'][0])
        self.assertIn('experience', catalogue.json['items'][0])

        status = client.get('/api/v1/catalogue/status')
        self.assertEqual(status.status_code, 200)
        self.assertGreaterEqual(status.json['product_count'], 1)
        self.assertFalse(status.json['live_scraping'])

        source_status = client.get('/api/v1/sources/Local%20development%20fixture/status')
        self.assertEqual(source_status.status_code, 200)
        self.assertIn('status', source_status.json)

        criteria = client.get('/api/v1/criteria')
        self.assertEqual(criteria.status_code, 200)
        self.assertIn('Government', [item['id'] for item in criteria.json['use_cases']])
        self.assertIn('privileged_admin', [item['id'] for item in criteria.json['work_profiles']])

        search = client.post('/api/v1/search', json={'query': 'Mac', 'use_case': 'Work'})
        self.assertEqual(search.status_code, 200)
        self.assertTrue(all('security' in item for item in search.json['items']))

        detail = client.get('/api/v1/devices/1?use_case=Government')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json['api_version'], 'v1')
        self.assertEqual(detail.json['item']['recommendation_context']['use_case'], 'Government')
        self.assertEqual(detail.json['item']['security']['score_version'], 'v2-transparent-heuristic')
        self.assertIn('limitations', detail.json['item']['security'])

        comparisons = client.get('/api/v1/devices/1/comparisons?use_case=Government')
        self.assertEqual(comparisons.status_code, 200)
        self.assertIn('items', comparisons.json)

        frontend = client.get('/app/')
        self.assertEqual(frontend.status_code, 200)
        self.assertIn('<div id="root">', frontend.text)
        frontend.close()

    def test_catalogue_import_is_protected_and_validated(self):
        client = self.app.test_client()
        self.assertEqual(client.post('/admin/catalogue/import', json={}).status_code, 401)
        headers = {'Authorization': 'Bearer test-token'}
        self.assertEqual(client.post('/admin/catalogue/import', headers=headers, json={}).status_code, 400)
        self.assertEqual(client.post('/admin/catalogue/import', headers=headers, json={
            'source': 'Test feed', 'products': [{'name': 'Test'}]
        }).status_code, 400)
        valid, source, source_url, _ = __import__('app').validate_catalogue_feed({
            'source': 'Approved test feed',
            'source_url': 'https://feed-provider.example/catalogue',
            'products': [{
                'name': 'Test Laptop', 'brand': 'TestBrand', 'model': 'Test Laptop', 'category': 'Laptops', 'cpu_speed': 3.2,
                'ram': 16, 'storage': 512, 'screen_size': 14, 'price': 899,
                'availability': 'in_stock',
                'offers': [
                    {'vendor': 'Higher price vendor', 'url': 'https://higher.example/product', 'price': 950,
                     'checked_at': '2026-08-25T00:00:00+00:00'},
                    {'vendor': 'Lower price vendor', 'url': 'https://lower.example/product', 'price': 850,
                     'checked_at': '2026-08-25T00:00:00+00:00'},
                ]
            }]
        })
        self.assertEqual(len(valid), 1)
        self.assertEqual(source, 'Approved test feed')
        self.assertEqual(source_url, 'https://feed-provider.example/catalogue')

        import app as app_module
        original_database = app_module.app.config['DATABASE_PATH']
        temp_database = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_database.close()
        try:
            app_module.app.config['DATABASE_PATH'] = temp_database.name
            app_module.ensure_database_schema()
            response = client.post('/admin/catalogue/import', headers=headers, json={
                'source': 'Approved test feed',
                'source_url': 'https://feed-provider.example/catalogue',
                'products': [{
                    'name': 'Imported Laptop', 'brand': 'Imported', 'model': 'Laptop', 'category': 'Laptops', 'cpu_speed': 3.5,
                    'ram': 32, 'storage': 1024, 'screen_size': 15, 'price': 1199,
                    'availability': 'in_stock',
                    'offers': [
                        {'vendor': 'Higher price vendor', 'url': 'https://higher.example/product', 'price': 1299, 'total_price': 1299},
                        {'vendor': 'Lower price vendor', 'url': 'https://lower.example/product', 'price': 1099, 'total_price': 1099},
                    ]
                }]
            })
            self.assertEqual(response.status_code, 202)
            imported = client.get('/api/v1/devices').json['items'][0]
            self.assertEqual(imported['name'], 'Imported Laptop')
            self.assertEqual(imported['catalogue']['source'], 'Approved test feed')
            self.assertIn('evidence_quality', imported['catalogue'])
            self.assertEqual([offer['price'] for offer in imported['offers']], [1099.0, 1299.0])
            self.assertGreaterEqual(len(imported['security']['score_factors']), 4)
            self.assertIn('experience', imported)
            self.assertIn('ratings', imported)
        finally:
            app_module.app.config['DATABASE_PATH'] = original_database
            os.unlink(temp_database.name)

    def test_production_mode_does_not_bootstrap_or_publish_sample_data(self):
        import app as app_module
        original_database = app_module.app.config['DATABASE_PATH']
        original_sample = app_module.app.config['ALLOW_SAMPLE_DATA']
        original_required = app_module.app.config['LIVE_DATA_REQUIRED']
        database = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        database.close()
        try:
            app_module.app.config.update(DATABASE_PATH=database.name, ALLOW_SAMPLE_DATA=False, LIVE_DATA_REQUIRED=True)
            app_module.ensure_database_schema()
            client = app_module.app.test_client()
            status = client.get('/api/v1/catalogue/status')
            self.assertEqual(status.json['product_count'], 0)
            self.assertEqual(status.json['catalogue_state'], 'empty')
            self.assertEqual(client.get('/api/v1/devices').json['items'], [])
            self.assertEqual(client.get('/api/v1/devices/1').status_code, 404)
            self.assertEqual(client.get('/readyz').status_code, 503)
            self.assertIsNone(app_module.get_device_image_url('Unverified device'))
            self.assertEqual(client.post('/refresh-devices', headers={'Authorization': 'Bearer test-token'}).status_code, 503)
        finally:
            app_module.app.config.update(DATABASE_PATH=original_database, ALLOW_SAMPLE_DATA=original_sample, LIVE_DATA_REQUIRED=original_required)
            os.unlink(database.name)

    def test_provider_contract_is_disabled_without_network_fallback(self):
        from integrations.providers import provider_descriptors
        from integrations.worker import run_provider
        names = {item['name'] for item in provider_descriptors()}
        self.assertIn('icecat', names)
        result = run_provider('amazon_paapi_uk', enabled=False)
        self.assertEqual(result['status'], 'not_configured')
        self.assertEqual(result['item_count'], 0)

    def test_unknown_price_is_not_coerced_to_zero_and_expired_offer_is_hidden(self):
        import app as app_module
        payload = {
            'source': 'Approved test feed',
            'source_url': 'https://feed-provider.example/catalogue',
            'products': [{
                'name': 'Unpriced Laptop', 'brand': 'TestBrand', 'model': 'Unpriced Laptop',
                'category': 'Laptops', 'cpu_speed': 3.0, 'ram': 16, 'storage': 512,
                'screen_size': 14, 'price': None,
                'offers': [
                    {'vendor': 'Expired vendor', 'url': 'https://expired.example/product', 'price': 700,
                     'expires_at': '2020-01-01T00:00:00+00:00'},
                    {'vendor': 'Current vendor', 'url': 'https://current.example/product', 'price': 800,
                     'total_price': 820, 'delivery_price': 20},
                ],
            }],
        }
        products, _, _, _ = app_module.validate_catalogue_feed(payload)
        self.assertIsNone(products[0]['price'])
        original_database = app_module.app.config['DATABASE_PATH']
        database = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        database.close()
        try:
            app_module.app.config['DATABASE_PATH'] = database.name
            app_module.ensure_database_schema()
            app_module.replace_catalogue(products, feed_source='Approved test feed')
            item = app_module.app.test_client().get('/api/v1/devices').json['items'][0]
            self.assertIsNone(item['price'])
            self.assertEqual(len(item['offers']), 1)
            self.assertEqual(item['offers'][0]['vendor'], 'Current vendor')
            self.assertEqual(item['offers'][0]['total_price'], 820.0)
        finally:
            app_module.app.config['DATABASE_PATH'] = original_database
            os.unlink(database.name)

    def test_graphviz_is_optional_for_flowchart_generation(self):
        import app as app_module
        original_folder = app_module.app.static_folder
        original_graphviz = app_module.graphviz
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app_module.app.static_folder = temp_dir
                app_module.graphviz = None
                output = app_module.create_flowchart({'id': 99991, 'name': 'Fallback Test Device'}, 'Work')
                self.assertTrue(os.path.isfile(output))
        finally:
            app_module.graphviz = original_graphviz
            app_module.app.static_folder = original_folder

    def test_showcase_is_explicitly_invite_only(self):
        showcase_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'showcase', 'index.html')
        with open(showcase_path, encoding='utf-8') as handle:
            showcase = handle.read()
        self.assertIn('invite-only pilot', showcase)
        self.assertIn('does not', showcase)
        self.assertNotIn('/admin/', showcase)


if __name__ == '__main__':
    unittest.main()
