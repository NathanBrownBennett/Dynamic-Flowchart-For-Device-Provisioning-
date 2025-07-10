from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import graphviz
import random
from device_scraper import DeviceDataScraper, FALLBACK_DEVICE_DATA

app = Flask(__name__)
form_submitted = False
error_occurred = False
devices = []

# Initialize device scraper
device_scraper = DeviceDataScraper()

# Minimum requirements based on UK government recommendations
minimum_requirements = {
    'category': 'PC',  # Personal Computer/Laptop/Tablet
    'price': 500,      # GBP
    'cpu_speed': 3.0,  # GHz
    'ram': 8,          # GB
    'storage': 256,    # GB
    'screen_size': 9,  # inches
}

def query_database(query, params):
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    print(f"Executing query: {query} with params: {params}")
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    print(f"Query results: {results}")
    return results

def get_image_paths():
    base_path = 'static/images'
    images = [f'{base_path}/{i}.jpg' for i in range(1, 17)]
    return images

def convert_to_dict(devices):
    if not devices:
        return []
    device_list = []
    for device in devices:
        device_dict = {
            'id': device[0],
            'name': device[1],
            'category': device[2],
            'cpu_speed': device[3],
            'ram': device[4],
            'storage': device[5],
            'screen_size': device[6],
            'price': device[7],
            'image': get_device_image_url(device[1])  # Get real device image
        }
        device_list.append(device_dict)
    return device_list

@app.route("/resources")
def resources():
    # Example response with links to educational content
    return jsonify({
        "cybersecurity": "https://www.example.com/cybersecurity-basics",
        "device_security": "https://www.example.com/device-security-best-practices"
    })

@app.route("/", methods=["GET", "POST"])
def index():
    global form_submitted, error_occurred, devices
    light_mode_image = 'static/images/backgrounds/2.jpg'
    dark_mode_image = 'static/images/backgrounds/1.png'
    form_submitted = False
    error_occurred = False
    
    # Fetch recommended devices from the database
    print("Getting recommended devices")
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices')
    recommended_devices = cursor.fetchall()
    conn.close()
    recommended_devices = convert_to_dict(recommended_devices)
    print(f"Recommended devices: {recommended_devices}")
    
    if request.method == 'POST':
        form_submitted = True
        error_occurred = False
        form_data = request.form
        print("Form Submitted. About to search for devices with form data:", form_data)
        
        # Extract form data with defaults
        name = form_data.get('searchBar', '')
        price_range_min = form_data.get('price_range_min', '100')
        price_range_max = form_data.get('price_range_max', '1500')
        cpu_speed = float(form_data.get('cpu_speed', 0))
        ram = int(form_data.get('ram', 0))
        storage = int(form_data.get('storage', 0))
        screen_size = float(form_data.get('screen_size', 0))
        use = form_data.get('use', 'Personal')
        device_type = form_data.get('device_type', '')
        operating_system = form_data.get('operating_system', '')
        brand = form_data.get('brand', '')
        cores = form_data.get('cores', '')
        threads = form_data.get('threads', '')
        ram_generation = form_data.get('ram_generation', '')
        storage_type = form_data.get('storage_type', '')
        
        print(f"Search parameters:")
        print(f"  Name: {name}")
        print(f"  Price Range: {price_range_min} - {price_range_max}")
        print(f"  CPU Speed: {cpu_speed}")
        print(f"  RAM: {ram}")
        print(f"  Storage: {storage}")
        print(f"  Screen Size: {screen_size}")
        print(f"  Use Case: {use}")
        print(f"  Device Type: {device_type}")
        print(f"  Operating System: {operating_system}")
        print(f"  Brand: {brand}")
        print(f"  Cores: {cores}")
        print(f"  Threads: {threads}")
        print(f"  RAM Generation: {ram_generation}")
        print(f"  Storage Type: {storage_type}")
        
        # Build dynamic query based on provided filters
        query_conditions = []
        params = []
        
        # Always include basic filters
        query_conditions.append("name LIKE ?")
        params.append(f'%{name}%')
        
        query_conditions.append("price BETWEEN ? AND ?")
        params.extend([int(price_range_min), int(price_range_max)])
        
        if cpu_speed > 0:
            query_conditions.append("cpu_speed >= ?")
            params.append(cpu_speed)
        
        if ram > 0:
            query_conditions.append("ram >= ?")
            params.append(ram)
        
        if storage > 0:
            query_conditions.append("storage >= ?")
            params.append(storage)
        
        if screen_size > 0:
            query_conditions.append("screen_size >= ?")
            params.append(screen_size)
        
        # Add optional filters if provided
        if device_type:
            query_conditions.append("category LIKE ?")
            params.append(f'%{device_type}%')
        
        if brand:
            query_conditions.append("name LIKE ?")
            params.append(f'%{brand}%')
        
        # Construct final query
        query = f"""
        SELECT * FROM devices 
        WHERE {' AND '.join(query_conditions)}
        ORDER BY 
            CASE 
                WHEN ? = 'Government' THEN (ram + storage/10 + cpu_speed*10)
                WHEN ? = 'Work' THEN (ram + storage/20 + cpu_speed*5)
                ELSE (price * -1)
            END DESC
        LIMIT 20
        """
        params.extend([use, use])
        
        print(f"Query: {query}")
        print(f"Params: {params}")
        
        try:
            devices = query_database(query, params)
            devices = convert_to_dict(devices)
            
            if not devices:
                # Fallback to showing recommended devices with a message
                devices = recommended_devices[:8]  # Show top 8 recommended
                print("No devices found matching criteria, showing recommended devices")
            
        except Exception as e:
            print(f"Database query error: {e}")
            error_occurred = True
            devices = []
        
        print(f"Final devices result: {len(devices)} devices found")
        print(f"Form submission result: form_submitted={form_submitted}, error_occurred={error_occurred}")
        print("Loading Index HTML with sql results")

    return render_template('index.html', recommended_devices=recommended_devices, light_mode_image=light_mode_image, dark_mode_image=dark_mode_image, form_submitted=form_submitted, error_occurred=error_occurred, devices=devices)

