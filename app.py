from flask import Flask, render_template, request, jsonify
import sqlite3
import graphviz

# Initialize Flask application
app = Flask(__name__)

# Minimum requirements based on UK government recommendations
minimum_requirements = {
    'category': 'PC', # Personal Computer/Laptop/Tablet
    'price': 500,      # GBP
    'cpu_speed': 3.0,  # GHz
    'ram': 8,          # GB
    'storage': 256,     # GB
    'screen_size': 9,  # inches
}

def query_database(query, params):
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

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
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    print(query)
    print(params)
    c.execute(query, params)
    devices = c.fetchall()
    conn.close()
    return devices

def create_flowchart(devices, personal_use=False):
    dot = graphviz.Digraph(comment='Device Provisioning Flowchart')
    
    # Starting point
    dot.node('A', 'Are you purchasing for personal or for work use?')
    dot.node('B', 'Personal Use')
    dot.node('C', 'Work Use')
    dot.edge('A', 'B', 'Personal')
    dot.edge('A', 'C', 'Work')
    
    if personal_use:
        for device in devices:
            dot.node(device[1], device[1])
            dot.edge('B', device[1])
    else:
        # Work use options
        dot.node('D', 'Are you looking to offer Personal Computers, Laptops or Tablets for your employees?')
        dot.edge('C', 'D')
        
        # Device categories
        dot.node('E', 'Personal Computers')
        dot.node('F', 'Laptops')
        dot.node('G', 'Tablets')
        dot.edge('D', 'E', 'PCs')
        dot.edge('D', 'F', 'Laptops')
        dot.edge('D', 'G', 'Tablets')
        
        # Filtered devices
        for category, node in zip(['PCs', 'Laptops', 'Tablets'], ['E', 'F', 'G']):
            filtered_devices = filter_devices(category=category)
            for device in filtered_devices:
                dot.node(device[1], device[1])
                dot.edge(node, device[1])
        
        # Additional steps
        dot.node('H', 'Consider Antivirus Software')
        dot.node('I', 'Consider Cloud Monitoring Tools')
        dot.node('J', 'Consider Backup Solutions')
        dot.node('K', 'Consider Remote Updates and Checkups')
        dot.node('L', 'Ensure DDR5 RAM and MDM Solutions')
        dot.node('M', 'Follow OS Hardening and Update Protocols')
        
        dot.edge('E', 'H')
        dot.edge('F', 'H')
        dot.edge('G', 'H')
        dot.edge('H', 'I')
        dot.edge('I', 'J')
        dot.edge('J', 'K')
    
    return dot

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
def index():
    form_submitted = False
    error_occurred = False
    usage = ''
    devices = filter_devices()
    all_devices = [
            {"id": device[0], "name": device[1], "category": device[2], "cpu_speed": device[3], 
             "ram": device[4], "storage": device[5], "screen_size": device[6], "price": device[7]}
            for device in devices
        ]
    recommended_devices = []
    for device in all_devices:
        recommended_devices.append({
            'id': device['id'],
            'name': device['name'], 
            'category': device['category'], 
            'cpu_speed': device['cpu_speed'], 
            'ram': device['ram'], 
            'storage': device['storage'], 
            'screen_size': device['screen_size'], 
            'price': device['price']
    })
    try:
        if request.method == "POST":
            form_submitted = True
            usage = request.form.get("use")
            category = request.form.get("device_type")
            price_range = request.form.get("price_range")
            if price_range:
                price_range = [int(x) for x in price_range.split(",")]
            searchBar = str(request.form.get("searchBar"))
            specs = {
                'cpu_speed': float(request.form.get("cpu_speed", minimum_requirements['cpu_speed'])),
                'ram': int(request.form.get("ram", minimum_requirements['ram'])),
                'storage': int(request.form.get("storage", minimum_requirements['storage'])),
                'screen_size': float(request.form.get("screen_size", minimum_requirements['screen_size']))
            }
            devices = filter_devices(searchBar=searchBar, category=category, price_range=price_range, specs=specs)
            return render_template("index.html", personal_use=usage, devices=devices, form_submitted=form_submitted, error_occurred=error_occurred, recommended_devices=recommended_devices)
        else:
            devices = filter_devices()
    except Exception as e:
        print("Error:", e)
        error_occurred = True
        recommended_devices = []
        return render_template("index.html", recommended_devices=recommended_devices)

    personal_use = request.args.get("personal_use", "false").lower() in ["true", "1", "t"]
    flowchart = create_flowchart(devices, personal_use=usage)
    return render_template("index.html", recommended_devices=recommended_devices)

@app.route("/device/<int:device_id>")
def device(device_id):
    conn = sqlite3.connect('devices.db')
    c = conn.cursor()
    c.execute("SELECT * FROM devices WHERE id=?", (device_id,))
    device = c.fetchone()
    conn.close()
    return render_template("device.html", device=device)

@app.route("/flowchart")
def flowchart():
    devices = filter_devices()
    dot = create_flowchart(devices)
    return dot._repr_svg_()

if __name__ == "__main__":
    app.run(debug=True, port=8000)