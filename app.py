from flask import Flask, render_template, request, jsonify
import sqlite3
import graphviz

# Initialize Flask application
app = Flask(__name__)

# Minimum requirements based on UK government recommendations
minimum_requirements = {
    'cpu_speed': 2.0,  # GHz
    'ram': 4,          # GB
    'storage': 64,     # GB
    'screen_size': 10  # inches
}

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
        
        dot.edge('E', 'H')
        dot.edge('F', 'H')
        dot.edge('G', 'H')
        dot.edge('H', 'I')
        dot.edge('I', 'J')
        dot.edge('J', 'K')
    
    return dot


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
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
            devices_json = [{"id": device[0], "name": device[1]} for device in devices]  # Simplified example
            return jsonify(devices_json)
        except Exception as e:
            print("Error:", e)
            return jsonify({"error": str(e)}), 400
    else:
        devices = filter_devices()
        personal_use = request.args.get("personal_use", "false").lower() in ["true", "1", "t"]
        flowchart = create_flowchart(devices, personal_use=personal_use)
        return render_template("index.html", personal_use=personal_use, devices=devices)
    return render_template("index.html")

@app.route("/device/<int:device_id>")
def device(device_id):
    conn = sqlite3.connect('devices.db')
    c = conn.cursor()
    c.execute("SELECT * FROM devices WHERE id=?", (device_id,))
    device = c.fetchone()
    conn.close()
    return render_template("device.html", device=device)

if __name__ == "__main__":
    app.run(debug=True)