@app.route('/device/<int:device_id>')
def device(device_id):
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
    device = cursor.fetchone()
    conn.close()
    
    if device:
        device = convert_to_dict([device])[0]
        
        # Add security features and retailer links
        security_features = enhance_device_data_with_security()
        device['security_features'] = security_features.get(device['category'], {})
        device['retailer_links'] = get_retailer_links(device['name'], device['category'])
        
    print(f"Device details for ID {device_id}: {device}")
    
    # Create flowchart (keeping existing functionality)
    flowchart_image_path = create_flowchart(device, device['category'])
    
    return render_template('device.html', device=device, flowchart_image_path=flowchart_image_path)

def create_flowchart(device, usage):
    dot = graphviz.Digraph(comment='Device Recommendations')
    dot.node('A', f'Device: {device["name"]}')
    dot.node('B', 'Recommended Software')
    dot.node('C', 'Security Measures')
    dot.edges(['AB', 'AC'])

    usage_to_table = {
        'Personal': 'PersonalUseSoftware',
        'Student': 'StudentUseSoftware',
        'Work': 'WorkUseSoftware',
        'Government': 'GovernmentUseSoftware'
    }

    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()

    table_name = usage_to_table.get(usage, 'PersonalUseSoftware')  # Default to PersonalUseSoftware if usage is not found

    query = f"SELECT Software FROM {table_name}"
    cursor.execute(query)

    software_entries = cursor.fetchall()

    for i, entry in enumerate(software_entries, start=1):
        software_node = f'S{i}'
        dot.node(software_node, entry[0])
        dot.edge('B', software_node)

    query = "SELECT * FROM SecurityRecommendations"
    cursor.execute(query)
    security_entries = cursor.fetchall()

    for i, entry in enumerate(security_entries, start=1):
        security_node = f'C{i}'
        dot.node(security_node, entry[1])
        dot.edge('C', security_node)

    image_path = f"static/flowcharts/{device['id']}.svg"
    dot.render(image_path, format='svg', cleanup=True)

    conn.close()

    return image_path + '.svg'

