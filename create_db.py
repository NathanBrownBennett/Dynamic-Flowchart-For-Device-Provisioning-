import sqlite3

# Connect to the demo SQLite database
conn = sqlite3.connect('devices.db')
c = conn.cursor()

# Create table
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
    ('Device A', 'Laptops', 2.5, 8, 256, 13, 1000),
    ('Device B', 'Laptops', 2.2, 4, 128, 15, 800),
    ('Device C', 'Tablet', 1.8, 4, 64, 10, 500),
    ('Device D', 'Tablet', 3.8, 4, 64, 10, 500),
    ('Device E', 'PCs', 3.8, 4, 64, 10, 500),
    ('Device E', 'PCs', 3.8, 4, 64, 10, 500),
    ('Device F', 'Laptops', 2.0, 16, 512, 14, 1500),
    ('Device G', 'Tablet', 2.5, 8, 256, 12, 900),
    ('Device H', 'PCs', 3.0, 8, 256, 15, 1200),
    ('Device I', 'Laptops', 2.8, 8, 512, 13, 1300),
    ('Device J', 'Tablet', 2.2, 4, 128, 11, 600),
    ('Device K', 'PCs', 3.5, 16, 512, 17, 2000),
    ('Device L', 'Laptops', 2.4, 8, 256, 14, 1100),
    ('Device M', 'Tablet', 2.0, 8, 128, 10, 700),
    ('Device N', 'PCs', 3.2, 8, 256, 15, 1300),
    ('Device O', 'Laptops', 2.6, 16, 512, 15, 1600),
    ('Device P', 'Tablet', 2.8, 4, 64, 9, 400),
    ('Device Q', 'PCs', 3.7, 16, 512, 17, 2200),
    ('Device R', 'Laptops', 2.2, 8, 256, 13, 1200),
    ('Device S', 'Tablet', 2.4, 8, 128, 11, 800),
    ('Device T', 'PCs', 3.3, 16, 512, 17, 1800),
    ('Device U', 'Laptops', 2.3, 8, 256, 14, 1300),
    ('Device V', 'Tablet', 2.6, 4, 64, 9, 500),
    ('Device W', 'PCs', 3.1, 8, 256, 15, 1400),
    ('Device X', 'Laptops', 2.7, 8, 512, 13, 1500),
    ('Device Y', 'Tablet', 2.1, 4, 128, 11, 700),
    ('Device Z', 'PCs', 3.6, 16, 512, 17, 2100),
    ('Device AA', 'Laptops', 2.9, 8, 256, 14, 1400),
    ('Device BB', 'Tablet', 2.3, 8, 128, 10, 900),
    ('Device CC', 'PCs', 3.4, 16, 512, 17, 1900),
    ('Device DD', 'Laptops', 2.1, 8, 256, 13, 1300),
    ('Device EE', 'Tablet', 2.5, 8, 128, 11, 900),
    ('Device FF', 'PCs', 3.0, 16, 512, 17, 1700),
    ('Device GG', 'Laptops', 2.8, 8, 256, 14, 1600),
    ('Device HH', 'Tablet', 2.2, 4, 64, 9, 600),
    ('Device II', 'PCs', 3.7, 16, 512, 17, 2300),
    ('Device JJ', 'Laptops', 2.6, 8, 256, 13, 1400),
    ('Device KK', 'Tablet', 2.4, 8, 128, 11, 1000),
    ('Device LL', 'PCs', 3.3, 16, 512, 17, 2000),
    ('Device MM', 'Laptops', 2.2, 8, 256, 14, 1500),
    ('Device NN', 'Tablet', 2.6, 8, 128, 10, 800),
    ('Device OO', 'PCs', 3.5, 16, 512, 17, 2200),
    ('Device PP', 'Laptops', 2.4, 8, 256, 13, 1300),
    ('Device QQ', 'Tablet', 2.8, 4, 64, 9, 500),
    ('Device RR', 'PCs', 3.7, 16, 512, 17, 2100),
    ('Device SS', 'Laptops', 2.2, 8, 256, 14, 1200),
    ('Device TT', 'Tablet', 2.4, 8, 128, 11, 800),
    ('Device UU', 'PCs', 3.3, 16, 512, 17, 1800),
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
