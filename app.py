from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import graphviz

app = Flask(__name__)
form_submitted = False
error_occurred = False 
devices=[]
# Minimum requirements based on UK government recommendations
minimum_requirements = {
    'category': 'PC', # Personal Computer/Laptop/Tablet
    'price': 500,      # GBP
    'cpu_speed': 3.0,  # GHz
    'ram': 8,          # GB
    'storage': 256,     # GB
    'screen_size': 9,  # inches
}

def getRecommendedDevices():
    i = 1
    print("Getting recommended devices")
    devices = filter_devices()
    all_devices = [
            {"id": device[0], "name": device[1], "category": device[2], "cpu_speed": device[3], 
             "ram": device[4], "storage": device[5], "screen_size": device[6], "price": device[7]}
            for device in devices
        ]
    recommended_devices = []
    for device in all_devices:
        if i > 16:
            i = 1
        recommended_devices.append({
            'image': f"static/images/{i}.jpg",
            'id': device['id'],
            'name': device['name'], 
            'category': device['category'], 
            'cpu_speed': device['cpu_speed'], 
            'ram': device['ram'], 
            'storage': device['storage'], 
            'screen_size': device['screen_size'], 
            'price': device['price']
    })
        i+= 1
    return recommended_devices

def query_database(query, params):
    print("Querying database")
    devices = []
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    devices = cursor.fetchall()
    conn.close()
    print("Devices from query_database:", devices)
    return devices

def filter_devices(searchBar=None, category=None, price_range=None, specs=None):
    conn = sqlite3.connect('devices.db')
    c = conn.cursor()
    conditions = []
    params = []

    if searchBar:
        conditions.append("name LIKE ?")
        params.append(f"%{searchBar}%")
    if category:
        conditions.append("category = ?")
        params.append(category)
    if price_range:
        conditions.append("price BETWEEN ? AND ?")
        params.extend(price_range)  # Assuming price_range is a tuple (min_price, max_price)
    if specs:
        # Adjusting the query to include specs filtering
        if specs.get('cpu_speed'):
            conditions.append("cpu_speed >= ?")
            params.append(specs['cpu_speed'])
        if specs.get('ram'):
            conditions.append("ram >= ?")
            params.append(specs['ram'])
        if specs.get('storage'):
            conditions.append("storage >= ?")
            params.append(specs['storage'])
        if specs.get('screen_size'):
            conditions.append("screen_size >= ?")
            params.append(specs['screen_size'])

    query = "SELECT * FROM devices"
    if conditions != []:
        query += " WHERE " + " AND ".join(conditions)
    print(query)
    print(params)
    c.execute(query, params)
    devices = c.fetchall()
    conn.close()
    return devices

@app.route("/resources")
def resources():
    # Example response with links to educational content
    return jsonify({
        "cybersecurity": "https://www.example.com/cybersecurity-basics",
        "device_security": "https://www.example.com/device-security-best-practices"
    })
    
@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    # Example implementation for feedback submission
    feedback = request.form.get("feedback")
    # Process and store feedback
    return jsonify({"status": "success", "message": "Thank you for your feedback!"})

@app.route("/", methods=["GET", "POST"])
def index(form_submitted=form_submitted, error_occurred=error_occurred, devices=devices):
    light_mode_image = 'static/images/backgrounds/2.jpg'
    dark_mode_image = 'static/images/backgrounds/1.png'
    recommended_devices = []
    recommended_devices = getRecommendedDevices()
    if devices == []:
        form_submitted = False
        error_occurred = False
        usage = ''
        if recommended_devices == []:
            print("No devices found")
            error_occurred = True
            return render_template("index.html", recommended_devices=recommended_devices, light_mode_image=light_mode_image, dark_mode_image=dark_mode_image, form_submitted=form_submitted, error_occurred=error_occurred, devices=devices)

        if request.method == "POST" and request.path == "/SubmitForm":
            devices, form_submitted, error_occurred = SubmitForm(usage)

        return render_template("index.html", recommended_devices=recommended_devices, light_mode_image=light_mode_image, dark_mode_image=dark_mode_image, form_submitted=form_submitted, error_occurred=error_occurred, devices=devices)
    return render_template("index.html", recommended_devices=recommended_devices, light_mode_image=light_mode_image, dark_mode_image=dark_mode_image, form_submitted=form_submitted, error_occurred=error_occurred, devices=devices)

@app.route("/SubmitForm", methods=["GET", "POST"])
def SubmitForm():
    usage = request.form.get("use", '')
    print("Form Submitted. About to search for devices with usage:",usage)
    devices = []
    devices = search_devices(usage)
    print(devices)
    form_submitted = True
    error_occurred = False
    print("Loading Index HTML with sql results")
    return index(form_submitted=form_submitted, error_occurred=error_occurred, devices=devices)

def search_devices(usage):
    print("Searching for Devices with usage:", usage)
    form_submitted = True
    error_occurred = False
    name = request.form.get('searchBar', '%')  # Default to '%' if searchBar is empty
    print("Name:", name)
    price_range = request.form.get('price_range', '0,0').split(',')
    min_price, max_price = (int(price_range[0]), int(price_range[1])) if len(price_range) == 2 else (0, 0)
    print("Price Range:", min_price, max_price)
    cpu_speed = float(request.form.get('cpu_speed', 0))
    print("CPU Speed:", cpu_speed)
    ram = int(request.form.get('ram', 0))
    print("RAM:", ram)
    storage = int(request.form.get('storage', 0))
    print("Storage:", storage)
    screen_size = float(request.form.get('screen_size', 0))
    print("Screen Size:", screen_size)

    valid_usages = ['Personal', 'Student', 'Work', 'Government']
    if usage not in valid_usages:
        print(f"Invalid usage: {usage}")
        return [], form_submitted, True
    else:
        print(f"Valid usage and table: {usage}")

    query = f"SELECT * FROM {usage} WHERE name LIKE ? AND price BETWEEN ? AND ? AND cpu_speed >= ? AND ram >= ? AND storage >= ? AND screen_size >= ?"
    print("Query:", query)
    params = [name, min_price, max_price, cpu_speed, ram, storage, screen_size]
    print("Params:", params)

    try:
        devices = query_database(query, params)
        print("Devices:", devices)
        return devices, form_submitted, error_occurred
    except sqlite3.OperationalError as e:
        print(f"SQL Error: {e}")
        devices = []
        error_occurred = True
        return devices, form_submitted, error_occurred

@app.route("/device/<int:device_id>")
def device(device_id):
    usage = request.form.get("usage", '')
    print("loading device page with id:",device_id)
    conn = sqlite3.connect('devices.db')
    c = conn.cursor()
    c.execute("SELECT * FROM devices WHERE id=?", (device_id,))
    device = c.fetchall()
    flowchart = create_flowchart(device, usage=usage)
    images = [f"static/images/{i}.jpg" for i in range(1, 17)]
    conn.close()
    
    if device:
        flowchart_image_path = create_flowchart(device, usage)  # Assuming the third column is 'usage'
        return render_template("device.html", device=device, flowchart_image_path=flowchart_image_path)
    else:
        return render_template("device.html", device=device, images=images), 404

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
    devices = filter_devices()
    dot = create_flowchart(devices)
    return dot._repr_svg_()

if __name__ == "__main__":
    app.run(debug=True, port=8000)