@app.route("/flowchart/<path:image_path>")
def serve_flowchart(image_path):
    return send_file(image_path, mimetype='image/svg+xml')

@app.route("/flowchart")
def flowchart():
    # This route seems to have an issue - removing problematic code
    return "Flowchart functionality moved to device-specific pages"

def populate_database_with_real_data():
    """Populate database with real device data from web sources"""
    try:
        print("Fetching real device data...")
        real_devices = device_scraper.get_real_device_data()
        
        if not real_devices:
            print("Using fallback device data...")
            real_devices = FALLBACK_DEVICE_DATA
        
        conn = sqlite3.connect('devices.db')
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute('DELETE FROM devices')
        
        # Insert real device data
        for device in real_devices:
            cursor.execute('''INSERT INTO devices 
                            (name, category, cpu_speed, ram, storage, screen_size, price) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (device['name'], device['category'], device['cpu_speed'], 
                           device['ram'], device['storage'], device['screen_size'], device['price']))
        
        conn.commit()
        conn.close()
        print(f"Successfully populated database with {len(real_devices)} devices")
        
    except Exception as e:
        print(f"Error populating database: {e}")
        # Use fallback data
        populate_fallback_data()

def populate_fallback_data():
    """Populate database with fallback data if web scraping fails"""
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute('DELETE FROM devices')
    
    # Insert fallback device data
    for device in FALLBACK_DEVICE_DATA:
        cursor.execute('''INSERT INTO devices 
                        (name, category, cpu_speed, ram, storage, screen_size, price) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (device['name'], device['category'], device['cpu_speed'], 
                       device['ram'], device['storage'], device['screen_size'], device['price']))
    
    conn.commit()
    conn.close()
    print(f"Populated database with {len(FALLBACK_DEVICE_DATA)} fallback devices")

def get_device_image_url(device_name):
    """Get a real device image URL or fallback to placeholder"""
    # For now, use local placeholder images to avoid 404 errors
    # In a production environment, you would have proper device images
    
    # Map device types to appropriate placeholder images
    device_name_lower = device_name.lower()
    
    if 'laptop' in device_name_lower or 'book' in device_name_lower:
        return 'static/images/1.jpg'  # Laptop placeholder
    elif 'desktop' in device_name_lower or 'pc' in device_name_lower:
        return 'static/images/2.jpg'  # Desktop placeholder
    elif 'tablet' in device_name_lower or 'ipad' in device_name_lower:
        return 'static/images/3.jpg'  # Tablet placeholder
    elif 'apple' in device_name_lower or 'mac' in device_name_lower:
        return 'static/images/4.jpg'  # Apple device placeholder
    elif 'dell' in device_name_lower:
        return 'static/images/5.jpg'  # Dell placeholder
    elif 'hp' in device_name_lower:
        return 'static/images/6.jpg'  # HP placeholder
    elif 'lenovo' in device_name_lower:
        return 'static/images/7.jpg'  # Lenovo placeholder
    elif 'microsoft' in device_name_lower or 'surface' in device_name_lower:
        return 'static/images/8.jpg'  # Microsoft placeholder
    else:
        # Default to a random placeholder from available images
        base_path = 'static/images'
        image_num = abs(hash(device_name)) % 16 + 1  # Deterministic but varied
        return f'{base_path}/{image_num}.jpg'

# Initialize database with real device data
print("Initializing database with device data...")
populate_fallback_data()  # Use fallback data for immediate testing

