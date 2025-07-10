import requests
import json
import re
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import quote_plus

class DeviceDataScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def scrape_amazon_devices(self, search_terms):
        """Scrape device data from Amazon search results"""
        devices = []
        
        for term in search_terms:
            try:
                # Amazon search URL
                search_url = f"https://www.amazon.co.uk/s?k={quote_plus(term)}&ref=nb_sb_noss"
                
                response = self.session.get(search_url)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find product containers
                products = soup.find_all('div', {'data-component-type': 's-search-result'})
                
                for i, product in enumerate(products[:5]):  # Limit to 5 per search
                    device_data = self.extract_amazon_product_data(product)
                    if device_data:
                        devices.append(device_data)
                
                # Add delay to be respectful
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error scraping Amazon for {term}: {e}")
                
        return devices

    def extract_amazon_product_data(self, product):
        """Extract individual product data from Amazon product container"""
        try:
            # Product name
            title_elem = product.find('h2', class_='a-size-mini')
            if not title_elem:
                title_elem = product.find('span', class_='a-offscreen')
            name = title_elem.get_text(strip=True) if title_elem else "Unknown Device"
            
            # Price
            price_elem = product.find('span', class_='a-price-whole')
            price = 0
            if price_elem:
                price_text = price_elem.get_text(strip=True).replace(',', '')
                price = float(re.findall(r'\d+', price_text)[0]) if re.findall(r'\d+', price_text) else 0
            
            # Image
            img_elem = product.find('img', class_='s-image')
            image_url = img_elem.get('src') if img_elem else None
            
            # Category determination
            category = self.determine_category(name)
            
            # Extract specs from title/description
            cpu_speed, ram, storage, screen_size = self.extract_specs_from_text(name)
            
            return {
                'name': name[:100],  # Limit name length
                'category': category,
                'cpu_speed': cpu_speed,
                'ram': ram,
                'storage': storage,
                'screen_size': screen_size,
                'price': price,
                'image_url': image_url,
                'source': 'Amazon'
            }
            
        except Exception as e:
            print(f"Error extracting product data: {e}")
            return None

    def scrape_currys_devices(self, search_terms):
        """Scrape device data from Currys PC World"""
        devices = []
        
        for term in search_terms:
            try:
                search_url = f"https://www.currys.co.uk/search?q={quote_plus(term)}"
                
                response = self.session.get(search_url)
                soup = BeautifulSoup(response.content, 'html.parser')
                
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

    def extract_specs_from_text(self, text):
        """Extract technical specifications from product text"""
        text_lower = text.lower()
        
        # CPU Speed
        cpu_speed = 3.0  # Default
        cpu_match = re.search(r'(\d+\.?\d*)\s*ghz', text_lower)
        if cpu_match:
            cpu_speed = float(cpu_match.group(1))
        elif 'm1' in text_lower or 'm2' in text_lower or 'm3' in text_lower:
            cpu_speed = 3.2  # Apple Silicon default
        
        # RAM
        ram = 8  # Default
        ram_match = re.search(r'(\d+)\s*gb.*ram|(\d+)gb.*memory', text_lower)
        if ram_match:
            ram = int(ram_match.group(1) or ram_match.group(2))
        
        # Storage
        storage = 256  # Default
        storage_match = re.search(r'(\d+)\s*gb.*ssd|(\d+)\s*tb.*ssd|(\d+)gb.*storage|(\d+)tb.*storage', text_lower)
        if storage_match:
            if 'tb' in text_lower:
                storage = int((storage_match.group(1) or storage_match.group(2) or storage_match.group(3) or storage_match.group(4))) * 1000
            else:
                storage = int(storage_match.group(1) or storage_match.group(2) or storage_match.group(3) or storage_match.group(4))
        
        # Screen Size
        screen_size = 13.0  # Default
        screen_match = re.search(r'(\d+\.?\d*)\s*["\']|(\d+\.?\d*)-inch', text_lower)
        if screen_match:
            screen_size = float(screen_match.group(1) or screen_match.group(2))
        
        return cpu_speed, ram, storage, screen_size

    def get_real_device_data(self):
        """Get real device data from multiple sources"""
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
        amazon_devices = self.scrape_amazon_devices(search_terms)
        all_devices.extend(amazon_devices)
        
        # Scrape from Currys (commented out to avoid rate limiting)
        # print("Scraping Currys...")
        # currys_devices = self.scrape_currys_devices(search_terms)
        # all_devices.extend(currys_devices)
        
        return all_devices

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
