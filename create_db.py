import sqlite3

# Connect to the demo SQLite database
conn = sqlite3.connect('devices.db')
c = conn.cursor()

# Drop existing tables if they exist so the script can be rerun safely
c.execute('DROP TABLE IF EXISTS devices')

# Create table with real device data
c.execute('''CREATE TABLE devices
             (id INTEGER PRIMARY KEY,
              name TEXT,
              category TEXT,
              cpu_speed REAL,
              ram INTEGER,
              storage INTEGER,
              screen_size REAL,
              price REAL)''')

# Sample data for 50 devices
devices_list = [
    ('Apple MacBook Air M1', 'Laptops', 3.2, 8, 256, 13.3, 999),
    ('Apple MacBook Pro 14', 'Laptops', 3.2, 16, 512, 14, 1999),
    ('Dell XPS 13', 'Laptops', 3.4, 16, 512, 13.4, 1299),
    ('Lenovo ThinkPad X1 Carbon', 'Laptops', 3.5, 16, 512, 14, 1599),
    ('HP Spectre x360', 'Laptops', 3.2, 16, 512, 13.3, 1499),
    ('Lenovo IdeaPad 3', 'Laptops', 2.5, 8, 256, 15.6, 599),
    ('Microsoft Surface Pro 9', 'Tablet', 3.1, 8, 256, 13, 999),
    ('Apple iPad Pro 11', 'Tablet', 3.2, 8, 256, 11, 899),
    ('Samsung Galaxy Tab S9', 'Tablet', 3.0, 8, 128, 11, 799),
    ('Dell OptiPlex 7000', 'PCs', 3.4, 16, 512, 24, 999),
    ('HP Pavilion Desktop', 'PCs', 3.2, 8, 512, 24, 799),
    ('Apple iMac 24', 'PCs', 3.2, 8, 256, 24, 1299),
]

# Insert sample data into the table
c.executemany('INSERT INTO devices (name, category, cpu_speed, ram, storage, screen_size, price) VALUES (?, ?, ?, ?, ?, ?, ?)', devices_list)

# Save (commit) the changes and close the connection
conn.commit()

PersonalUseSoftware = [
"Norton 360", 
"McAfee Total Protection",
"Bitdefender Total Security",
"Kaspersky",
"Avast Free",
"Avira Prime"
]

StudentUseSoftware = [ 
"Norton 360", 
"McAfee Total Protection", 
"Bitdefender Total Security", 
"Kaspersky Total Security", 
"Avast Premium Security", 
"Avira Prime" 
]

WorkUseSoftware = [
"Symantec Endpoint Protection", 
"McAfee Endpoint Security", 
"Bitdefender GravityZone", 
"Kaspersky Endpoint Security", 
"Sophos Intercept X", 
"Trend Micro Apex One" 
]

GovernmentUseSoftware = [
"Symantec Endpoint Protection", 
"McAfee Endpoint Security", 
"Bitdefender GravityZone", 
"Kaspersky Endpoint Security", 
"Sophos Intercept X", 
"Trend Micro Apex One" 
]

c.execute('''CREATE TABLE PersonalUseSoftware
             (id INTEGER PRIMARY KEY,
              Software TEXT)''')

c.executemany('INSERT INTO PersonalUseSoftware (Software) VALUES (?)', [(software,) for software in PersonalUseSoftware])
conn.commit()

c.execute('''CREATE TABLE StudentUseSoftware
             (id INTEGER PRIMARY KEY,
              Software TEXT)''')

c.executemany('INSERT INTO StudentUseSoftware (Software) VALUES (?)', [(software,) for software in StudentUseSoftware])
conn.commit()

c.execute('''CREATE TABLE WorkUseSoftware
             (id INTEGER PRIMARY KEY,
              Software TEXT)''')

c.executemany('INSERT INTO WorkUseSoftware (Software) VALUES (?)', [(software,) for software in WorkUseSoftware])
conn.commit()

c.execute('''CREATE TABLE GovernmentUseSoftware
             (id INTEGER PRIMARY KEY,
              Software TEXT)''')

c.executemany('INSERT INTO GovernmentUseSoftware (Software) VALUES (?)', [(software,) for software in GovernmentUseSoftware])
conn.commit()

SecurityRecommendations = [
    "BitLocker Drive Encryption",
    "Windows Defender Application Guard",
    "Credential Guard",
    "Device Guard",
    "Windows Hello for Business",
    "Enable Auto-Lock",
    "Secure Boot",
    "VPN Usage",
    "Group Policy Object (GPO)",
    "Regular Patching",
    "Endpoint Protection",
    "Application Whitelisting",
    "Data Loss Prevention",
    "Least Privilege Principle",
    "Network Segmentation",
    "Multi-Factor Authentication (MFA)",
    "Disable Unnecessary Services",
    "OS Hardening",
    "User Training and Awareness",
    "Regular Backups"
]

c.execute('''CREATE TABLE SecurityRecommendations
             (id INTEGER PRIMARY KEY,
              Software TEXT)''')

c.executemany('INSERT INTO SecurityRecommendations (Software) VALUES (?)', [(software,) for software in SecurityRecommendations])
conn.commit()

c.execute('''CREATE TABLE Personal
             (id INTEGER PRIMARY KEY,
              name TEXT,
              category TEXT,
              cpu_speed REAL,
              ram INTEGER,
              storage INTEGER,
              screen_size REAL,
              price REAL)''')

c.executemany('INSERT INTO Personal (name, category, cpu_speed, ram, storage, screen_size, price) VALUES (?, ?, ?, ?, ?, ?, ?)', devices_list)
conn.commit()

c.execute('''CREATE TABLE Work
             (id INTEGER PRIMARY KEY,
              name TEXT,
              category TEXT,
              cpu_speed REAL,
              ram INTEGER,
              storage INTEGER,
              screen_size REAL,
              price REAL)''')

c.executemany('INSERT INTO Work (name, category, cpu_speed, ram, storage, screen_size, price) VALUES (?, ?, ?, ?, ?, ?, ?)', devices_list)
conn.commit()

c.execute('''CREATE TABLE Government
             (id INTEGER PRIMARY KEY,
              name TEXT,
              category TEXT,
              cpu_speed REAL,
              ram INTEGER,
              storage INTEGER,
              screen_size REAL,
              price REAL)''')

c.executemany('INSERT INTO Government (name, category, cpu_speed, ram, storage, screen_size, price) VALUES (?, ?, ?, ?, ?, ?, ?)', devices_list)
conn.commit()

c.execute('''CREATE TABLE Education
             (id INTEGER PRIMARY KEY,
              name TEXT,
              category TEXT,
              cpu_speed REAL,
              ram INTEGER,
              storage INTEGER,
              screen_size REAL,
              price REAL)''')

c.executemany('INSERT INTO Education (name, category, cpu_speed, ram, storage, screen_size, price) VALUES (?, ?, ?, ?, ?, ?, ?)', devices_list)
conn.commit()

conn.close()
