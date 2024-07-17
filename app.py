from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import graphviz
import random

app = Flask(__name__)
form_submitted = False
error_occurred = False 
devices = []

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
    images = get_image_paths()
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
            'image': random.choice(images)  # Assign a random image to each device
        }
        device_list.append(device_dict)  # Append the dictionary to the list
    return device_list

@app.route("/resources")
def resources():
    # Example response with links to educational content
    return jsonify({
        "cybersecurity": "https://www.example.com/cybersecurity-basics",
        "device_security": "https://www.example.com/device-security-best-practices"
    })

@app.route("/", methods=["GET", "POST"])
def index(form_submitted=form_submitted, error_occurred=error_occurred, devices=devices):
    light_mode_image = 'static/images/backgrounds/2.jpg'
    dark_mode_image = 'static/images/backgrounds/1.png'
    if devices is None:
        devices = []
    # Fetch recommended devices from the database
    print("Getting recommended devices")
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices')
    recommended_devices = cursor.fetchall()
    conn.close()
    recommended_devices = convert_to_dict(recommended_devices)
    print(f"Recommended devices: {recommended_devices}")
    return render_template('index.html', recommended_devices=recommended_devices, light_mode_image=light_mode_image, dark_mode_image=dark_mode_image, form_submitted=form_submitted, error_occurred=error_occurred, devices=devices)

@app.route('/SubmitForm', methods=['POST'])
def SubmitForm():
    # Capture form inputs
    form_data = request.form
    print("Form Submitted. About to search for devices with form data:", form_data)
    
    name = form_data.get('searchBar', '')
    price_range_min = form_data.get('price_range_min', '100')
    price_range_max = form_data.get('price_range_max', '1500')
    cpu_speed = float(form_data.get('cpu_speed', 0))
    ram = int(form_data.get('ram', 0))
    storage = int(form_data.get('storage', 0))
    screen_size = float(form_data.get('screen_size', 0))
    use = form_data.get('use', 'Personal')
    
    print(f"Name: {name}")
    print(f"Price Range: {price_range_min} {price_range_max}")
    print(f"CPU Speed: {cpu_speed}")
    print(f"RAM: {ram}")
    print(f"Storage: {storage}")
    print(f"Screen Size: {screen_size}")
    print(f"Valid usage and table: {use}")
    
    # Adjust query according to your database schema
    query = """
    SELECT * FROM devices 
    WHERE name LIKE ? 
      AND price BETWEEN ? AND ? 
      AND cpu_speed >= ? 
      AND ram >= ? 
      AND storage >= ? 
      AND screen_size >= ?
    """
    params = [f'%{name}%', int(price_range_min), int(price_range_max), cpu_speed, ram, storage, screen_size]
    print(f"Query: {query}")
    print(f"Params: {params}")
    
    devices = query_database(query, params)
    devices = convert_to_dict(devices)
    form_submitted = True
    error_occurred = not bool(devices)
    
    print(f"Devices from query_database: {devices}")
    print(f"Devices: {devices}")
    print(f"({devices}, {form_submitted}, {error_occurred})")
    print("Loading Index HTML with sql results")
    
    return index(form_submitted=form_submitted, error_occurred=error_occurred, devices=devices)

@app.route('/device/<int:device_id>')
def device(device_id):
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
    device = cursor.fetchone()
    conn.close()
    if device:
        device = convert_to_dict([device])[0]
    print(f"Device details for ID {device_id}: {device}")
    
    return render_template('device.html', device=device)

def create_flowchart(device, usage):
    dot = graphviz.Digraph(comment='Device Recommendations')
    dot.node('A', f'Device: {device}')
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

    image_path = f"static/flowcharts/{device[0]}.svg"
    dot.render(image_path, format='svg', cleanup=True)

    conn.close()

    return image_path + '.svg'

@app.route("/flowchart/<path:image_path>")
def serve_flowchart(image_path):
    return send_file(image_path, mimetype='image/svg+xml')

@app.route("/flowchart")
def flowchart():
    devices = device
    dot = create_flowchart(devices)
    return dot._repr_svg_()

if __name__ == "__main__":
    app.run(debug=True, port=8000)
