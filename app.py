from flask import Flask, render_template, request
import solara
import graphviz
import pandas as pd
import sqlite3

# Initialize Flask application
app = Flask(__name__)

# Minimum requirements based on UK government recommendations
minimum_requirements = {
    'cpu_speed': 2.0,  # GHz
    'ram': 4,          # GB
    'storage': 64,     # GB
    'screen_size': 10  # inches
}

# Function to filter devices from database
def filter_devices(category=None, price_range=None, specs=None):
    conn = sqlite3.connect('devices.db')
    c = conn.cursor()
    query = "SELECT * FROM devices WHERE 1=1"
    params = []
    
    if category:
        query += " AND category=?"
        params.append(category)
    if price_range:
        query += " AND price BETWEEN ? AND ?"
        params.extend(price_range)
    if specs:
        if 'cpu_speed' in specs:
            query += " AND cpu_speed>=?"
            params.append(specs['cpu_speed'])
        if 'ram' in specs:
            query += " AND ram>=?"
            params.append(specs['ram'])
        if 'storage' in specs:
            query += " AND storage>=?"
            params.append(specs['storage'])
        if 'screen_size' in specs:
            query += " AND screen_size>=?"
            params.append(specs['screen_size'])
        if 'price' in specs:
            query += " AND price<=?"
            params.append(specs['price'])
    
    c.execute(query, params)
    devices = c.fetchall()
    conn.close()
    return devices

# Function to create the flowchart
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
        for category, node in zip(['personal_computers', 'laptops', 'tablets'], ['E', 'F', 'G']):
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
        category = request.form.get("device_type")
        price_range = request.form.get("price_range")
        if price_range:
            price_range = [int(x) for x in price_range.split(",")]
        specs = {
            'cpu_speed': float(request.form.get("cpu_speed", minimum_requirements['cpu_speed'])),
            'ram': int(request.form.get("ram", minimum_requirements['ram'])),
            'storage': int(request.form.get("storage", minimum_requirements['storage'])),
            'screen_size': float(request.form.get("screen_size", minimum_requirements['screen_size']))
        }
        devices = filter_devices(category=category, price_range=price_range, specs=specs)
        return render_template("index.html", devices=devices)
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
