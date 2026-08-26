import requests
import json
import re
from bs4 import BeautifulSoup
import time
import csv
import os
from urllib.parse import quote_plus, urljoin, urlparse

class LinkValidator:
    """Validates retailer URLs are accessible"""
    def __init__(self, timeout=5, retries=2):
        self.timeout = timeout
        self.retries = retries
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def validate_url(self, url):
        """Check if URL is accessible (returns True/False)"""
        try:
            for attempt in range(self.retries):
                try:
                    response = requests.head(url, timeout=self.timeout, headers=self.headers, allow_redirects=False)
                    return response.status_code < 400  # 2xx, 3xx are valid
                except requests.Timeout:
                    if attempt < self.retries - 1:
                        time.sleep(1)
                    continue
            return False
        except Exception as e:
            print(f"Link validation error for {url}: {e}")
            return False
    
    def validate_retailer_links(self, retailer_links):
        """Validate all retailer links for a device"""
        results = {}
        for retailer, url in retailer_links.items():
            results[retailer] = {
                'url': url,
                'valid': self.validate_url(url)
            }
            time.sleep(0.5)  # Be respectful to servers
        return results


class DeviceDataScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'BStudioB-Device-Provisioning-Toolkit/1.0 (+https://provisioning.bstudiob.co.uk/)'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.link_validator = LinkValidator()
        self.request_timeout = (3, 10)
        self.max_html_bytes = int(os.environ.get('SCRAPER_MAX_HTML_BYTES', '2097152'))
        self.request_delay = max(0.0, min(float(os.environ.get('RETAILER_REQUEST_DELAY_SECONDS', '0.5')), 5.0))

    @staticmethod
    def _price_from_text(value):
        match = re.search(r'£\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)', str(value or ''))
        if not match:
            return None
        try:
            price = float(match.group(1).replace(',', ''))
            return price if price > 0 else None
        except ValueError:
            return None

    @staticmethod
    def _retailer_url(value, base_url, allowed_hosts):
        absolute = urljoin(base_url, str(value or '').strip())
        parsed = urlparse(absolute)
        if (parsed.scheme != 'https' or parsed.username or parsed.password or
                (parsed.hostname or '').lower() not in allowed_hosts):
            return None
        return absolute

    @staticmethod
    def _brand_from_title(title):
        known = ('Acer', 'Apple', 'ASUS', 'Dell', 'Google', 'HP', 'Huawei', 'Lenovo',
                 'Microsoft', 'MSI', 'Samsung')
        lowered = str(title or '').lower()
        for brand in known:
            if re.search(rf'\b{re.escape(brand.lower())}\b', lowered):
                return brand
        first = re.sub(r'[^A-Za-z0-9-]', '', str(title or '').split(' ', 1)[0])
        return first[:80] or 'Unknown'

    @staticmethod
    def _is_device_title(title):
        lowered = str(title or '').lower()
        markers = ('laptop', 'notebook', 'macbook', 'chromebook', 'thinkpad', 'ideapad',
                   'zenbook', 'ipad', 'tablet', 'galaxy tab', 'surface pro', 'desktop',
                   'imac', 'all-in-one', 'gaming pc', 'tower pc', 'mini pc', 'mac mini',
                   'omnidesk')
        return any(marker in lowered for marker in markers)

    def _get_html(self, url):
        """Fetch bounded retailer HTML with no redirect-based trust expansion."""
        response = self.session.get(
            url, timeout=self.request_timeout, allow_redirects=False, stream=True
        )
        response.raise_for_status()
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > self.max_html_bytes:
            response.close()
            raise ValueError('retailer response too large')
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > self.max_html_bytes:
                response.close()
                raise ValueError('retailer response too large')
        response.close()
        return bytes(body)
    
    def load_devices_from_csv(self, csv_file='devices.csv'):
        """Load device data from CSV file"""
        devices = []
        try:
            csv_path = os.path.join(os.path.dirname(__file__), csv_file)
            if not os.path.exists(csv_path):
                print(f"CSV file not found: {csv_path}")
                return devices
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        device = {
                            'name': row['name'],
                            'category': row['category'],
                            'cpu_speed': float(row['cpu_speed']),
                            'ram': int(row['ram']),
                            'storage': int(row['storage']),
                            'screen_size': float(row['screen_size']),
                            'price': int(row['price']),
                            'source': row.get('source', 'CSV database')
                        }
                        devices.append(device)
                    except (ValueError, KeyError) as e:
                        print(f"Error parsing CSV row: {e}")
                        continue
            
            print(f"Successfully loaded {len(devices)} devices from CSV")
            return devices
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return devices

    def scrape_amazon_devices(self, search_terms, max_per_term=5):
        """Observe bounded Amazon UK search results from fixed HTTPS pages."""
        devices = []
        
        for term in search_terms:
            try:
                # Amazon search URL
                search_url = f"https://www.amazon.co.uk/s?k={quote_plus(term)}&ref=nb_sb_noss"
                
                soup = BeautifulSoup(self._get_html(search_url), 'html.parser')
                
                # Find product containers
                products = soup.find_all('div', {'data-component-type': 's-search-result'})
                
                for product in products[:max(1, min(int(max_per_term), 20))]:
                    device_data = self.extract_amazon_product_data(product)
                    if device_data:
                        devices.append(device_data)
                
                if self.request_delay:
                    time.sleep(self.request_delay)
                
            except Exception as e:
                print(f"Error scraping Amazon for {term}: {e}")
                
        return devices

    def extract_amazon_product_data(self, product):
        """Extract individual product data from Amazon product container"""
        try:
            # Product name
            title_elem = product.select_one('h2 a span') or product.select_one('h2 span') or product.find('h2')
            name = title_elem.get_text(' ', strip=True) if title_elem else ''
            if not name or name.startswith('£') or not self._is_device_title(name):
                return None
            
            # Price
            price_elem = product.select_one('span.a-price span.a-offscreen') or product.select_one('span.a-offscreen')
            price = self._price_from_text(price_elem.get_text(' ', strip=True) if price_elem else '')
            if price is None:
                return None

            link_elem = product.select_one('h2 a[href]') or product.select_one('a.a-link-normal[href]')
            product_url = self._retailer_url(
                link_elem.get('href') if link_elem else None,
                'https://www.amazon.co.uk/',
                {'amazon.co.uk', 'www.amazon.co.uk'},
            )
            if not product_url:
                return None
            asin = str(product.get('data-asin') or '').strip().upper()
            if re.fullmatch(r'[A-Z0-9]{10}', asin):
                product_url = f'https://www.amazon.co.uk/dp/{asin}'
            
            # Image
            img_elem = product.find('img', class_='s-image')
            image_url = img_elem.get('src') if img_elem else None
            
            # Category determination
            category = self.determine_category(name)
            
            # Extract specs from title/description
            cpu_speed, ram, storage, screen_size = self.extract_specs_from_text(name, use_defaults=False)
            
            return {
                'name': name[:160],
                'category': category,
                'cpu_speed': cpu_speed,
                'ram': ram,
                'storage': storage,
                'screen_size': screen_size,
                'price': price,
                'image_url': image_url,
                'source': 'Amazon UK',
                'retailer': 'Amazon UK',
                'product_url': product_url,
                'product_identifier': asin or None,
                'brand': self._brand_from_title(name),
                'condition': 'refurbished' if re.search(r'\b(renewed|refurbished|pre-owned)\b', name, re.I) else 'new',
            }
            
        except Exception as e:
            print(f"Error extracting product data: {e}")
            return None

    def scrape_john_lewis_devices(self, search_terms, max_per_term=8):
        """Observe bounded John Lewis search results from fixed HTTPS pages."""
        devices = []
        for term in search_terms:
            try:
                search_url = f"https://www.johnlewis.com/search?search-term={quote_plus(term)}"
                soup = BeautifulSoup(self._get_html(search_url), 'html.parser')
                products = soup.select('article')
                accepted = 0
                for product in products:
                    if accepted >= max(1, min(int(max_per_term), 20)):
                        break
                    device_data = self.extract_john_lewis_product_data(product)
                    if device_data:
                        devices.append(device_data)
                        accepted += 1
                if self.request_delay:
                    time.sleep(self.request_delay)
            except Exception as exc:
                print(f"John Lewis observation failed for {term}: {type(exc).__name__}")
        return devices

    def extract_john_lewis_product_data(self, product):
        """Extract one structured John Lewis product card without guessing values."""
        try:
            title_elem = product.select_one('[data-testid="product-title"]')
            price_elem = product.select_one('[data-testid="product-card-price-now"]')
            link_elem = product.select_one('a[href]')
            name = title_elem.get_text(' ', strip=True) if title_elem else ''
            price = self._price_from_text(price_elem.get_text(' ', strip=True) if price_elem else '')
            product_url = self._retailer_url(
                link_elem.get('href') if link_elem else None,
                'https://www.johnlewis.com/',
                {'johnlewis.com', 'www.johnlewis.com'},
            )
            if not name or price is None or not product_url or not self._is_device_title(name):
                return None
            cpu_speed, ram, storage, screen_size = self.extract_specs_from_text(name, use_defaults=False)
            return {
                'name': name[:160],
                'category': self.determine_category(name),
                'cpu_speed': cpu_speed,
                'ram': ram,
                'storage': storage,
                'screen_size': screen_size,
                'price': price,
                'image_url': None,
                'source': 'John Lewis',
                'retailer': 'John Lewis',
                'product_url': product_url,
                'product_identifier': None,
                'brand': self._brand_from_title(name),
                'condition': 'new',
            }
        except Exception as exc:
            print(f"John Lewis product extraction failed: {type(exc).__name__}")
            return None

    def collect_retailer_observations(self, search_terms, max_per_source=8):
        """Collect a bounded catalogue; individual retailer failures are isolated."""
        observations = []
        collectors = (
            ('Amazon UK', self.scrape_amazon_devices),
            ('John Lewis', self.scrape_john_lewis_devices),
        )
        for retailer, collector in collectors:
            try:
                observations.extend(collector(search_terms, max_per_term=max_per_source))
            except Exception as exc:
                print(f"{retailer} observation failed: {type(exc).__name__}")
        return observations

    def scrape_currys_devices(self, search_terms):
        """Scrape device data from Currys PC World"""
        devices = []
        
        for term in search_terms:
            try:
                search_url = f"https://www.currys.co.uk/search?q={quote_plus(term)}"
                
                soup = BeautifulSoup(self._get_html(search_url), 'html.parser')
                
                # Find product containers
                products = soup.find_all('article', class_=re.compile('product'))
                
                for product in products[:5]:  # Limit to 5 per search
                    device_data = self.extract_currys_product_data(product)
                    if device_data:
                        devices.append(device_data)
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error scraping Currys for {term}: {e}")
                
        return devices

    def extract_currys_product_data(self, product):
        """Extract individual product data from Currys product container"""
        try:
            # Product name
            title_elem = product.find('h3') or product.find('h2')
            name = title_elem.get_text(strip=True) if title_elem else "Unknown Device"
            
            # Price
            price_elem = product.find('span', class_=re.compile('price'))
            price = 0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'£([\d,]+)', price_text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            # Image
            img_elem = product.find('img')
            image_url = img_elem.get('src') if img_elem else None
            
            # Category determination
            category = self.determine_category(name)
            
            # Extract specs from title/description
            cpu_speed, ram, storage, screen_size = self.extract_specs_from_text(name)
            
            return {
                'name': name[:100],
                'category': category,
                'cpu_speed': cpu_speed,
                'ram': ram,
                'storage': storage,
                'screen_size': screen_size,
                'price': price,
                'image_url': image_url,
                'source': 'Currys'
            }
            
        except Exception as e:
            print(f"Error extracting Currys product data: {e}")
            return None

    def determine_category(self, name):
        """Determine device category based on name"""
        name_lower = name.lower()
        
        if any(word in name_lower for word in ['macbook', 'laptop', 'notebook', 'thinkpad', 'ideapad', 'zenbook']):
            return 'Laptops'
        elif any(word in name_lower for word in ['ipad', 'tablet', 'surface pro']):
            return 'Tablet'
        elif any(word in name_lower for word in ['imac', 'desktop', 'pc', 'all-in-one']):
            return 'PCs'
        else:
            return 'Laptops'  # Default to laptops

    def extract_specs_from_text(self, text, use_defaults=True):
        """Extract explicit specifications; live observations use zero for unknowns."""
        text_lower = text.lower()
        
        # CPU Speed
        cpu_speed = 3.0 if use_defaults else 0.0
        cpu_match = re.search(r'(\d+\.?\d*)\s*ghz', text_lower)
        if cpu_match:
            cpu_speed = float(cpu_match.group(1))
        elif use_defaults and ('m1' in text_lower or 'm2' in text_lower or 'm3' in text_lower):
            cpu_speed = 3.2  # Apple Silicon default
        
        # RAM
        ram = 8 if use_defaults else 0
        ram_match = re.search(r'(\d+)\s*gb\s*(?:ram|memory)\b|(?:ram|memory)\s*[:\-]?\s*(\d+)\s*gb\b', text_lower)
        if ram_match:
            ram = int(ram_match.group(1) or ram_match.group(2))
        
        # Storage
        storage = 256 if use_defaults else 0
        storage_match = re.search(r'(\d+(?:\.\d+)?)\s*(tb|gb)\s*(?:ssd|storage|emmc|hdd)\b', text_lower)
        if storage_match:
            amount = float(storage_match.group(1))
            storage = int(amount * 1000 if storage_match.group(2) == 'tb' else amount)
        
        # Screen Size
        screen_size = 13.0 if use_defaults else 0.0
        screen_match = re.search(r'(\d+\.?\d*)\s*["\'”“″]|(\d+\.?\d*)[ -]?inch', text_lower)
        if screen_match:
            screen_size = float(screen_match.group(1) or screen_match.group(2))
        
        return cpu_speed, ram, storage, screen_size

    def get_real_device_data(self):
        """Get real device data from multiple sources (prioritize CSV, fallback to scraping)"""
        # Try CSV first (reliable, doesn't change)
        all_devices = self.load_devices_from_csv('devices.csv')
        
        if all_devices and len(all_devices) > 8:
            print(f"CSV provided {len(all_devices)} devices, using as primary source")
            return all_devices
        
        # Fallback to web scraping if CSV is insufficient
        search_terms = [
            'macbook air laptop',
            'dell xps laptop',
            'lenovo thinkpad laptop',
            'hp pavilion laptop',
            'surface laptop',
            'ipad tablet',
            'samsung galaxy tab',
            'imac desktop',
            'hp desktop pc'
        ]
        
        all_devices = []
        
        # Scrape from Amazon
        print("Scraping Amazon...")
        try:
            amazon_devices = self.scrape_amazon_devices(search_terms)
            all_devices.extend(amazon_devices)
        except Exception as e:
            print(f"Amazon scraping failed: {e}")
        
        # Scrape from Currys (commented out to avoid rate limiting)
        # print("Scraping Currys...")
        # currys_devices = self.scrape_currys_devices(search_terms)
        # all_devices.extend(currys_devices)
        
        return all_devices

    def search_devices_live(self, search_query, max_results=20):
        """
        Perform a fresh live search across retailers for a specific query.
        Returns current market results, not cached database results.
        """
        try:
            print(f"[LIVE SEARCH] Querying for: {search_query}")
            results = []
            
            # Scrape Amazon for this specific query
            search_url = f"https://www.amazon.co.uk/s?k={quote_plus(search_query)}&ref=nb_sb_noss"
            soup = BeautifulSoup(self._get_html(search_url), 'html.parser')
            
            products = soup.find_all('div', {'data-component-type': 's-search-result'})
            
            for product in products[:max_results]:
                try:
                    device_data = self.extract_amazon_product_data(product)
                    if device_data:
                        device_data['retailer'] = 'Amazon UK'
                        device_data['search_query'] = search_query
                        results.append(device_data)
                        print(f"  Found: {device_data['name']} - £{device_data['price']}")
                except Exception as e:
                    print(f"  Error extracting product: {e}")
                    continue
            
            # Also try Currys for better variety
            try:
                currys_url = f"https://www.currys.co.uk/search?q={quote_plus(search_query)}"
                soup = BeautifulSoup(self._get_html(currys_url), 'html.parser')
                products = soup.find_all('article', class_=re.compile('product'))
                
                for product in products[:max_results//2]:  # Get fewer from Currys
                    try:
                        device_data = self.extract_currys_product_data(product)
                        if device_data:
                            device_data['retailer'] = 'Currys'
                            device_data['search_query'] = search_query
                            results.append(device_data)
                            print(f"  Found: {device_data['name']} - £{device_data['price']}")
                    except Exception as e:
                        pass
            except Exception as e:
                print(f"Currys search failed: {e}")
            
            print(f"[LIVE SEARCH] Found {len(results)} results for '{search_query}'")
            return results
            
        except Exception as e:
            print(f"Live search error for '{search_query}': {e}")
            return []

    def get_retailer_current_price(self, device_name, retailer='amazon'):
        """
        Get current price from specific retailer via web scraping.
        Returns price, availability, and link.
        """
        try:
            if retailer.lower() == 'amazon':
                search_url = f"https://www.amazon.co.uk/s?k={quote_plus(device_name)}&ref=nb_sb_noss"
                soup = BeautifulSoup(self._get_html(search_url), 'html.parser')
                
                first_product = soup.find('div', {'data-component-type': 's-search-result'})
                if first_product:
                    price_elem = first_product.find('span', class_='a-price-whole')
                    link_elem = first_product.find('a', class_='a-link-normal')
                    
                    price = 0
                    if price_elem:
                        price_text = price_elem.get_text(strip=True).replace(',', '')
                        price = float(re.findall(r'\d+', price_text)[0]) if re.findall(r'\d+', price_text) else 0
                    
                    link = 'https://www.amazon.co.uk' + link_elem.get('href') if link_elem else None
                    
                    return {
                        'price': price,
                        'link': link,
                        'available': True,
                        'retailer': 'Amazon UK'
                    }
            
            elif retailer.lower() == 'currys':
                search_url = f"https://www.currys.co.uk/search?q={quote_plus(device_name)}"
                soup = BeautifulSoup(self._get_html(search_url), 'html.parser')
                
                first_product = soup.find('article', class_=re.compile('product'))
                if first_product:
                    price_elem = first_product.find('span', class_=re.compile('price'))
                    link_elem = first_product.find('a', class_=re.compile('product-link'))
                    
                    price = 0
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price_match = re.search(r'£([\d,]+)', price_text)
                        price = float(price_match.group(1).replace(',', '')) if price_match else 0
                    
                    link = link_elem.get('href') if link_elem else None
                    
                    return {
                        'price': price,
                        'link': link,
                        'available': True,
                        'retailer': 'Currys'
                    }
            
            return {'price': 0, 'link': None, 'available': False, 'retailer': retailer}
            
        except Exception as e:
            print(f"Error fetching current price from {retailer}: {e}")
            return {'price': 0, 'link': None, 'available': False, 'retailer': retailer, 'error': str(e)}

# Fallback data if scraping fails
FALLBACK_DEVICE_DATA = [
    {
        'name': 'Apple MacBook Air M2',
        'category': 'Laptops',
        'cpu_speed': 3.2,
        'ram': 8,
        'storage': 256,
        'screen_size': 13.6,
        'price': 1149,
        'image_url': 'https://m.media-amazon.com/images/I/71jG+e7roXL._AC_SX679_.jpg',
        'source': 'Apple Store'
    },
    {
        'name': 'Dell XPS 13 Plus',
        'category': 'Laptops',
        'cpu_speed': 4.7,
        'ram': 16,
        'storage': 512,
        'screen_size': 13.4,
        'price': 1299,
        'image_url': 'https://m.media-amazon.com/images/I/61Qe0euJJZL._AC_SX679_.jpg',
        'source': 'Dell'
    },
    {
        'name': 'Lenovo ThinkPad X1 Carbon Gen 11',
        'category': 'Laptops',
        'cpu_speed': 4.9,
        'ram': 16,
        'storage': 512,
        'screen_size': 14.0,
        'price': 1599,
        'image_url': 'https://m.media-amazon.com/images/I/61vFO-RbAjL._AC_SX679_.jpg',
        'source': 'Lenovo'
    },
    {
        'name': 'HP Spectre x360 14',
        'category': 'Laptops',
        'cpu_speed': 4.7,
        'ram': 16,
        'storage': 1000,
        'screen_size': 13.5,
        'price': 1399,
        'image_url': 'https://m.media-amazon.com/images/I/71d5fMkgJ+L._AC_SX679_.jpg',
        'source': 'HP'
    },
    {
        'name': 'Microsoft Surface Laptop 5',
        'category': 'Laptops',
        'cpu_speed': 4.7,
        'ram': 8,
        'storage': 256,
        'screen_size': 13.5,
        'price': 999,
        'image_url': 'https://m.media-amazon.com/images/I/61NmArJTHZL._AC_SX679_.jpg',
        'source': 'Microsoft'
    },
    {
        'name': 'Apple iPad Pro 12.9"',
        'category': 'Tablet',
        'cpu_speed': 3.2,
        'ram': 8,
        'storage': 128,
        'screen_size': 12.9,
        'price': 1079,
        'image_url': 'https://m.media-amazon.com/images/I/81Vf0j4rOKL._AC_SX679_.jpg',
        'source': 'Apple'
    },
    {
        'name': 'Samsung Galaxy Tab S9+',
        'category': 'Tablet',
        'cpu_speed': 3.0,
        'ram': 12,
        'storage': 256,
        'screen_size': 12.4,
        'price': 799,
        'image_url': 'https://m.media-amazon.com/images/I/61HI8rRCMUL._AC_SX679_.jpg',
        'source': 'Samsung'
    },
    {
        'name': 'Apple iMac 24" M3',
        'category': 'PCs',
        'cpu_speed': 3.2,
        'ram': 8,
        'storage': 256,
        'screen_size': 24.0,
        'price': 1299,
        'image_url': 'https://m.media-amazon.com/images/I/61kS8tZKZiL._AC_SX679_.jpg',
        'source': 'Apple'
    },
    {
        'name': 'HP Pavilion All-in-One 27',
        'category': 'PCs',
        'cpu_speed': 3.5,
        'ram': 16,
        'storage': 512,
        'screen_size': 27.0,
        'price': 899,
        'image_url': 'https://m.media-amazon.com/images/I/71X0Yj-xMiL._AC_SX679_.jpg',
        'source': 'HP'
    },
    {
        'name': 'Dell OptiPlex 7000 Tower',
        'category': 'PCs',
        'cpu_speed': 4.4,
        'ram': 16,
        'storage': 512,
        'screen_size': 24.0,
        'price': 799,
        'image_url': 'https://m.media-amazon.com/images/I/51oMI4W4D5L._AC_SX679_.jpg',
        'source': 'Dell'
    }
]
