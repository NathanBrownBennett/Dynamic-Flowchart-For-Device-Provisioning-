import solara
from flask import Flask, render_template
import graphviz
import pandas as pd

# Example device data (would be fetched from GSMArena in a real implementation)
devices = [
    {'name': 'Device A', 'category': 'laptop', 'cpu_speed': 2.5, 'ram': 8, 'storage': 256, 'screen_size': 13, 'price': 1000},
    {'name': 'Device B', 'category': 'laptop', 'cpu_speed': 2.2, 'ram': 4, 'storage': 128, 'screen_size': 15, 'price': 800},
    {'name': 'Device C', 'category': 'tablet', 'cpu_speed': 1.8, 'ram': 4, 'storage': 64, 'screen_size': 10, 'price': 500},
    # Add more devices as needed
]

# Minimum requirements based on UK government recommendations
minimum_requirements = {
    'cpu_speed': 2.0,  # GHz
    'ram': 4,          # GB
    'storage': 64,     # GB
    'screen_size': 10  # inches
}

# Function to filter devices
def filter_devices(devices, category=None, price_range=None, specs=None):
    filtered_devices = []
    for device in devices:
        if category and device['category'] != category:
            continue
        if price_range and not (price_range[0] <= device['price'] <= price_range[1]):
            continue
        if specs:
            if device['cpu_speed'] < specs.get('cpu_speed', minimum_requirements['cpu_speed']):
                continue
            if device['ram'] < specs.get('ram', minimum_requirements['ram']):
                continue
            if device['storage'] < specs.get('storage', minimum_requirements['storage']):
                continue
            if device['screen_size'] < specs.get('screen_size', minimum_requirements['screen_size']):
                continue
        filtered_devices.append(device)
    return filtered_devices

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
            dot.node(device['name'], device['name'])
            dot.edge('B', device['name'])
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
            filtered_devices = filter_devices(devices, category=category)
            for device in filtered_devices:
                dot.node(device['name'], device['name'])
                dot.edge(node, device['name'])
        
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

# Interactive Solara app
@solara.component
def DeviceProvisioningApp():
    work_use = solara.use_state("Personal")
    device_type = solara.use_state("Laptops")
    price_range = solara.use_state((500, 1500))
    cpu_speed = solara.use_state(2.0)
    ram = solara.use_state(4)
    storage = solara.use_state(64)
    screen_size = solara.use_state(10)
    
    def on_submit():
        specs = {
            'cpu_speed': cpu_speed.value,
            'ram': ram.value,
            'storage': storage.value,
            'screen_size': screen_size.value,
        }
        if work_use.value == 'Work':
            category_map = {'PCs': 'personal_computers', 'Laptops': 'laptops', 'Tablets': 'tablets'}
            category = category_map.get(device_type.value)
            filtered_devices = filter_devices(devices, category=category, price_range=price_range.value, specs=specs)
            dot = create_flowchart(filtered_devices)
        elif work_use.value == 'Personal':
            filtered_devices = filter_devices(devices, price_range=price_range.value, specs=specs)
            dot = create_flowchart(filtered_devices, personal_use=True)
        dot.render('flowchart', format='png', cleanup=False)
        solara.display(solara.Image('flowchart.png'))
    
    solara.Markdown("# Device Provisioning Flowchart")
    
    solara.Select(label="Use", options=["Personal", "Work"], value=work_use)
    solara.Select(label="Device Type", options=["PCs", "Laptops", "Tablets"], value=device_type)
    solara.RangeSlider(label="Price Range", min=100, max=3000, step=50, value=price_range)
    solara.FloatSlider(label="CPU Speed (GHz)", min=1.0, max=4.0, step=0.1, value=cpu_speed)
    solara.IntSlider(label="RAM (GB)", min=1, max=16, step=1, value=ram)
    solara.IntSlider(label="Storage (GB)", min=16, max=1024, step=16, value=storage)
    solara.FloatSlider(label="Screen Size (inches)", min=7, max=20, step=0.5, value=screen_size)
    
    solara.Button("Generate Flowchart", on_click=on_submit)

# Run the Solara app
solara.run(DeviceProvisioningApp)
