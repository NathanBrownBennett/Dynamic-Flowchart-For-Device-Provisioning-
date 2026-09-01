import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        cls.app.config.update(TESTING=True, ADMIN_TOKEN='test-token', PUBLIC_RATE_LIMIT=10000)

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
        self.assertEqual(response.status_code, 400)

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
                '/api/image-proxy?url=https://media.johnlewiscontent.com/image.png'
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
        self.assertEqual(detail.json['item']['security']['score_version'], 'v3-evidence-gated-readiness')
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
            self.assertEqual(imported['security']['score'], None)
            self.assertEqual(imported['security']['rating_state'], 'unrated_insufficient_evidence')
            self.assertEqual(imported['security']['rating_basis'], 'not_scored')
            self.assertEqual(imported['benchmark']['rating_basis'], 'not_scored')
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
        original_observation = app_module.app.config['ENABLE_LIVE_SCRAPING']
        database = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        database.close()
        try:
            app_module.app.config.update(DATABASE_PATH=database.name, ALLOW_SAMPLE_DATA=False,
                                         LIVE_DATA_REQUIRED=True, ENABLE_LIVE_SCRAPING=False)
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
            app_module.app.config.update(DATABASE_PATH=original_database, ALLOW_SAMPLE_DATA=original_sample,
                                         LIVE_DATA_REQUIRED=original_required, ENABLE_LIVE_SCRAPING=original_observation)
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
                     'checked_at': '2019-12-31T00:00:00+00:00',
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

    def test_observation_refresh_is_current_sorted_and_preserves_data_on_failure(self):
        import app as app_module

        original = {
            key: app_module.app.config[key]
            for key in ('DATABASE_PATH', 'ALLOW_SAMPLE_DATA', 'ENABLE_LIVE_SCRAPING', 'LIVE_DATA_REQUIRED')
        }
        database = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        database.close()
        observations = [
            {
                'name': 'Apple Test Laptop, 8GB RAM, 256GB SSD, 13”', 'brand': 'Apple',
                'category': 'Laptops', 'cpu_speed': 0, 'ram': 8, 'storage': 256,
                'screen_size': 13, 'price': 799, 'retailer': 'Amazon UK',
                'product_url': 'https://www.amazon.co.uk/dp/B012345678',
                'image_url': 'https://m.media-amazon.com/images/I/test-device.jpg',
                'product_identifier': 'B012345678', 'condition': 'new',
            },
            {
                'name': 'Apple Test Laptop, 8GB RAM, 256GB SSD, 13”', 'brand': 'Apple',
                'category': 'Laptops', 'cpu_speed': 0, 'ram': 8, 'storage': 256,
                'screen_size': 13, 'price': 699, 'retailer': 'John Lewis',
                'product_url': 'https://www.johnlewis.com/apple-test-laptop/p12345',
                'condition': 'new',
            },
        ]
        try:
            app_module.app.config.update(
                DATABASE_PATH=database.name, ALLOW_SAMPLE_DATA=False,
                ENABLE_LIVE_SCRAPING=False, LIVE_DATA_REQUIRED=True,
            )
            app_module.ensure_database_schema()
            result = app_module.refresh_retailer_observation_catalogue(observations)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['item_count'], 1)

            client = app_module.app.test_client()
            status = client.get('/api/v1/catalogue/status').json
            self.assertEqual(status['catalogue_state'], 'current')
            self.assertEqual(status['catalogue_mode'], 'retailer_observation')
            self.assertEqual(status['source_states']['observed'], 1)
            item = client.get('/api/v1/devices').json['items'][0]
            self.assertEqual(item['catalogue']['source_state'], 'observed')
            self.assertEqual(item['data_quality']['price_state'], 'observed')
            self.assertEqual(item['os'], 'Unknown')
            self.assertIsNone(item['security']['score'])
            self.assertEqual(item['security']['level'], 'Unrated')
            self.assertIsNone(item['benchmark']['overall_index'])
            self.assertEqual([offer['total_price'] for offer in item['offers']], [699.0, 799.0])
            self.assertTrue(all(not offer['total_price_complete'] for offer in item['offers']))
            cached_search = client.post('/search-live', json={'query': 'Test Laptop', 'max_results': 10})
            self.assertEqual(cached_search.status_code, 200)
            self.assertEqual(cached_search.json['total_found'], 1)
            cheapest = client.post('/get-current-price', json={'device_name': 'Apple Test Laptop'})
            self.assertEqual(cheapest.status_code, 200)
            self.assertEqual(cheapest.json['retailer'], 'John Lewis')
            self.assertEqual(cheapest.json['total_price'], 699.0)
            self.assertTrue(item['image'].startswith('/api/image-proxy?url='))
            conn = __import__('sqlite3').connect(database.name)
            self.assertEqual(
                conn.execute('SELECT image_url FROM devices LIMIT 1').fetchone()[0],
                'https://m.media-amazon.com/images/I/test-device.jpg',
            )
            conn.close()

            failed = app_module.refresh_retailer_observation_catalogue([])
            self.assertEqual(failed['status'], 'no_results')
            self.assertEqual(client.get('/api/v1/catalogue/status').json['product_count'], 1)
        finally:
            app_module.app.config.update(**original)
            os.unlink(database.name)

    def test_feed_dates_assertions_and_hardening_input_are_constrained(self):
        import app as app_module
        with self.assertRaises(ValueError):
            app_module.validate_catalogue_feed({
                'source': 'Bad date feed', 'retrieved_at': 'not-a-date',
                'products': [{'name': 'Device', 'brand': 'Brand', 'model': 'Model', 'category': 'Laptops'}],
            })
        products, _, _, _ = app_module.validate_catalogue_feed({
            'source': 'Operator feed', 'source_url': 'https://provider.example/catalogue',
            'products': [{
                'name': 'Device', 'brand': 'Brand', 'model': 'Model', 'category': 'Laptops',
                'source_state': 'verified', 'confidence': 'high', 'evidence_quality': 'independent',
            }],
        })
        self.assertEqual(products[0]['source_state'], 'reviewed')
        self.assertEqual(products[0]['confidence'], 'medium')
        self.assertEqual(products[0]['evidence_quality'], 'reviewed')
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        with self.assertRaisesRegex(ValueError, 'future'):
            app_module.validate_catalogue_feed({
                'source': 'Future feed', 'retrieved_at': future,
                'products': [{'name': 'Device', 'brand': 'Brand', 'model': 'Model', 'category': 'Laptops'}],
            })
        with self.assertRaisesRegex(ValueError, 'freshness window'):
            app_module.validate_catalogue_feed({
                'source': 'Bad window feed', 'retrieved_at': app_module._utc_now(),
                'products': [{
                    'name': 'Device', 'brand': 'Brand', 'model': 'Model', 'category': 'Laptops',
                    'price_checked_at': '2026-08-25T00:00:00+00:00',
                    'expires_at': '2026-08-24T00:00:00+00:00',
                }],
            })
        client = self.app.test_client()
        injected = client.post('/generate-hardening-script', data={
            'os': 'Windows 11\nWrite-Output injected', 'tasks': ['enforce_firewall'],
            'device_id': '1\r\nunsafe.txt',
        })
        self.assertEqual(injected.status_code, 400)
        normalized_bypass = client.post('/generate-hardening-script', data={
            'os': 'Windows 11', 'tasks': ['enforce firewall!!!'], 'device_id': '12',
        })
        self.assertEqual(normalized_bypass.status_code, 400)
        padded_os = client.post('/generate-hardening-script', data={
            'os': ' Windows 11 ', 'tasks': ['enforce_firewall'], 'device_id': '12',
        })
        self.assertEqual(padded_os.status_code, 400)
        duplicate = client.post('/generate-hardening-script', data={
            'os': 'Windows 11', 'tasks': ['enforce_firewall', 'enforce_firewall'], 'device_id': '12',
        })
        self.assertEqual(duplicate.status_code, 400)
        valid = client.post('/generate-hardening-script', data={
            'os': 'Windows 11', 'tasks': ['enforce_firewall'], 'device_id': '12',
        })
        self.assertEqual(valid.status_code, 200)
        self.assertIn('filename=hardening_device_12.ps1', valid.headers['Content-Disposition'])
        self.assertNotIn('injected', valid.text)
        unsafe_filename = client.post('/generate-hardening-script', data={
            'os': 'Windows 11', 'tasks': ['enforce_firewall'], 'device_id': '١٢',
        })
        self.assertEqual(unsafe_filename.status_code, 200)
        self.assertIn('filename=hardening_device_unknown.ps1', unsafe_filename.headers['Content-Disposition'])
        evidence = [{'cve_id': 'CVE-TEST-1', 'fixed_version': '2.0', 'source_url': 'https://security.example/cve'}]
        support = {'support_until': '2030-01-01'}
        low_spec = {'cpu_speed': 1.0, 'ram': 4, 'storage': 64}
        high_spec = {'cpu_speed': 5.0, 'ram': 128, 'storage': 4096}
        low_score = app_module.compute_security_score(
            low_spec, 'Windows 11', 'Intel', 'Personal', evidence, support
        )[0]
        high_score = app_module.compute_security_score(
            high_spec, 'Windows 11', 'Intel', 'Personal', evidence, support
        )[0]
        self.assertEqual(low_score, high_score)

    def test_live_security_score_requires_explicit_matching_operating_system(self):
        import app as app_module
        device = {
            'id': 901, 'name': 'Example Windows 11 Laptop', 'category': 'Laptops',
            'cpu_speed': 3.2, 'ram': 16, 'storage': 512, 'screen_size': 14,
            'price': 900, 'source_state': 'reviewed',
        }
        evidence = {901: [{
            'provider': 'Example security source', 'cve_id': 'CVE-2026-0001',
            'source_url': 'https://security.example/CVE-2026-0001',
            'checked_at': app_module._utc_now(),
        }]}
        support = {901: {
            'operating_system': 'Windows 11', 'support_until': '2030-01-01',
            'source_url': 'https://support.example/windows-11',
            'checked_at': app_module._utc_now(),
        }}
        inferred_only = app_module.apply_rule_engine(
            [device], 'Personal', security_evidence_by_id=evidence, support_by_id=support,
        )[0]
        self.assertIsNone(inferred_only['security']['score'])
        self.assertFalse(inferred_only['evidence_completeness']['explicit_operating_system'])

        explicit = dict(device, operating_system='Windows 11')
        rated = app_module.apply_rule_engine(
            [explicit], 'Personal', security_evidence_by_id=evidence, support_by_id=support,
        )[0]
        self.assertIsNotNone(rated['security']['score'])
        self.assertTrue(rated['evidence_completeness']['explicit_operating_system'])

        mismatched_support = dict(support)
        mismatched_support[901] = dict(support[901], operating_system='Linux')
        mismatch = app_module.apply_rule_engine(
            [explicit], 'Personal', security_evidence_by_id=evidence, support_by_id=mismatched_support,
        )[0]
        self.assertIsNone(mismatch['security']['score'])

        unattributed = {901: [dict(evidence[901][0], source_url=None)]}
        missing_attribution = app_module.apply_rule_engine(
            [explicit], 'Personal', security_evidence_by_id=unattributed, support_by_id=support,
        )[0]
        self.assertIsNone(missing_attribution['security']['score'])

    def test_operator_evidence_requires_attribution_and_loses_high_trust(self):
        import app as app_module
        checked_at = app_module._utc_now()
        product = {
            'name': 'Evidence Laptop', 'brand': 'Evidence', 'model': 'Laptop',
            'category': 'Laptops', 'operating_system': 'Windows 11',
            'benchmarks': [{
                'suite': 'Example suite', 'score': 80, 'evidence_type': 'measured',
                'source_url': 'https://benchmarks.example/results/1',
                'tested_at': checked_at, 'confidence': 'high',
            }],
            'security_evidence': [{
                'provider': 'Example security source', 'cve_id': 'CVE-2026-0001',
                'source_url': 'https://security.example/CVE-2026-0001',
                'checked_at': checked_at, 'confidence': 'high',
            }],
            'support_lifecycle': {
                'operating_system': 'Windows 11', 'support_until': '2030-01-01T00:00:00+00:00',
                'source_url': 'https://support.example/windows-11',
                'checked_at': checked_at, 'confidence': 'high',
            },
        }
        products, _, _, _ = app_module.validate_catalogue_feed({
            'source': 'Operator evidence feed', 'retrieved_at': checked_at, 'products': [product],
        })
        self.assertEqual(products[0]['benchmarks'][0]['confidence'], 'medium')
        self.assertEqual(products[0]['security_evidence'][0]['confidence'], 'medium')
        self.assertEqual(products[0]['support_lifecycle']['confidence'], 'medium')

        missing_source = dict(product)
        missing_source['security_evidence'] = [dict(product['security_evidence'][0], source_url=None)]
        with self.assertRaisesRegex(ValueError, 'security source_url'):
            app_module.validate_catalogue_feed({
                'source': 'Unattributed evidence feed', 'retrieved_at': checked_at,
                'products': [missing_source],
            })

    def test_catalogue_bulk_loads_only_the_selected_sql_page(self):
        import app as app_module
        filters = app_module._api_filters({'page': 1, 'page_size': 2})
        with patch('app._catalogue_metadata_map', return_value={}) as metadata, \
                patch('app._vendor_offers_map', return_value={}) as offers, \
                patch('app._evidence_map', return_value={}) as evidence, \
                patch('app._support_map', return_value={}) as support:
            items, total = app_module._api_catalogue(filters)
        self.assertGreater(total, 2)
        self.assertEqual(len(items), 2)
        selected_ids = [item['id'] for item in items]
        metadata.assert_called_once_with(selected_ids)
        offers.assert_called_once_with(selected_ids)
        self.assertEqual(evidence.call_count, 2)
        self.assertTrue(all(call.args[1] == selected_ids for call in evidence.call_args_list))
        support.assert_called_once_with(selected_ids)

    def test_legacy_detail_redirects_without_rendering_graphviz(self):
        with patch('app.create_flowchart') as flowchart:
            response = self.app.test_client().get('/device/1')
        self.assertEqual(response.status_code, 308)
        self.assertEqual(response.headers['Location'], '/#device/1')
        flowchart.assert_not_called()

    def test_partial_retailer_refresh_preserves_fuller_catalogue(self):
        import app as app_module
        original = {key: app_module.app.config[key] for key in ('DATABASE_PATH', 'ALLOW_SAMPLE_DATA')}
        database = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        database.close()
        try:
            app_module.app.config.update(DATABASE_PATH=database.name, ALLOW_SAMPLE_DATA=False)
            app_module.ensure_database_schema()
            observations = [{
                'name': f'Brand Laptop {number}, 16GB RAM, 512GB SSD', 'brand': 'Brand',
                'category': 'Laptops', 'ram': 16, 'storage': 512, 'price': 800 + number,
                'retailer': 'John Lewis',
                'product_url': f'https://www.johnlewis.com/brand-laptop-{number}/p{number}',
            } for number in range(1, 5)]
            self.assertEqual(app_module.refresh_retailer_observation_catalogue(observations)['status'], 'completed')
            before = [item['name'] for item in app_module.app.test_client().get('/api/v1/devices').json['items']]
            with patch('app.replace_catalogue', wraps=app_module.replace_catalogue) as replace:
                partial = app_module.refresh_retailer_observation_catalogue(observations[:1])
            self.assertEqual(partial['status'], 'partial_results')
            self.assertEqual(app_module.app.test_client().get('/api/v1/catalogue/status').json['product_count'], 4)
            self.assertEqual(
                [item['name'] for item in app_module.app.test_client().get('/api/v1/devices').json['items']],
                before,
            )
            replace.assert_not_called()
        finally:
            app_module.app.config.update(**original)
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