@app.route("/refresh-devices", methods=["POST"])
def refresh_devices():
    """Refresh device data from web sources"""
    try:
        print("Refreshing device data from web sources...")
        real_devices = device_scraper.get_real_device_data()
        
        if not real_devices:
            real_devices = FALLBACK_DEVICE_DATA
        
        conn = sqlite3.connect('devices.db')
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute('DELETE FROM devices')
        
        # Insert new device data
        for device in real_devices:
            cursor.execute('''INSERT INTO devices 
                            (name, category, cpu_speed, ram, storage, screen_size, price) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (device['name'], device['category'], device['cpu_speed'], 
                           device['ram'], device['storage'], device['screen_size'], device['price']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully refreshed {len(real_devices)} devices',
            'count': len(real_devices)
        })
        
    except Exception as e:
        print(f"Error refreshing devices: {e}")
        return jsonify({
            'success': False, 
            'message': f'Error refreshing devices: {str(e)}'
        }), 500

@app.route("/compare-devices", methods=["POST"])
def compare_devices():
    """Compare devices based on user criteria"""
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        category = data.get('category')
        price_range = data.get('priceRange')
        performance = data.get('performance')
        
        # Get the current device for comparison
        conn = sqlite3.connect('devices.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
        current_device = cursor.fetchone()
        
        if not current_device:
            return jsonify([])
        
        current_price = current_device[7]  # price is at index 7
        current_cpu = current_device[3]    # cpu_speed is at index 3
        current_category = current_device[2] # category is at index 2
        
        # Build comparison query
        query = "SELECT * FROM devices WHERE id != ?"
        params = [device_id]
        
        # Category filter
        if category == 'same':
            query += " AND category = ?"
            params.append(current_category)
        
        # Price range filter
        if price_range == 'similar':
            query += " AND price BETWEEN ? AND ?"
            params.extend([current_price - 200, current_price + 200])
        elif price_range == 'lower':
            query += " AND price < ?"
            params.append(current_price)
        elif price_range == 'higher':
            query += " AND price > ?"
            params.append(current_price)
        
        # Performance filter
        if performance == 'similar':
            query += " AND cpu_speed BETWEEN ? AND ?"
            params.extend([current_cpu - 0.5, current_cpu + 0.5])
        elif performance == 'higher':
            query += " AND cpu_speed > ?"
            params.append(current_cpu)
        
        query += " LIMIT 6"  # Limit to 6 comparison devices
        
        cursor.execute(query, params)
        comparison_devices = cursor.fetchall()
        conn.close()
        
        # Convert to dict format
        comparison_list = convert_to_dict(comparison_devices)
        
        return jsonify(comparison_list)
        
    except Exception as e:
        print(f"Error in compare_devices: {e}")
        return jsonify([]), 500

def enhance_device_data_with_security():
    """Add security and retailer information to device data"""
    security_features = {
        'Laptops': {
            'encryption': 'BitLocker/FileVault support',
            'authentication': 'Windows Hello/Touch ID',
            'os_security': 'TPM 2.0 chip',
            'network': 'Enterprise Wi-Fi security'
        },
        'Tablet': {
            'encryption': 'Hardware encryption',
            'authentication': 'Biometric authentication',
            'os_security': 'Secure boot',
            'network': 'VPN support'
        },
        'PCs': {
            'encryption': 'Hardware encryption support',
            'authentication': 'Multi-factor authentication',
            'os_security': 'UEFI Secure Boot',
            'network': 'Enterprise network support'
        }
    }
    return security_features

def get_retailer_links(device_name, category):
    """Generate retailer links for purchasing"""
    import urllib.parse
    encoded_name = urllib.parse.quote_plus(device_name)
    
    retailers = {
        'amazon': f"https://amazon.co.uk/s?k={encoded_name}",
        'currys': f"https://currys.co.uk/search?q={encoded_name}",
        'johnlewis': f"https://johnlewis.com/search?search-term={encoded_name}",
    }
    
    # Add category-specific retailers
    if 'Apple' in device_name or 'Mac' in device_name or 'iPad' in device_name:
        retailers['apple'] = f"https://apple.com/uk/shop/buy-{category.lower()}"
    
    if 'Microsoft' in device_name or 'Surface' in device_name:
        retailers['microsoft'] = f"https://microsoft.com/en-gb/store/b/pc?q={encoded_name}"
    
    return retailers

if __name__ == "__main__":
    app.run(debug=True, port=8000)
