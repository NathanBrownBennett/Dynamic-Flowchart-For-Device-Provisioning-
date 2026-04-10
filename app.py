from flask import Flask, render_template, request, jsonify, send_file, Response, abort
import os
import sqlite3
import graphviz
import random
import threading
import requests
from device_scraper import DeviceDataScraper, FALLBACK_DEVICE_DATA
import re
import time

app = Flask(__name__)
form_submitted = False
error_occurred = False
devices = []


@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.root_path, 'static', 'favicon.svg'), mimetype='image/svg+xml')


@app.route('/validate-links', methods=['POST'])
def validate_links():
    """Validate retailer links for a device (async helper)"""
    try:
        data = request.get_json()
        device_name = data.get('device_name', '')
        category = data.get('category', 'device')
        
        retailer_links = get_retailer_links(device_name, category)
        
        # Validate each link (quick check)
        validation_results = {}
        for retailer, url in retailer_links.items():
            try:
                response = requests.head(url, timeout=3, allow_redirects=True)
                validation_results[retailer] = {
                    'url': url,
                    'valid': response.status_code < 400,
                    'status': response.status_code
                }
            except Exception as e:
                validation_results[retailer] = {
                    'url': url,
                    'valid': False,
                    'error': str(e)
                }
        
        return jsonify({
            'device': device_name,
            'links': validation_results
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

# Initialize device scraper
device_scraper = DeviceDataScraper()

# ---- Performance Helpers (Caching & Indexes) (moved up so routes can call) ----
LIVE_LISTINGS_CACHE = { 'data': [], 'ts': 0 }
LIVE_CACHE_TTL = 900  # 15 minutes

# Search results cache - keyed by search term
SEARCH_RESULTS_CACHE = {}
SEARCH_CACHE_TTL = 300  # 5 minutes

def get_search_cache_key(search_term, price_min, price_max, cpu_speed, ram, storage, screen_size, use_case):
    """Generate cache key for search results"""
    return f"{search_term}|{price_min}|{price_max}|{cpu_speed}|{ram}|{storage}|{screen_size}|{use_case}"

def get_cached_search_results(cache_key):
    """Get cached search results if still fresh"""
    now = time.time()
    if cache_key in SEARCH_RESULTS_CACHE:
        results, timestamp = SEARCH_RESULTS_CACHE[cache_key]
        if now - timestamp < SEARCH_CACHE_TTL:
            print(f"[CACHE] Using cached search results for: {cache_key.split('|')[0]}")
            return results
        else:
            del SEARCH_RESULTS_CACHE[cache_key]  # Expired
    return None

def cache_search_results(cache_key, results):
    """Cache search results with timestamp"""
    SEARCH_RESULTS_CACHE[cache_key] = (results, time.time())
    print(f"[CACHE] Cached {len(results)} results for: {cache_key.split('|')[0]}")

def get_cached_live_listings():
    """Return cached live listings or refresh if TTL expired."""
    now = time.time()
    if LIVE_LISTINGS_CACHE['data'] and now - LIVE_LISTINGS_CACHE['ts'] < LIVE_CACHE_TTL:
        return LIVE_LISTINGS_CACHE['data']
    try:
        live = device_scraper.get_real_device_data()[:8]
        mapped = [{
            'id': None,
            'name': x.get('name'),
            'category': x.get('category'),
            'cpu_speed': x.get('cpu_speed', 0),
            'ram': x.get('ram', 0),
            'storage': x.get('storage', 0),
            'screen_size': x.get('screen_size', 0),
            'price': x.get('price', 0),
            'image_url': x.get('image_url'),
            'source': x.get('source')
        } for x in live]
        enriched = apply_rule_engine(mapped, use_case='Work')
        for item in enriched:
            item['retailer_links'] = get_retailer_links(item['name'], item['category'] or 'device')
        LIVE_LISTINGS_CACHE['data'] = enriched
        LIVE_LISTINGS_CACHE['ts'] = now
        return enriched
    except Exception as e:
        print(f"Error fetching live listings (cache): {e}")
        return []

def ensure_db_indexes():
    try:
        conn = sqlite3.connect('devices.db')
        cursor = conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_name ON devices(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_category ON devices(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_price ON devices(price)')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Index creation error: {e}")

ensure_db_indexes()

# Minimum requirements based on UK government recommendations
minimum_requirements = {
    'category': 'PC',  # Personal Computer/Laptop/Tablet
    'price': 500,      # GBP
    'cpu_speed': 3.0,  # GHz
    'ram': 8,          # GB
    'storage': 256,    # GB
    'screen_size': 9,  # inches
}

# --- Security Rule Engine and Scoring ---

def infer_os_and_cpu(device_name: str, category: str):
    name = device_name.lower()
    # OS inference
    if any(k in name for k in ['macbook', 'imac', 'mac ', 'macos', 'apple']):
        os = 'macOS'
        cpu_vendor = 'Apple Silicon' if any(k in name for k in ['m1', 'm2', 'm3']) else 'Intel'
    elif any(k in name for k in ['ipad']):
        os = 'iPadOS'
        cpu_vendor = 'Apple Silicon'
    elif any(k in name for k in ['surface', 'windows', 'thinkpad', 'xps', 'latitude', 'hp ', 'spectre', 'pavilion', 'lenovo', 'dell']):
        os = 'Windows 11'
        # Rough CPU inference
        if any(k in name for k in ['ryzen', 'amd']):
            cpu_vendor = 'AMD'
        elif any(k in name for k in ['intel', 'core i', 'i3', 'i5', 'i7', 'i9']):
            cpu_vendor = 'Intel'
        else:
            cpu_vendor = 'Unknown'
    elif any(k in name for k in ['chromebook', 'chromeos']):
        os = 'ChromeOS'
        cpu_vendor = 'Intel'
    elif any(k in name for k in ['galaxy tab', 'android', 'samsung tab']):
        os = 'Android'
        cpu_vendor = 'Qualcomm'
    elif any(k in name for k in ['ubuntu', ' linux', 'fedora', 'debian', 'redhat', 'centos', 'pop!_os', 'arch']):
        os = 'Linux'
        cpu_vendor = 'Intel'
    else:
        # Default by category
        os = 'Windows 11' if category in ['Laptops', 'PCs'] else 'Android'
        cpu_vendor = 'Intel' if category in ['Laptops', 'PCs'] else 'Unknown'
    return os, cpu_vendor


def detect_known_vulnerabilities(os: str, cpu_vendor: str, device_name: str):
    findings = []
    mitigations = []

    # CPU micro-architectural vulns (generalized)
    if cpu_vendor in ['Intel', 'AMD']:
        findings.append('Speculative execution side-channels (Spectre/Meltdown class)')
        mitigations.append('Ensure firmware (microcode) and OS patches are up to date; enable mitigations')

    if cpu_vendor == 'Intel' and re.search(r'i3|i5|i7|i9', device_name, re.I):
        mitigations.append('Enable/verify UEFI Secure Boot and TPM 2.0')

    if os == 'Windows 11':
        mitigations.append('Enable BitLocker with TPM 2.0 and PIN; use Windows Hello for Business')
    elif os == 'macOS':
        mitigations.append('Enable FileVault; require Apple ID with 2FA; Gatekeeper/App Notarization')
    elif os in ['Android', 'iPadOS']:
        mitigations.append('Require device encryption, biometric unlock, and MDM enrollment')

    # Supply chain / bloatware risk on OEM Windows devices
    if os == 'Windows 11' and any(b in device_name.lower() for b in ['hp', 'dell', 'lenovo', 'acer', 'asus']):
        findings.append('Potential OEM preinstalled software increases attack surface')
        mitigations.append('Use clean OS image or remove bloatware; consider Windows Autopilot/MDM')

    # Example OS risks
    if os == 'Android':
        findings.append('Android fragmentation risk; slower security patch cadence on some models')
        mitigations.append('Choose Android Enterprise Recommended models; enforce monthly patch SLAs')

    return findings, mitigations


def compute_security_score(device: dict, os: str, cpu_vendor: str, use_case: str):
    # Base from hardware capability
    score = 50
    score += min(max((device.get('cpu_speed', 0) - 2.5) * 10, 0), 25)  # up to +25
    score += 5 if device.get('ram', 0) >= 16 else (2 if device.get('ram', 0) >= 8 else 0)
    score += 5 if device.get('storage', 0) >= 512 else 0

    # OS baseline security
    os_weight = {
        'Windows 11': 10,
        'macOS': 12,
        'ChromeOS': 12,
        'iPadOS': 10,
        'Android': 6
    }
    score += os_weight.get(os, 8)

    # CPU vendor risk adjustments
    if cpu_vendor in ['Intel', 'AMD']:
        score -= 5  # speculative class mitigations overhead and residual risk
    elif cpu_vendor == 'Apple Silicon':
        score += 3

    # Use-case requirements tighten score caps
    if use_case in ['Government', 'Public Sector']:
        if device.get('ram', 0) < 16 or device.get('cpu_speed', 0) < 3.0:
            score -= 8
    elif use_case in ['Work', 'Business', 'Enterprise']:
        if device.get('ram', 0) < 8:
            score -= 5

    # Clamp
    score = max(0, min(100, int(round(score))))

    # Level
    if score >= 85:
        level = 'Excellent'
    elif score >= 70:
        level = 'Good'
    elif score >= 55:
        level = 'Adequate'
    else:
        level = 'Risky'

    return score, level


def hardening_recommendations(os: str, use_case: str):
    recs = {
        'software': [],
        'hardware': [],
        'settings': []
    }
    # Software
    if os == 'Windows 11':
        recs['software'] = ['Microsoft Defender for Endpoint', 'BitLocker', 'Microsoft Intune/Autopilot']
        recs['settings'] = ['Require TPM 2.0 + Secure Boot', 'Enforce WDAC/Smart App Control', 'Disable legacy protocols (SMBv1, NTLM where possible)']
    elif os == 'macOS':
        recs['software'] = ['Jamf Pro (MDM)', 'FileVault', 'Little Snitch or LuLu (network monitor)']
        recs['settings'] = ['Enable Gatekeeper and System Integrity Protection', 'Require 2FA and strong passwords', 'Limit kernel/system extensions']
    elif os == 'Android':
        recs['software'] = ['Android Enterprise (MDM)', 'Google Play Protect (enforced)', 'Corporate VPN client']
        recs['settings'] = ['Block sideloading; managed Play Store only', 'Enforce monthly security patches', 'Enable device encryption and work profile']
    elif os == 'iPadOS':
        recs['software'] = ['Apple Business Manager + MDM', 'Per-app VPN', 'Managed Open In policies']
        recs['settings'] = ['Enforce passcode/biometric auth', 'Disallow unmanaged profiles', 'Automatic updates']
    else:
        recs['software'] = ['EDR/AV appropriate to OS', 'MDM enrollment']
        recs['settings'] = ['Enable full-disk encryption', 'Automatic updates', 'Least privilege accounts']

    # Hardware tokens and extras (all use-cases)
    recs['hardware'] = ['FIDO2 security keys (e.g., YubiKey)', 'Privacy screen', 'Webcam cover']

    # Tighten for government/public sector
    if use_case in ['Government', 'Public Sector']:
        recs['settings'].append('CIS benchmark-aligned configuration')
        recs['hardware'].append('TPM 2.0 attestation (where applicable)')

    return recs


def compute_benchmark_metrics(device: dict, security_score: int):
    """Compute simple normalized hardware benchmark indices for display."""
    cpu_speed = float(device.get('cpu_speed') or 0)
    ram_gb = int(device.get('ram') or 0)
    storage_gb = int(device.get('storage') or 0)

    # Hardware-only indices (0-100)
    cpu_index = max(0, min(100, int(round((cpu_speed / 5.0) * 100))))
    memory_index = max(0, min(100, int(round((ram_gb / 64.0) * 100))))
    storage_index = max(0, min(100, int(round((storage_gb / 2000.0) * 100))))

    # Weighted blended score with security posture included for practical ranking
    overall = int(round(
        cpu_index * 0.35 +
        memory_index * 0.25 +
        storage_index * 0.15 +
        security_score * 0.25
    ))

    return {
        'cpu_index': cpu_index,
        'memory_index': memory_index,
        'storage_index': storage_index,
        'overall_index': max(0, min(100, overall))
    }


def get_debloat_tools(os_name: str, device_name: str):
    """Return curated debloat/performance optimization tools by inferred OS and vendor."""
    os_group = 'Windows 11' if 'Windows' in (os_name or '') else (os_name or '')
    name = (device_name or '').lower()

    tools_by_os = {
        'Windows 11': [
            {
                'name': 'O&O AppBuster',
                'url': 'https://www.oo-software.com/en/ooappbuster',
                'description': 'Removes preinstalled Windows apps and OEM bloatware safely.'
            },
            {
                'name': 'BCUninstaller',
                'url': 'https://www.bcuninstaller.com/',
                'description': 'Batch uninstall utility for stubborn software and leftovers.'
            },
            {
                'name': 'Microsoft PC Manager',
                'url': 'https://pcmanager.microsoft.com/',
                'description': 'Official cleanup and startup optimization tool from Microsoft.'
            }
        ],
        'macOS': [
            {
                'name': 'AppCleaner',
                'url': 'https://freemacsoft.net/appcleaner/',
                'description': 'Thoroughly removes apps and residual files.'
            },
            {
                'name': 'OnyX',
                'url': 'https://www.titanium-software.fr/en/onyx.html',
                'description': 'Maintenance, cache cleanup, and system tuning utility.'
            }
        ],
        'Linux': [
            {
                'name': 'BleachBit',
                'url': 'https://www.bleachbit.org/',
                'description': 'System cleaner for cache/log cleanup and reclaiming storage.'
            },
            {
                'name': 'Stacer',
                'url': 'https://github.com/oguzhaninan/Stacer',
                'description': 'Open-source optimizer and startup/process management dashboard.'
            }
        ],
        'Android': [
            {
                'name': 'Universal Android Debloater Next Generation',
                'url': 'https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation',
                'description': 'ADB-based debloat utility for removing non-essential packages.'
            }
        ],
        'iPadOS': [
            {
                'name': 'Apple Configurator',
                'url': 'https://apps.apple.com/us/app/apple-configurator/id1037126344',
                'description': 'Apple-managed provisioning and app/profile control utility.'
            }
        ],
        'ChromeOS': [
            {
                'name': 'Google Admin Console',
                'url': 'https://admin.google.com/',
                'description': 'Policy-driven app control and performance hygiene at scale.'
            }
        ]
    }

    vendor_tool = None
    if os_group == 'Windows 11':
        if 'dell' in name:
            vendor_tool = {
                'name': 'Dell SupportAssist (Cleanup/Updates)',
                'url': 'https://www.dell.com/support/home/supportassist',
                'description': 'Driver, firmware, and diagnostics management for Dell devices.'
            }
        elif 'lenovo' in name:
            vendor_tool = {
                'name': 'Lenovo Vantage',
                'url': 'https://support.lenovo.com/solutions/ht505081',
                'description': 'Device maintenance and update management for Lenovo systems.'
            }
        elif 'hp' in name:
            vendor_tool = {
                'name': 'HP Support Assistant',
                'url': 'https://support.hp.com/help/hp-support-assistant',
                'description': 'HP diagnostics, updates, and optimization utility.'
            }
        elif 'surface' in name or 'microsoft' in name:
            vendor_tool = {
                'name': 'Surface Diagnostic Toolkit',
                'url': 'https://support.microsoft.com/surface',
                'description': 'Diagnostics and tuning resources for Microsoft Surface devices.'
            }

    tools = list(tools_by_os.get(os_group, tools_by_os.get('Windows 11', [])))
    if vendor_tool:
        tools.append(vendor_tool)
    return tools


def apply_rule_engine(devices_list: list, use_case: str):
    """Filter/enrich devices based on use-case policies and compute security metadata."""
    enriched = []
    for d in devices_list:
        # Normalize keys between DB devices and scraped devices
        scraped_image_url = d.get('image_url') or d.get('image')
        
        device = {
            'id': d.get('id'),
            'name': d.get('name'),
            'category': d.get('category'),
            'cpu_speed': d.get('cpu_speed', 0),
            'ram': d.get('ram', 0),
            'storage': d.get('storage', 0),
            'screen_size': d.get('screen_size', 0),
            'price': d.get('price', 0),
            'image': get_device_image_url(d.get('name') or '', scraped_image_url),  # Use scraped URL if available
            'source': d.get('source')
        }
        os, cpu_vendor = infer_os_and_cpu(device['name'] or '', device.get('category') or '')
        findings, mitigations = detect_known_vulnerabilities(os, cpu_vendor, device['name'] or '')
        score, level = compute_security_score(device, os, cpu_vendor, use_case)
        recs = hardening_recommendations(os, use_case)

        # Policy gates
        allowed = True
        if use_case in ['Government', 'Public Sector']:
            if device.get('ram', 0) < 16 or device.get('cpu_speed', 0) < 3.0:
                allowed = False  # baseline capability requirement
        if use_case in ['Work', 'Business', 'Enterprise'] and device.get('ram', 0) < 8:
            allowed = False

        device['os'] = os
        device['cpu_vendor'] = cpu_vendor
        device['security'] = {
            'score': score,
            'level': level,
            'findings': findings,
            'mitigations': mitigations,
            'recommendations': recs
        }
        device['benchmark'] = compute_benchmark_metrics(device, score)
        device['debloat_tools'] = get_debloat_tools(os, device.get('name') or '')
        device['retailer_links'] = get_retailer_links(device['name'], device.get('category') or 'device')
        device['allowed'] = allowed
        enriched.append(device)
    return enriched

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
    # Enrich with security metadata for default view (assume Work baseline)
    enriched_recommended = apply_rule_engine(recommended_devices, use_case='Work')
    print(f"Recommended devices: {recommended_devices}")
    
    # Live listings via cache (performance optimization)
    live_listings = get_cached_live_listings()

    # Pagination params for search results
    page = int(request.args.get('page', 1))
    page_size = 20
    total_results = 0

    if request.method == 'POST':
        form_submitted = True
        error_occurred = False
        form_data = request.form
        print("Form Submitted. About to search for devices with form data:", form_data)
        
        # Extract form data with defaults
        name = form_data.get('searchBar', '').strip()
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
        
        print(f"Search parameters:")
        print(f"  Search Term: {name}")
        print(f"  Price Range: {price_range_min} - {price_range_max}")
        print(f"  CPU Speed: {cpu_speed}")
        print(f"  RAM: {ram}")
        print(f"  Storage: {storage}")
        print(f"  Screen Size: {screen_size}")
        print(f"  Use Case: {use}")
        print(f"  Device Type: {device_type}")
        print(f"  Operating System: {operating_system}")
        print(f"  Brand: {brand}")
        
        try:
            # Check cache first
            cache_key = get_search_cache_key(name, price_range_min, price_range_max, cpu_speed, ram, storage, screen_size, use)
            cached_results = get_cached_search_results(cache_key)
            
            if cached_results:
                devices = cached_results
            elif name:  # If user provided a search term, use LIVE scraping instead of static database
                print(f"[LIVE SEARCH] Searching for: {name}")
                # Perform live web scraping for fresh results
                live_results = device_scraper.search_devices_live(name, max_results=20)
                
                if live_results:
                    # Convert scraped results to dict format
                    devices = [{
                        'id': None,
                        'name': item.get('name'),
                        'category': item.get('category'),
                        'cpu_speed': item.get('cpu_speed', 0),
                        'ram': item.get('ram', 0),
                        'storage': item.get('storage', 0),
                        'screen_size': item.get('screen_size', 0),
                        'price': item.get('price', 0),
                        'image': item.get('image_url'),  # Direct image URL from scraper
                        'image_url': item.get('image_url'),  # Also preserve as image_url for apply_rule_engine
                        'source': item.get('retailer', 'Web Search'),
                        'search_query': name
                    } for item in live_results]
                    
                    # Apply filtering on live results
                    if cpu_speed > 0 or ram > 0 or storage > 0 or screen_size > 0:
                        devices = [d for d in devices if 
                            (d['cpu_speed'] >= cpu_speed if cpu_speed > 0 else True) and
                            (d['ram'] >= ram if ram > 0 else True) and
                            (d['storage'] >= storage if storage > 0 else True) and
                            (d['screen_size'] >= screen_size if screen_size > 0 else True)
                        ]
                    
                    # Filter by price range
                    try:
                        price_min = int(price_range_min)
                        price_max = int(price_range_max)
                        devices = [d for d in devices if price_min <= d['price'] <= price_max]
                    except:
                        pass
                    
                    # Filter by device type if specified
                    if device_type:
                        devices = [d for d in devices if device_type.lower() in (d.get('category') or '').lower()]
                    
                    # Filter by brand if specified
                    if brand:
                        devices = [d for d in devices if brand.lower() in (d.get('name') or '').lower()]
                    
                    # Cache the filtered results
                    if devices:
                        cache_search_results(cache_key, devices)
                else:
                    print(f"No live results found for '{name}', falling back to database")
                    devices = recommended_devices[:8]
                    
            else:  # No search term, use database recommendations
                print("[SEARCH] No search term provided, using database recommendations")
                devices = recommended_devices
            
            # Enrich search results with security scoring
            devices = apply_rule_engine(devices, use_case=use)
            
            # Filter based on use-case requirements
            if use in ['Government', 'Public Sector', 'Work', 'Business', 'Enterprise']:
                devices = [d for d in devices if d.get('allowed')]
            
            total_results = len(devices)
            
            if not devices:
                print(f"No devices matched all criteria, showing recommended alternatives")
                devices = enriched_recommended[:8]
                
        except Exception as e:
            print(f"Search error: {e}")
            import traceback
            traceback.print_exc()
            error_occurred = True
            devices = enriched_recommended[:8]
        
        print(f"Final devices result: {len(devices)} devices found")
        print(f"Form submission result: form_submitted={form_submitted}, error_occurred={error_occurred}")
        print("Rendering results")

    total_pages = (total_results // page_size + (1 if total_results % page_size else 0)) if total_results else 0
    return render_template(
        'index.html',
        recommended_devices=enriched_recommended,
        light_mode_image=light_mode_image,
        dark_mode_image=dark_mode_image,
        form_submitted=form_submitted,
        error_occurred=error_occurred,
        devices=devices,
        live_listings=live_listings,
        page=page,
        total_pages=total_pages,
        total_results=total_results
    )

@app.route('/device/<int:device_id>')
def device(device_id):
    conn = sqlite3.connect('devices.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
    device = cursor.fetchone()
    conn.close()
    
    if not device:
        abort(404)

    device = convert_to_dict([device])[0]
    # Enrich with rule engine (assume Work here; could be parameterized)
    enriched = apply_rule_engine([device], use_case='Work')[0]
    device.update({
        'os': enriched.get('os'),
        'cpu_vendor': enriched.get('cpu_vendor'),
        'security': enriched.get('security'),
        'benchmark': enriched.get('benchmark'),
        'debloat_tools': enriched.get('debloat_tools')
    })
    # Add retailer links
    device['retailer_links'] = enriched.get('retailer_links') or get_retailer_links(device['name'], device['category'])
        
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

    output_base = os.path.join('static', 'flowcharts', str(device['id']))
    dot.render(output_base, format='svg', cleanup=True)

    conn.close()

    return output_base + '.svg'

@app.route("/flowchart/<path:image_path>")
def serve_flowchart(image_path):
    # Only allow serving SVGs from static/flowcharts and reject path traversal.
    safe_name = os.path.basename(image_path)
    if safe_name != image_path or not safe_name.lower().endswith('.svg'):
        abort(404)

    static_root = app.static_folder or os.path.join(app.root_path, 'static')
    full_path = os.path.join(static_root, 'flowcharts', safe_name)
    if not os.path.isfile(full_path):
        abort(404)

    return send_file(full_path, mimetype='image/svg+xml')

@app.route("/flowchart")
def flowchart():
    # This route seems to have an issue - removing problematic code
    return "Flowchart functionality moved to device-specific pages"

def populate_database_with_real_data():
    """Populate database with real device data from CSV (preferred) or web sources"""
    try:
        print("Fetching device data (CSV-preferred)...")
        # Try CSV first - this is the preferred source
        real_devices = device_scraper.load_devices_from_csv('devices.csv')
        
        # Fallback to web scraping and fallback data if CSV is insufficient
        if not real_devices or len(real_devices) < 8:
            print("CSV insufficient or not found, attempting web scraping...")
            scraped_devices = device_scraper.get_real_device_data()
            if scraped_devices and len(scraped_devices) >= 8:
                real_devices = scraped_devices
                print(f"Successfully scraped {len(real_devices)} devices from web sources")
            else:
                print("Web scraping unsuccessful or insufficient, using fallback data...")
                real_devices = FALLBACK_DEVICE_DATA
        else:
            print(f"Successfully loaded {len(real_devices)} devices from CSV")
        
        conn = sqlite3.connect('devices.db')
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute('DELETE FROM devices')
        
        # Insert device data
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

def get_device_image_url(device_name, scraped_url=None):
    """Get device image URL: prioritize scraped images, fallback to static placeholders"""
    # Use scraped image URL if available (from web scraping)
    if scraped_url and (scraped_url.startswith('http://') or scraped_url.startswith('https://')):
        return scraped_url
    
    # Fallback: use local placeholder images if no scraped URL
    # Map device types to appropriate placeholder images
    device_name_lower = device_name.lower()
    
    if 'laptop' in device_name_lower or 'book' in device_name_lower:
        return '/static/images/1.jpg'  # Laptop placeholder
    elif 'desktop' in device_name_lower or 'pc' in device_name_lower:
        return '/static/images/2.jpg'  # Desktop placeholder
    elif 'tablet' in device_name_lower or 'ipad' in device_name_lower:
        return '/static/images/3.jpg'  # Tablet placeholder
    elif 'apple' in device_name_lower or 'mac' in device_name_lower:
        return '/static/images/4.jpg'  # Apple device placeholder
    elif 'dell' in device_name_lower:
        return '/static/images/5.jpg'  # Dell placeholder
    elif 'hp' in device_name_lower:
        return '/static/images/6.jpg'  # HP placeholder
    elif 'lenovo' in device_name_lower:
        return '/static/images/7.jpg'  # Lenovo placeholder
    elif 'microsoft' in device_name_lower or 'surface' in device_name_lower:
        return '/static/images/8.jpg'  # Microsoft placeholder
    else:
        # Default to a random placeholder from available images
        base_path = '/static/images'
        image_num = abs(hash(device_name)) % 16 + 1  # Deterministic but varied
        return f'{base_path}/{image_num}.jpg'

# Initialize database with real device data (CSV-preferred)
print("Initializing database with device data...")
populate_database_with_real_data()

@app.route("/api/image-proxy", methods=["GET"])
def image_proxy():
    """
    Proxy for external device images to handle CORS and caching.
    Prevents broken image links and improves load reliability.
    """
    try:
        image_url = request.args.get('url', '')
        if not image_url or not (image_url.startswith('http://') or image_url.startswith('https://')):
            return "Invalid image URL", 400
        
        # Fetch the image with timeout
        response = requests.get(image_url, timeout=5)
        response.raise_for_status()
        
        # Return image with caching headers
        return response.content, 200, {
            'Content-Type': response.headers.get('Content-Type', 'image/jpeg'),
            'Cache-Control': 'public, max-age=86400'  # Cache for 24 hours
        }
    except Exception as e:
        print(f"Image proxy error: {e}")
        # Return placeholder or 1x1 transparent GIF
        return b'', 404

@app.route("/search-live", methods=["POST"])
def search_live():
    """
    Endpoint for live device search across retailers.
    Takes search term and returns fresh market results.
    """
    try:
        data = request.get_json()
        search_term = data.get('query', '').strip()
        max_results = data.get('max_results', 20)
        
        if not search_term or len(search_term) < 2:
            return jsonify({'error': 'Search term too short'}), 400
        
        print(f"[API] Live search for: {search_term}")
        results = device_scraper.search_devices_live(search_term, max_results=max_results)
        
        if not results:
            return jsonify({
                'query': search_term,
                'results': [],
                'message': 'No devices found for this search term',
                'source': 'live_web_search'
            }), 200
        
        # Apply security scoring to results
        enriched_results = apply_rule_engine(results, use_case='Personal')
        
        return jsonify({
            'query': search_term,
            'results': enriched_results[:max_results],
            'total_found': len(enriched_results),
            'source': 'live_web_search'
        }), 200
        
    except Exception as e:
        print(f"Live search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/get-current-price", methods=["POST"])
def get_current_price():
    """
    Get current pricing from specific retailer.
    Real-time price comparison across retailers.
    """
    try:
        data = request.get_json()
        device_name = data.get('device_name', '')
        retailer = data.get('retailer', 'amazon')  # amazon, currys, johnlewis, etc.
        
        if not device_name:
            return jsonify({'error': 'Device name required'}), 400
        
        print(f"[API] Fetching current price from {retailer} for: {device_name}")
        
        price_info = device_scraper.get_retailer_current_price(device_name, retailer)
        
        return jsonify({
            'device': device_name,
            'retailer': retailer,
            'price': price_info['price'],
            'link': price_info['link'],
            'available': price_info['available'],
            'timestamp': time.time()
        }), 200
        
    except Exception as e:
        print(f"Price fetch error: {e}")
        return jsonify({'error': str(e)}), 500

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
    """Generate retailer links for purchasing with fallback options"""
    import urllib.parse
    encoded_name = urllib.parse.quote_plus(device_name)
    
    retailers = {
        'amazon': f"https://www.amazon.co.uk/s?k={encoded_name}",
        'currys': f"https://www.currys.co.uk/search?keyword={encoded_name}",
        'johnlewis': f"https://www.johnlewis.com/search?search-term={encoded_name}",
    }
    
    # Add category-specific retailers
    if any(brand in device_name for brand in ['Apple', 'Mac', 'iPad']):
        retailers['apple'] = "https://www.apple.com/uk/shop"
    
    if any(brand in device_name for brand in ['Microsoft', 'Surface']):
        retailers['microsoft'] = "https://www.microsoft.com/en-gb/store"
    
    if 'Dell' in device_name:
        retailers['dell'] = "https://www.dell.com/en-uk"
    
    if any(brand in device_name for brand in ['HP', 'Hewlett']):
        retailers['hp'] = "https://store.hp.com/UKCtlg/Home"
    
    if 'Lenovo' in device_name:
        retailers['lenovo'] = "https://www.lenovo.com/gb/en"
    
    if 'Samsung' in device_name:
        retailers['samsung'] = "https://www.samsung.com/uk"
    
    if 'ASUS' in device_name:
        retailers['asus'] = "https://www.asus.com/uk"
    
    if 'Google' in device_name or 'Pixel' in device_name:
        retailers['google'] = "https://store.google.com/gb"
    
    # Add Scan and other UK retailers for tech products
    retailers['scan'] = f"https://www.scan.co.uk/search?q={encoded_name}"
    
    return retailers

# --- Hardening Script Generation ---

HARDENING_COMMANDS = {
    'Windows 11': {
        'enable_full_disk_encryption': [
            '# Enable BitLocker on system drive (requires elevation & TPM)',
            'if ((Get-BitLockerVolume -MountPoint C:).VolumeStatus -ne "FullyEncrypted") {',
            '  manage-bde -on C: -UsedSpaceOnly -RecoveryPassword',
            '}',
            'Write-Output "[Info] BitLocker enable command issued (may require reboot)."'
        ],
        'enforce_firewall': [
            'Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True'
        ],
        'disable_smb1': [
            'Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force',
            'Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart'
        ],
        'enable_windows_defender_smart_app_control': [
            '# Smart App Control cannot be force-enabled post installation; placeholder',
            'Write-Output "[Info] Ensure Smart App Control is enabled (manual/UI if needed)."'
        ],
        'enable_automatic_updates': [
            'Set-Service wuauserv -StartupType Automatic',
            'Write-Output "[Info] Windows Update service set to Automatic."'
        ],
        'harden_powershell': [
            'Set-ExecutionPolicy -ExecutionPolicy AllSigned -Scope LocalMachine -Force',
            'Write-Output "[Info] PowerShell execution policy set to AllSigned."'
        ],
        'remove_bloatware_oem': [
            '# Attempt removal of common OEM bloatware (safe sample subset)',
            '$bloat = @("CandyCrush*","Spotify*","Disney*","Xbox*","Cortana")',
            'Get-AppxPackage -AllUsers | Where-Object { $bloat | Where { $_ -like $_.Name } } | ForEach-Object { Remove-AppxPackage -Package $_.PackageFullName -ErrorAction SilentlyContinue }'
        ],
        'enable_bitlocker_network_unlock_note': [
            'Write-Output "[Info] For network unlock configure WDS + DHCP with proper certificates (manual)."'
        ]
    },
    'macOS': {
        'enable_full_disk_encryption': [
            'fdesetup status || fdesetup enable -user "$USER"',
            'echo "[Info] FileVault enable command issued (may prompt)."'
        ],
        'enable_firewall': [
            'defaults write /Library/Preferences/com.apple.alf globalstate -int 1',
            'echo "[Info] macOS Application Firewall enabled."'
        ],
        'enable_gatekeeper': [
            'spctl --master-enable',
            'echo "[Info] Gatekeeper enforced (App notarization)."'
        ],
        'enable_automatic_updates': [
            'softwareupdate --schedule on',
            'defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool TRUE'
        ],
        'disable_remote_login': [
            'systemsetup -setremotelogin off',
            'echo "[Info] Remote Login (SSH) disabled."'
        ],
        'disable_airdrop': [
            'defaults write com.apple.NetworkBrowser DisableAirDrop -bool YES',
            'echo "[Info] AirDrop disabled (user logout/restart may be needed)."'
        ],
        'enforce_password_policy_note': [
            'echo "[Note] Use pwpolicy or MDM to enforce complex password baselines."'
        ]
    },
    'Android': {
        'note_android_enterprise': [
            'echo "[Note] Use Android Enterprise policies via MDM for: encryption, screen lock, patch cadence."'
        ]
    },
    'iPadOS': {
        'note_ipados_mdm': [
            'echo "[Note] Apply configuration profiles via Apple Business Manager / MDM."'
        ]
    },
    'ChromeOS': {
        'note_chromeos_admin_console': [
            'echo "[Note] Enforce policies via Google Admin Console (Verified boot is default)."'
        ]
    },
    'Linux': {
        'enable_firewall': [
            'echo "[Info] Enabling UFW firewall..."',
            'if command -v ufw >/dev/null 2>&1; then sudo ufw enable || true; else echo "[Warn] UFW not installed"; fi'
        ],
        'enable_automatic_updates': [
            'echo "[Info] Ensuring unattended-upgrades present (Debian/Ubuntu)..."',
            'if command -v apt-get >/dev/null 2>&1; then sudo apt-get update -y || true; sudo apt-get install -y unattended-upgrades || true; sudo dpkg-reconfigure -plow unattended-upgrades || true; fi'
        ],
        'disable_root_ssh_login': [
            'echo "[Info] Disabling direct root SSH login..."',
            "sudo sed -i.bak 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config || true",
            'sudo systemctl restart ssh || sudo systemctl restart sshd || true'
        ],
        'install_fail2ban': [
            'echo "[Info] Installing fail2ban (Debian/Ubuntu)..."',
            'if command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y fail2ban || true; fi',
            'sudo systemctl enable --now fail2ban || true'
        ],
        'enforce_password_policy_note': [
            'echo "[Note] Configure PAM (pam_pwquality) & login.defs for password complexity and lockout."'
        ]
    }
}

def sanitize_task_id(label: str) -> str:
    return re.sub(r'[^a-z0-9_]+', '', label.lower().replace(' ', '_'))

def build_hardening_script(os_name: str, task_ids: list):
    os_group = 'Windows 11' if 'Windows' in os_name else os_name
    commands_map = HARDENING_COMMANDS.get(os_group, {})
    shebang = ''
    filename_ext = 'txt'
    if os_group == 'Windows 11':
        shebang = '# PowerShell Hardening Script\nSet-StrictMode -Version Latest\n$ErrorActionPreference = "Stop"\n'
        filename_ext = 'ps1'
    elif os_group in ['macOS', 'Linux']:
        shebang = '#!/bin/bash\nset -euo pipefail\n'
        filename_ext = 'sh'
    else:
        shebang = '#!/bin/sh\n'
        filename_ext = 'sh'

    header = [
        '# =============================================',
        '#  Device Provisioning Toolkit - Hardening Script',
        f'#  Target OS: {os_name}',
        '#  Generated: runtime',
        '#  NOTE: Review before executing with elevated privileges.',
        '# =============================================',
        ''
    ]

    body = []
    for tid in task_ids:
        if tid in commands_map:
            body.append(f"# -- Task: {tid} --")
            body.extend(commands_map[tid])
            body.append('')
        else:
            body.append(f"# [Skipped] Unknown or unsupported task id: {tid}")
    script = shebang + '\n'.join(header + body) + '\n'
    return script, filename_ext

@app.route('/generate-hardening-script', methods=['POST'])
def generate_hardening_script():
    try:
        form_tasks = request.form.getlist('tasks')
        os_name = request.form.get('os', 'Unknown')
        device_id = request.form.get('device_id')

        # Whitelist tasks by sanitization & presence in mapping
        normalized = []
        os_group = 'Windows 11' if 'Windows' in os_name else os_name
        valid_map = HARDENING_COMMANDS.get(os_group, {})
        for t in form_tasks:
            tid = sanitize_task_id(t)
            if tid in valid_map:
                normalized.append(tid)

        if not normalized:
            return Response('No valid tasks selected.', mimetype='text/plain')

        script, ext = build_hardening_script(os_name, normalized)
        fname = f'hardening_device_{device_id or "unknown"}.{ext}'
        return Response(
            script,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename={fname}'}
        )
    except Exception as e:
        return Response(f'Error generating script: {e}', mimetype='text/plain', status=500)

# ---- Asynchronous Scraping (background refresh) ----
SCRAPE_THREAD = None
SCRAPE_LOCK = threading.Lock()

def background_scrape():
    """Refresh devices in background without blocking request thread."""
    print("[AsyncScrape] Background scrape started")
    try:
        real_devices = device_scraper.get_real_device_data()
        if real_devices:
            conn = sqlite3.connect('devices.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM devices')
            for d in real_devices:
                cursor.execute('''INSERT INTO devices (name, category, cpu_speed, ram, storage, screen_size, price)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                               (d['name'], d['category'], d['cpu_speed'], d['ram'], d['storage'], d['screen_size'], d['price']))
            conn.commit()
            conn.close()
            print(f"[AsyncScrape] Updated {len(real_devices)} devices")
        else:
            print("[AsyncScrape] No real devices fetched; skipping update")
    except Exception as e:
        print(f"[AsyncScrape] Error: {e}")
    finally:
        with SCRAPE_LOCK:
            global SCRAPE_THREAD
            SCRAPE_THREAD = None
        print("[AsyncScrape] Background scrape finished")

@app.route('/async-refresh', methods=['POST'])
def async_refresh():
    global SCRAPE_THREAD
    with SCRAPE_LOCK:
        if SCRAPE_THREAD and SCRAPE_THREAD.is_alive():
            return jsonify({'status': 'in_progress'}), 202
        SCRAPE_THREAD = threading.Thread(target=background_scrape, daemon=True)
        SCRAPE_THREAD.start()
    return jsonify({'status': 'started'}), 202


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8002))
    debug_mode = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    app.run(debug=debug_mode, port=port)
