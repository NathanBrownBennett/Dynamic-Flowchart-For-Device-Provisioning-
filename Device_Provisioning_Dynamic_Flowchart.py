import graphviz
import requests
from bs4 import BeautifulSoup

# Define the minimum requirements based on UK government recommendations
minimum_requirements = {
    'cpu_speed': 2.0,  # GHz
    'ram': 4,          # GB
    'storage': 64,     # GB
    'screen_size': 10  # inches
}

# Function to get devices from GSMArena
def get_devices(category):
    url = f"https://www.gsmarena.com/{category}.php3"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    devices = []
    for link in soup.find_all('a', class_='model-link'):
        device_name = link.text.strip()
        devices.append(device_name)
    return devices

# Function to filter devices based on minimum requirements
def filter_devices(devices):
    filtered_devices = []
    for device in devices:
        # Fetch device details and filter based on requirements
        # Here we assume a function fetch_device_details(device) that returns a dictionary with details
        details = fetch_device_details(device)
        if (details['cpu_speed'] >= minimum_requirements['cpu_speed'] and
            details['ram'] >= minimum_requirements['ram'] and
            details['storage'] >= minimum_requirements['storage'] and
            details['screen_size'] >= minimum_requirements['screen_size']):
            filtered_devices.append(device)
    return filtered_devices

# Placeholder function for fetching device details (to be implemented)
def fetch_device_details(device):
    # In actual implementation, fetch details from the device page on GSMArena
    return {
        'cpu_speed': 2.5,  # GHz
        'ram': 8,          # GB
        'storage': 128,    # GB
        'screen_size': 12  # inches
    }

# Function to create the flowchart
def create_flowchart():
    dot = graphviz.Digraph(comment='Device Provisioning Dynamic Flowchart')
    
    # Start Menu
    dot.node('A', 'Are you purchasing for personal or for work use?')
    dot.node('B', 'Personal Use')
    dot.node('C', 'Work Use')
    dot.edge('A', 'B', 'Personal')
    dot.edge('A', 'C', 'Work')
    
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
    
    # Fetch and filter devices for each category
    for category, node in zip(['personal_computers', 'laptops', 'tablets'], ['E', 'F', 'G']):
        devices = get_devices(category)
        filtered_devices = filter_devices(devices)
        for device in filtered_devices:
            dot.node(device, device)
            dot.edge(node, device)
    
    return dot

# Create and render the flowchart
flowchart = create_flowchart()
flowchart.render('device_provisioning_flowchart', format='png')
