import unittest

from bs4 import BeautifulSoup


class RetailerObservationTests(unittest.TestCase):
    def test_retailer_cards_parse_real_titles_decimal_prices_and_safe_urls(self):
        from device_scraper import DeviceDataScraper

        scraper = DeviceDataScraper()
        amazon = BeautifulSoup('''
            <div data-component-type="s-search-result" data-asin="B012345678">
              <h2><a href="/example-laptop/dp/B012345678"><span>HP Test Laptop, 16GB RAM, 512GB SSD, 14”</span></a></h2>
              <span class="a-price"><span class="a-offscreen">£849.50</span></span>
            </div>
        ''', 'html.parser').div
        amazon_item = scraper.extract_amazon_product_data(amazon)
        self.assertEqual(amazon_item['name'], 'HP Test Laptop, 16GB RAM, 512GB SSD, 14”')
        self.assertEqual(amazon_item['price'], 849.50)
        self.assertEqual(amazon_item['ram'], 16)
        self.assertEqual(amazon_item['storage'], 512)
        self.assertEqual(amazon_item['screen_size'], 14)
        self.assertEqual(amazon_item['product_url'], 'https://www.amazon.co.uk/dp/B012345678')

        john_lewis = BeautifulSoup('''
            <article>
              <a href="/apple-test-laptop/p12345"><span data-testid="product-title">Apple Test Laptop, 8GB RAM, 256GB SSD, 13”</span></a>
              <span data-testid="product-card-price-now">£699.00</span>
            </article>
        ''', 'html.parser').article
        john_lewis_item = scraper.extract_john_lewis_product_data(john_lewis)
        self.assertEqual(john_lewis_item['price'], 699.0)
        self.assertEqual(john_lewis_item['product_url'], 'https://www.johnlewis.com/apple-test-laptop/p12345')
        self.assertEqual(john_lewis_item['image_url'], None)

if __name__ == '__main__':
    unittest.main()
