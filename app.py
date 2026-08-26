from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, Response, abort
import os
import sqlite3
import html
from datetime import datetime, timezone, timedelta
try:
    import graphviz
except ImportError:  # Graphviz is optional; the SVG fallback keeps WSGI hosting viable.
    graphviz = None
import random
import threading
import requests
from device_scraper import DeviceDataScraper, FALLBACK_DEVICE_DATA
import re
import time
import functools
import hmac
import ipaddress
import socket
from urllib.parse import urlparse
from integrations.providers import provider_descriptors
from integrations.worker import run_provider

app = Flask(__name__)


def _env_bool(name, default=False):
    return os.environ.get(name, str(default).lower()).lower() in ('1', 'true', 'yes', 'on')


app.config.update(
    # Keep mutable operational actions disabled until an operator explicitly
    # provisions a secret in the hosting environment.
    ADMIN_TOKEN=os.environ.get('PROVISIONING_ADMIN_TOKEN', ''),
    ENABLE_LIVE_SCRAPING=_env_bool('ENABLE_LIVE_SCRAPING'),
    # Sample data is a local test/preview fixture only. It is never enabled by
    # the production default and cannot be reached through a public route.
    ALLOW_SAMPLE_DATA=_env_bool('ALLOW_SAMPLE_DATA'),
    LIVE_DATA_REQUIRED=_env_bool('LIVE_DATA_REQUIRED'),
    PROVIDER_SYNC_ENABLED=_env_bool('PROVIDER_SYNC_ENABLED'),
    CATALOGUE_TTL_HOURS=int(os.environ.get('CATALOGUE_TTL_HOURS', '168')),
    OFFER_TTL_HOURS=int(os.environ.get('OFFER_TTL_HOURS', '48')),
    RETAILER_SEARCH_TERMS=os.environ.get('RETAILER_SEARCH_TERMS', 'laptop,tablet,desktop computer'),
    RETAILER_RESULT_LIMIT=max(1, min(int(os.environ.get('RETAILER_RESULT_LIMIT', '8')), 20)),
    RETAILER_OBSERVATION_TTL_HOURS=max(1, min(int(os.environ.get('RETAILER_OBSERVATION_TTL_HOURS', '12')), 48)),
    RETAILER_REFRESH_INTERVAL_MINUTES=max(15, min(int(os.environ.get('RETAILER_REFRESH_INTERVAL_MINUTES', '360')), 1440)),
    DATABASE_PATH=os.environ.get('DATABASE_PATH', os.path.join(app.root_path, 'devices.db')),
    IMAGE_PROXY_MAX_BYTES=int(os.environ.get('IMAGE_PROXY_MAX_BYTES', '5242880')),
    PUBLIC_RATE_LIMIT=int(os.environ.get('PUBLIC_RATE_LIMIT', '30')),
    PUBLIC_RATE_WINDOW=int(os.environ.get('PUBLIC_RATE_WINDOW', '60')),
    FRONTEND_DIST=os.environ.get('FRONTEND_DIST', os.path.join(app.root_path, 'frontend', 'dist')),
    SERVE_FRONTEND_AT_ROOT=_env_bool('SERVE_FRONTEND_AT_ROOT', True),
    MAX_CONTENT_LENGTH=int(os.environ.get('MAX_CONTENT_LENGTH', '32768')),
)
form_submitted = False
error_occurred = False
devices = []
RATE_LIMIT_STATE = {}
RETAILER_REFRESH_LOCK = threading.Lock()
RETAILER_REFRESH_THREAD = None
SCORE_VERSION = 'v2-transparent-heuristic'
USE_CASES = ('Personal', 'Work', 'Government')
WORK_PROFILES = ('general_office', 'remote_worker', 'developer', 'privileged_admin', 'field_worker')
USE_CASE_LABELS = {
    'Personal': 'Domestic use',
    'Work': 'Business use',
    'Government': 'Government/public-sector use',
}


def _env_hosts(name, default=''):
    return {
        host.strip().lower().rstrip('.')
        for host in os.environ.get(name, default).split(',')
        if host.strip()
    }


def _is_public_hostname(hostname):
    """Reject hostnames that resolve to local, private, or reserved IPs."""
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
        return bool(addresses) and all(not ipaddress.ip_address(address).is_private
                                       and not ipaddress.ip_address(address).is_loopback
                                       and not ipaddress.ip_address(address).is_link_local
                                       and not ipaddress.ip_address(address).is_reserved
                                       for address in addresses)
    except (OSError, ValueError):
        return False


def _allowed_outbound_url(value, env_name, default_hosts):
    parsed = urlparse(value or '')
    hostname = (parsed.hostname or '').lower().rstrip('.')
    if parsed.scheme != 'https' or not hostname or parsed.username or parsed.password:
        return None
    if hostname not in _env_hosts(env_name, default_hosts):
        return None
    if not _is_public_hostname(hostname):
        return None
    return parsed


def public_rate_limited(view):
    """Small single-process guard; use provider/API rate limiting in hosting too."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        now = time.monotonic()
        key = request.remote_addr or 'unknown'
        window = app.config['PUBLIC_RATE_LIMIT']
        bucket = RATE_LIMIT_STATE.get(key, [])
        bucket = [stamp for stamp in bucket if now - stamp < app.config['PUBLIC_RATE_WINDOW']]
        if len(bucket) >= window:
            return jsonify({'error': 'rate limit exceeded'}), 429
        bucket.append(now)
        RATE_LIMIT_STATE[key] = bucket
        return view(*args, **kwargs)
    return wrapped


def admin_mutation_required(view):
    """Protect data-refresh/mutation routes with an operator bearer token.

    The token is intentionally read only from the environment. If it is not
    configured, the route is unavailable rather than accidentally public.
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        configured = app.config.get('ADMIN_TOKEN', '')
        if not configured:
            return jsonify({'error': 'operator action is disabled'}), 503
        supplied = request.headers.get('Authorization', '')
        scheme, _, token = supplied.partition(' ')
        if scheme.lower() != 'bearer' or not token or not hmac.compare_digest(token, configured):
            return jsonify({'error': 'operator authorization required'}), 401
        return view(*args, **kwargs)
    return wrapped


@app.after_request
def add_security_headers(response):
    """Baseline headers suitable for a reverse-proxy hosted deployment."""
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'; object-src 'none'; img-src 'self' https: data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self';"
    )
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response


@app.route('/healthz')
def healthz():
    """Cheap liveness probe. Use /readyz for data readiness."""
    return jsonify({'status': 'ok', 'service': 'device-provisioning-toolkit'}), 200


def _database_readiness():
    """Return non-sensitive database/catalogue readiness information."""
    try:
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        product_count = conn.execute('SELECT COUNT(*) FROM devices').fetchone()[0]
        offer_count = conn.execute('SELECT COUNT(*) FROM device_offers').fetchone()[0]
        conn.close()
        catalogue_state = _catalogue_state(product_count=product_count, offer_count=offer_count)
        ready = catalogue_state not in {'empty', 'unavailable'} or not app.config['LIVE_DATA_REQUIRED']
        if app.config['LIVE_DATA_REQUIRED'] and catalogue_state != 'current':
            ready = False
        return {'ready': ready, 'catalogue_state': catalogue_state,
                'product_count': product_count, 'offer_count': offer_count}
    except (OSError, sqlite3.Error) as exc:
        return {'ready': False, 'catalogue_state': 'unavailable',
                'error': type(exc).__name__}


@app.route('/readyz')
def readyz():
    status = _database_readiness()
    return jsonify({'service': 'device-provisioning-toolkit', **status}), 200 if status['ready'] else 503


@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.root_path, 'static', 'favicon.svg'), mimetype='image/svg+xml')


@app.route('/validate-links', methods=['POST'])
@admin_mutation_required
def validate_links():
    """Validate retailer links for a device (async helper)"""
    try:
        data = request.get_json(silent=True) or {}
        device_name = data.get('device_name', '')
        category = data.get('category', 'device')
        
        retailer_links = get_retailer_links(device_name, category)
        
        # Validate each link (quick check)
        validation_results = {}
        for retailer, url in retailer_links.items():
            try:
                if not _allowed_outbound_url(
                    url,
                    'RETAILER_ALLOWED_HOSTS',
                    'amazon.co.uk,www.amazon.co.uk,currys.co.uk,www.currys.co.uk'
                ):
                    validation_results[retailer] = {'url': url, 'valid': False, 'error': 'host not allowlisted'}
                    continue
                response = requests.head(url, timeout=3, allow_redirects=False)
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
    """Return cached provider results only; never scrape a retailer request path."""
    now = time.time()
    if LIVE_LISTINGS_CACHE['data'] and now - LIVE_LISTINGS_CACHE['ts'] < LIVE_CACHE_TTL:
        return LIVE_LISTINGS_CACHE['data']
    # The legacy scraper remains importable for local maintenance, but is not
    # an approved production data source. Provider workers populate the normal
    # catalogue tables after terms, credentials and rate limits are approved.
    LIVE_LISTINGS_CACHE['data'] = []
    LIVE_LISTINGS_CACHE['ts'] = now
    return []

def ensure_db_indexes():
    try:
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_name ON devices(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_category ON devices(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_price ON devices(price)')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Index creation error: {e}")

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


def _rating_label(score):
    if score >= 85:
        return 'Excellent'
    if score >= 70:
        return 'Good'
    if score >= 55:
        return 'Adequate'
    return 'Needs attention'


def compute_security_score(device: dict, os: str, cpu_vendor: str, use_case: str):
    """Return a transparent security score and the factors that produced it."""
    factors = []
    base_points = 50
    score = base_points
    factors.append({'id': 'baseline', 'label': 'Starting baseline', 'points': base_points,
                    'explanation': 'Neutral starting point before device-specific evidence.'})
    cpu_points = int(round(min(max((device.get('cpu_speed', 0) - 2.5) * 10, 0), 25)))
    score += cpu_points
    factors.append({'id': 'cpu', 'label': 'CPU capability', 'points': cpu_points,
                    'explanation': 'Higher headroom helps updates, security tooling and sustained workloads.'})
    ram_points = 5 if device.get('ram', 0) >= 16 else (2 if device.get('ram', 0) >= 8 else 0)
    score += ram_points
    factors.append({'id': 'memory', 'label': 'Memory headroom', 'points': ram_points,
                    'explanation': 'More memory leaves room for browsers, updates and endpoint protection.'})
    storage_points = 5 if device.get('storage', 0) >= 512 else 0
    score += storage_points
    factors.append({'id': 'storage', 'label': 'Storage headroom', 'points': storage_points,
                    'explanation': 'Adequate free space makes updates, recovery and backups easier.'})

    # OS baseline security
    os_weight = {
        'Windows 11': 10,
        'macOS': 12,
        'ChromeOS': 12,
        'iPadOS': 10,
        'Android': 6
    }
    os_points = os_weight.get(os, 8)
    score += os_points
    factors.append({'id': 'os', 'label': 'Operating-system baseline', 'points': os_points,
                    'explanation': f'{os} security controls are inferred from the product name and category.'})

    # CPU vendor risk adjustments
    if cpu_vendor in ['Intel', 'AMD']:
        score -= 5  # speculative class mitigations overhead and residual risk
        factors.append({'id': 'cpu_risk', 'label': 'CPU risk adjustment', 'points': -5,
                        'explanation': 'Residual speculative-execution risk requires current firmware and OS mitigations.'})
    elif cpu_vendor == 'Apple Silicon':
        score += 3
        factors.append({'id': 'cpu_risk', 'label': 'CPU risk adjustment', 'points': 3,
                        'explanation': 'Apple Silicon receives a small baseline uplift in this heuristic.'})

    # Use-case requirements tighten score caps
    if use_case in ['Government', 'Public Sector']:
        if device.get('ram', 0) < 16 or device.get('cpu_speed', 0) < 3.0:
            score -= 8
            factors.append({'id': 'use_case', 'label': 'Public-sector baseline', 'points': -8,
                            'explanation': 'The selected public-sector context expects at least 16 GB RAM and 3.0 GHz CPU.'})
    elif use_case in ['Work', 'Business', 'Enterprise']:
        if device.get('ram', 0) < 8:
            score -= 5
            factors.append({'id': 'use_case', 'label': 'Business baseline', 'points': -5,
                            'explanation': 'The selected business context penalises devices below the 8 GB RAM baseline.'})

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

    hardware_score = max(0, min(100, int(round(
        min((device.get('cpu_speed', 0) / 5.0) * 100, 100) * 0.5 +
        min((device.get('ram', 0) / 32.0) * 100, 100) * 0.25 +
        min((device.get('storage', 0) / 1000.0) * 100, 100) * 0.25
    ))))
    os_score = {'Windows 11': 82, 'macOS': 90, 'ChromeOS': 86,
                'iPadOS': 87, 'Android': 70, 'Linux': 78}.get(os, 65)
    return score, level, {
        'factors': factors,
        'hardware_rating': hardware_score,
        'hardware_label': _rating_label(hardware_score),
        'os_rating': os_score,
        'os_label': _rating_label(os_score),
    }


def experience_comment(device: dict, os: str, benchmark: dict):
    """Translate the normalized metrics into a useful, non-laboratory comment."""
    ram = int(device.get('ram') or 0)
    storage = int(device.get('storage') or 0)
    cpu = float(device.get('cpu_speed') or 0)
    if benchmark['overall_index'] >= 80:
        summary = 'Should feel responsive for demanding everyday work, multitasking and security tools.'
    elif benchmark['overall_index'] >= 60:
        summary = 'A balanced everyday experience for browsing, documents, calls and normal productivity.'
    else:
        summary = 'Best for lighter workloads; heavier multitasking may feel slower.'
    strengths = []
    tradeoffs = []
    if ram >= 16:
        strengths.append('Good memory headroom for multitasking')
    else:
        tradeoffs.append('8 GB or less may limit heavier multitasking')
    if storage >= 512:
        strengths.append('Comfortable storage for apps and updates')
    else:
        tradeoffs.append('Plan storage management and backups')
    if cpu >= 4:
        strengths.append('Strong CPU headroom')
    else:
        tradeoffs.append('CPU headroom is suited to normal rather than sustained heavy workloads')
    return {'summary': summary, 'strengths': strengths, 'tradeoffs': tradeoffs,
            'os_context': f'Experience comments assume a current, supported {os} installation.'}


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


def _normalise_use_case(value):
    value = str(value or 'Personal').strip()
    return value if value in USE_CASES else 'Personal'


def _normalise_work_profile(value):
    value = str(value or 'general_office').strip()
    return value if value in WORK_PROFILES else 'general_office'


def apply_rule_engine(devices_list: list, use_case: str, work_profile: str = 'general_office'):
    """Filter/enrich devices based on use-case policies and compute security metadata."""
    use_case = _normalise_use_case(use_case)
    work_profile = _normalise_work_profile(work_profile)
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
            'source': d.get('source'),
            'brand': d.get('brand'), 'model': d.get('model'), 'variant': d.get('variant'),
            'mpn': d.get('mpn'), 'gtin': d.get('gtin'), 'sku': d.get('sku'),
            'region': d.get('region'), 'release_date': d.get('release_date'),
            'operating_system': d.get('operating_system'), 'source_state': d.get('source_state'),
        }
        inferred_os, cpu_vendor = infer_os_and_cpu(device['name'] or '', device.get('category') or '')
        os = device.get('operating_system') or inferred_os
        findings, mitigations = detect_known_vulnerabilities(os, cpu_vendor, device['name'] or '')
        score, level, score_details = compute_security_score(device, os, cpu_vendor, use_case)
        recs = hardening_recommendations(os, use_case)

        if use_case == 'Work' and work_profile == 'privileged_admin':
            recs['settings'].append('Use a separate privileged account and phishing-resistant MFA')
        elif use_case == 'Work' and work_profile == 'field_worker':
            recs['settings'].append('Use device tracking, remote lock and offline data protection')
        elif use_case == 'Work' and work_profile == 'developer':
            recs['settings'].append('Separate development credentials and review developer-tool permissions')

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
            'recommendations': recs,
            'score_version': SCORE_VERSION,
            'evidence_quality': 'heuristic',
            'score_factors': score_details['factors'],
            'hardware_rating': score_details['hardware_rating'],
            'hardware_label': score_details['hardware_label'],
            'os_rating': score_details['os_rating'],
            'os_label': score_details['os_label'],
            'limitations': [
                'This is a comparison heuristic, not a certification.',
                'It does not verify firmware, patch status, vendor support or local policy.',
            ],
        }
        device['benchmark'] = compute_benchmark_metrics(device, score)
        device['experience'] = experience_comment(device, os, device['benchmark'])
        device['ratings'] = {
            'security': {'score': score, 'label': level},
            'performance': {'score': device['benchmark']['overall_index'],
                            'label': _rating_label(device['benchmark']['overall_index'])},
            'operating_system': {'score': score_details['os_rating'], 'label': score_details['os_label']},
            'hardware': {'score': score_details['hardware_rating'], 'label': score_details['hardware_label']},
        }
        device['debloat_tools'] = get_debloat_tools(os, device.get('name') or '')
        device['retailer_links'] = get_retailer_links(device['name'], device.get('category') or 'device')
        device['allowed'] = allowed
        device['recommendation_context'] = {
            'use_case': use_case,
            'use_case_label': USE_CASE_LABELS[use_case],
            'work_profile': work_profile if use_case == 'Work' else None,
            'score_version': SCORE_VERSION,
        }
        enriched.append(device)
    return enriched

def query_database(query, params):
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
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
            'image': get_device_image_url(device[1], device[18] if len(device) > 18 else None),
        }
        optional = ('brand', 'model', 'variant', 'mpn', 'gtin', 'sku', 'region',
                    'release_date', 'operating_system', 'source_state', 'image_url')
        for offset, key in enumerate(optional, start=8):
            if len(device) > offset:
                device_dict[key] = device[offset]
        device_list.append(device_dict)
    return device_list

@app.route("/resources")
def resources():
    return jsonify({
        "cybersecurity": "https://www.ncsc.gov.uk/collection/device-security",
        "device_security": "https://www.ncsc.gov.uk/collection/small-business-guide",
        "vulnerability_data": "https://nvd.nist.gov/developers/vulnerabilities",
        "price_guidance": "https://www.gov.uk/government/publications/price-transparency-cma209"
    })


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_expired(value):
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= datetime.now(timezone.utc)
    except ValueError:
        return True


def _derived_identity(name, category='device'):
    """Only used for the explicitly opt-in local fixture catalogue."""
    words = str(name or '').split()
    brand = words[0] if words else 'Unknown'
    return {'brand': brand[:80], 'model': str(name or category)[:120],
            'variant': None, 'mpn': None, 'gtin': None, 'sku': None,
            'region': 'GB', 'identity_quality': 'derived_fixture'}


def _catalogue_state(product_count=None, offer_count=None):
    if product_count is None or offer_count is None:
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        product_count = conn.execute('SELECT COUNT(*) FROM devices').fetchone()[0]
        offer_count = conn.execute('SELECT COUNT(*) FROM device_offers').fetchone()[0]
        conn.close()
    if not product_count:
        return 'empty'
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    sample_count = conn.execute(
        "SELECT COUNT(*) FROM device_catalogue_metadata WHERE source_state = 'sample'"
    ).fetchone()[0]
    current_products = conn.execute(
        "SELECT COUNT(*) FROM device_catalogue_metadata WHERE source_state IN ('verified', 'reviewed', 'observed') "
        "AND (expires_at IS NULL OR expires_at > ?)", (_utc_now(),)
    ).fetchone()[0]
    current_offers = conn.execute(
        "SELECT COUNT(*) FROM device_offers WHERE expires_at IS NULL OR expires_at > ?", (_utc_now(),)
    ).fetchone()[0]
    conn.close()
    if app.config['ALLOW_SAMPLE_DATA'] and sample_count >= product_count:
        return 'sample'
    if not app.config['ALLOW_SAMPLE_DATA'] and sample_count >= product_count and not current_products:
        return 'unavailable'
    if current_products and current_offers:
        return 'current'
    if current_products:
        return 'partial'
    return 'stale'


def _catalogue_metadata_map(device_ids):
    if not device_ids:
        return {}
    placeholders = ','.join('?' for _ in device_ids)
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    rows = conn.execute(
        f'''SELECT device_id, source, source_url, retrieved_at, price_checked_at,
                   availability, expires_at, support_until, warranty,
                   image_license, evidence_url, evidence_quality, source_state,
                   source_license, confidence, freshness_hours
            FROM device_catalogue_metadata WHERE device_id IN ({placeholders})''',
        list(device_ids)
    ).fetchall()
    conn.close()
    return {
        row[0]: {
            'source': row[1], 'source_url': row[2], 'retrieved_at': row[3],
            'price_checked_at': row[4], 'availability': row[5], 'expires_at': row[6],
            'support_until': row[7], 'warranty': row[8], 'image_license': row[9],
            'evidence_url': row[10], 'evidence_quality': row[11],
            'source_state': row[12], 'source_license': row[13],
            'confidence': row[14], 'freshness_hours': row[15],
        } for row in rows
    }


def _vendor_offers_map(device_ids):
    """Return current provider offers sorted by total cost, unknown last."""
    if not device_ids:
        return {}
    placeholders = ','.join('?' for _ in device_ids)
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    rows = conn.execute(
        f'''SELECT device_id, provider, vendor, seller, url, affiliate_url,
                   product_identifier, condition, price, item_price, delivery_price,
                   total_price, currency, availability, stock_message,
                   checked_at, expires_at, source_url, source_license,
                   is_affiliate, is_sponsored
            FROM device_offers WHERE device_id IN ({placeholders})''', list(device_ids)
    ).fetchall()
    conn.close()
    offers = {}
    for row in rows:
        if _is_expired(row[16]):
            continue
        total_price = row[11] if row[11] is not None else row[8]
        offers.setdefault(row[0], []).append({
            'provider': row[1], 'vendor': row[2], 'seller': row[3], 'url': row[4],
            'affiliate_url': row[5], 'product_identifier': row[6], 'condition': row[7],
            'price': row[8], 'item_price': row[9], 'delivery_price': row[10],
            'total_price': total_price, 'total_price_complete': row[11] is not None,
            'currency': row[12], 'availability': row[13], 'stock_message': row[14],
            'checked_at': row[15], 'expires_at': row[16], 'source_url': row[17],
            'source_license': row[18], 'is_affiliate': bool(row[19]),
            'is_sponsored': bool(row[20]),
        })
    for device_id in offers:
        offers[device_id].sort(key=lambda offer: (
            offer['total_price'] is None,
            offer['total_price'] if offer['total_price'] is not None else float('inf'),
            offer['vendor'].lower()
        ))
    return offers


def _evidence_map(table, device_ids):
    if not device_ids:
        return {}
    placeholders = ','.join('?' for _ in device_ids)
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    if table == 'benchmark_results':
        rows = conn.execute(
            f'''SELECT suite, version, workload, score, evidence_type, source_url,
                       licence, tested_at, confidence, notes, device_id
                FROM benchmark_results WHERE device_id IN ({placeholders}) ORDER BY tested_at DESC''',
            list(device_ids)
        ).fetchall()
        values = ({'suite': r[0], 'version': r[1], 'workload': r[2], 'score': r[3],
                   'evidence_type': r[4], 'source_url': r[5], 'licence': r[6],
                   'tested_at': r[7], 'confidence': r[8], 'notes': r[9]} for r in rows)
    elif table == 'security_evidence':
        rows = conn.execute(
            f'''SELECT provider, cve_id, cpe, kev_status, affected_version,
                       fixed_version, source_url, checked_at, evidence_type,
                       confidence, summary, device_id
                FROM security_evidence WHERE device_id IN ({placeholders}) ORDER BY checked_at DESC''',
            list(device_ids)
        ).fetchall()
        values = ({'provider': r[0], 'cve_id': r[1], 'cpe': r[2], 'kev_status': r[3],
                   'affected_version': r[4], 'fixed_version': r[5], 'source_url': r[6],
                   'checked_at': r[7], 'evidence_type': r[8], 'confidence': r[9],
                   'summary': r[10]} for r in rows)
    else:
        conn.close()
        return {}
    result = {}
    for row, value in zip(rows, values):
        result.setdefault(row[-1], []).append(value)
    conn.close()
    return result


def _support_map(device_ids):
    if not device_ids:
        return {}
    placeholders = ','.join('?' for _ in device_ids)
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    rows = conn.execute(
        f'''SELECT operating_system, support_until, patch_cadence, source_url,
                   checked_at, confidence, device_id
            FROM support_lifecycle WHERE device_id IN ({placeholders})''', list(device_ids)
    ).fetchall()
    conn.close()
    return {row[-1]: {'operating_system': row[0], 'support_until': row[1],
                      'patch_cadence': row[2], 'source_url': row[3],
                      'checked_at': row[4], 'confidence': row[5]} for row in rows}


def _api_device(device_row, use_case='Personal', work_profile='general_office', metadata=None, offers=None):
    """Return the stable public device representation used by the Vite app."""
    item = apply_rule_engine(convert_to_dict([device_row]), use_case=use_case, work_profile=work_profile)[0]
    metadata = metadata if metadata is not None else _catalogue_metadata_map([device_row[0]]).get(device_row[0])
    item['catalogue'] = metadata or {
        'source': None, 'source_url': None,
        'retrieved_at': None, 'price_checked_at': None, 'availability': 'unknown',
        'expires_at': None, 'support_until': None, 'warranty': None,
        'image_license': None, 'evidence_url': None, 'evidence_quality': 'unknown',
        'source_state': 'unavailable', 'confidence': 'unknown',
    }
    item['offers'] = offers if offers is not None else (_vendor_offers_map([device_row[0]]).get(device_row[0], []) if device_row[0] else [])
    item['vendor_links'] = [
        {'vendor': vendor, 'url': url, 'price': None, 'availability': 'price not supplied'}
        for vendor, url in item['retailer_links'].items()
    ]
    item['data_quality'] = {
        'catalogue_state': item['catalogue'].get('source_state') or 'unknown',
        'confidence': item['catalogue'].get('confidence') or 'unknown',
        'price_state': ('observed' if item['offers'] and item['catalogue'].get('source_state') == 'observed'
                        else 'verified' if item['offers'] else 'unavailable'),
        'benchmark_state': 'heuristic_estimate',
        'security_state': 'heuristic_rules',
    }
    item['benchmark_evidence'] = _evidence_map('benchmark_results', [device_row[0]]).get(device_row[0], [])
    item['security_evidence'] = _evidence_map('security_evidence', [device_row[0]]).get(device_row[0], [])
    item['support_lifecycle'] = _support_map([device_row[0]]).get(device_row[0])
    return item


def _api_filters(data):
    data = data or {}
    try:
        page = max(1, min(int(data.get('page', 1)), 10000))
        page_size = max(1, min(int(data.get('page_size', 20)), 50))
        price_min = float(data.get('price_min', 0) or 0)
        price_max = float(data.get('price_max', 1000000) or 1000000)
        cpu_speed = float(data.get('cpu_speed', 0) or 0)
        ram = int(data.get('ram', 0) or 0)
        storage = int(data.get('storage', 0) or 0)
        screen_size = float(data.get('screen_size', 0) or 0)
    except (TypeError, ValueError):
        raise ValueError('numeric filters are invalid')
    if price_min < 0 or price_max < price_min or cpu_speed < 0 or ram < 0 or storage < 0 or screen_size < 0:
        raise ValueError('numeric filters are out of range')
    return {
        'query': str(data.get('query', '') or '').strip()[:100],
        'category': str(data.get('category', '') or '').strip()[:40],
        'brand': str(data.get('brand', '') or '').strip()[:40],
        'operating_system': str(data.get('operating_system', '') or '').strip()[:40],
        'use_case': _normalise_use_case(data.get('use_case', 'Personal')),
        'work_profile': _normalise_work_profile(data.get('work_profile', 'general_office')),
        'price_min': price_min, 'price_max': price_max, 'cpu_speed': cpu_speed,
        'ram': ram, 'storage': storage, 'screen_size': screen_size,
        'page': page, 'page_size': page_size,
    }


def _api_catalogue(filters):
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    rows = conn.execute('SELECT * FROM devices ORDER BY id').fetchall()
    conn.close()
    query = filters['query'].lower()
    category = filters['category'].lower()
    brand = filters['brand'].lower()
    operating_system = filters['operating_system'].lower()
    matched = []
    metadata_map = _catalogue_metadata_map([row[0] for row in rows])
    offers_map = _vendor_offers_map([row[0] for row in rows])
    for row in rows:
        metadata = metadata_map.get(row[0]) or {}
        if not app.config['ALLOW_SAMPLE_DATA'] and metadata.get('source_state') == 'sample':
            continue
        name, row_category = (row[1] or '').lower(), (row[2] or '').lower()
        row_brand = (row[8] if len(row) > 8 else '') or (row[1] or '').split(' ', 1)[0]
        if query and query not in name:
            continue
        if category and category not in row_category:
            continue
        if brand and brand not in str(row_brand).lower():
            continue
        if row[7] is not None and not (filters['price_min'] <= row[7] <= filters['price_max']):
            continue
        if row[3] < filters['cpu_speed'] or row[4] < filters['ram'] or row[5] < filters['storage'] or row[6] < filters['screen_size']:
            continue
        if operating_system and operating_system not in infer_os_and_cpu(row[1] or '', row[2] or '')[0].lower():
            continue
        matched.append(_api_device(row, filters['use_case'], filters['work_profile'], metadata, offers_map.get(row[0], [])))
    matched.sort(key=lambda item: (
        not item.get('allowed', True),
        -(item.get('security') or {}).get('score', 0),
        -(item.get('benchmark') or {}).get('overall_index', 0),
        (item.get('offers') or [{}])[0].get('total_price', float('inf')),
        item.get('name', '').lower(),
    ))
    start = (filters['page'] - 1) * filters['page_size']
    end = start + filters['page_size']
    return matched[start:end], len(matched)


@app.route('/api/v1/healthz')
def api_healthz():
    return jsonify({'status': 'ok', 'service': 'device-provisioning-toolkit', 'api_version': 'v1',
                    'catalogue_state': _catalogue_state(),
                    'live_data_required': app.config['LIVE_DATA_REQUIRED']})


@app.route('/api/v1/catalogue/status', methods=['GET'])
@public_rate_limited
def api_catalogue_status():
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    rows = conn.execute('''SELECT source, MIN(source_url), MAX(retrieved_at),
                          MAX(price_checked_at), COUNT(*)
                          FROM device_catalogue_metadata GROUP BY source
                          ORDER BY MAX(retrieved_at) DESC''').fetchall()
    product_count = conn.execute('SELECT COUNT(*) FROM devices').fetchone()[0]
    offer_count = conn.execute('SELECT COUNT(*) FROM device_offers').fetchone()[0]
    current_offer_count = conn.execute(
        'SELECT COUNT(*) FROM device_offers WHERE expires_at IS NULL OR expires_at > ?', (_utc_now(),)
    ).fetchone()[0]
    benchmark_count = conn.execute('SELECT COUNT(DISTINCT device_id) FROM benchmark_results').fetchone()[0]
    security_count = conn.execute('SELECT COUNT(DISTINCT device_id) FROM security_evidence').fetchone()[0]
    identity_count = conn.execute("SELECT COUNT(*) FROM devices WHERE brand IS NOT NULL AND model IS NOT NULL").fetchone()[0]
    sample_count = conn.execute("SELECT COUNT(*) FROM device_catalogue_metadata WHERE source_state = 'sample'").fetchone()[0]
    source_state_rows = conn.execute(
        'SELECT source_state, COUNT(*) FROM device_catalogue_metadata GROUP BY source_state ORDER BY source_state'
    ).fetchall()
    conn.close()
    visible_product_count = product_count if app.config['ALLOW_SAMPLE_DATA'] else max(0, product_count - sample_count)
    return jsonify({
        'api_version': 'v1', 'product_count': visible_product_count,
        'catalogue_state': _catalogue_state(product_count=product_count, offer_count=offer_count),
        'live_scraping': False,
        'retailer_observation_enabled': app.config['ENABLE_LIVE_SCRAPING'],
        'catalogue_mode': 'retailer_observation' if any(row[0] == 'observed' for row in source_state_rows) else 'provider_feed',
        'catalogue_disclaimer': ('Retailer page observations are not retailer-authorised feeds. '
                                 'Verify price, stock, condition and specifications on the retailer site.'),
        'source_states': {row[0] or 'unknown': row[1] for row in source_state_rows},
        'sample_data': app.config['ALLOW_SAMPLE_DATA'],
        'live_data_required': app.config['LIVE_DATA_REQUIRED'],
        'offer_count': offer_count, 'current_offer_count': current_offer_count,
        'benchmark_coverage': benchmark_count,
        'security_evidence_coverage': security_count,
        'identity_coverage': identity_count,
        'providers': provider_descriptors(),
        'sources': [{'source': row[0], 'source_url': row[1], 'retrieved_at': row[2],
                     'price_checked_at': row[3], 'product_count': row[4]} for row in rows],
    })


@app.route('/api/v1/sources/<path:source>/status', methods=['GET'])
@public_rate_limited
def api_source_status(source):
    """Return coarse freshness status without exposing provider internals."""
    source = str(source or '').strip()[:160]
    if not source:
        return jsonify({'error': 'source is required'}), 400
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    row = conn.execute('''SELECT MAX(retrieved_at), MAX(price_checked_at),
                                MAX(expires_at), COUNT(*)
                         FROM device_catalogue_metadata WHERE source = ?''', (source,)).fetchone()
    conn.close()
    if not row or not row[3]:
        return jsonify({'source': source, 'status': 'unknown', 'product_count': 0, 'api_version': 'v1'}), 200
    expires_at = row[2]
    stale = bool(expires_at and expires_at < _utc_now())
    return jsonify({
        'api_version': 'v1', 'source': source,
        'status': 'stale' if stale else 'available',
        'product_count': row[3], 'retrieved_at': row[0],
        'price_checked_at': row[1], 'expires_at': expires_at,
    })


@app.route('/api/v1/devices', methods=['GET'])
@public_rate_limited
def api_devices():
    try:
        filters = _api_filters(request.args)
        items, total = _api_catalogue(filters)
        return jsonify({'items': items, 'page': filters['page'], 'page_size': filters['page_size'], 'total': total, 'live_scraping': False})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/api/v1/devices/<int:device_id>', methods=['GET'])
@public_rate_limited
def api_device(device_id):
    use_case = _normalise_use_case(request.args.get('use_case', 'Personal'))
    work_profile = _normalise_work_profile(request.args.get('work_profile', 'general_office'))
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    row = conn.execute('SELECT * FROM devices WHERE id = ?', (device_id,)).fetchone()
    metadata = conn.execute('SELECT source_state FROM device_catalogue_metadata WHERE device_id = ?', (device_id,)).fetchone()
    conn.close()
    if not row or (not app.config['ALLOW_SAMPLE_DATA'] and metadata and metadata[0] == 'sample'):
        return jsonify({'error': 'device not found'}), 404
    return jsonify({'item': _api_device(row, use_case, work_profile), 'api_version': 'v1'})


@app.route('/api/v1/search', methods=['POST'])
@public_rate_limited
def api_search():
    try:
        filters = _api_filters(request.get_json(silent=True) or {})
        items, total = _api_catalogue(filters)
        return jsonify({'items': items, 'page': filters['page'], 'page_size': filters['page_size'], 'total': total, 'live_scraping': False, 'api_version': 'v1'})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/api/v1/devices/<int:device_id>/comparisons', methods=['GET'])
@public_rate_limited
def api_comparisons(device_id):
    category = request.args.get('category', 'same')
    price_range = request.args.get('price_range', 'similar')
    performance = request.args.get('performance', 'similar')
    use_case = _normalise_use_case(request.args.get('use_case', 'Personal'))
    work_profile = _normalise_work_profile(request.args.get('work_profile', 'general_office'))
    if category not in {'same', 'all'} or price_range not in {'similar', 'lower', 'higher', 'all'} or performance not in {'similar', 'higher', 'all'}:
        return jsonify({'error': 'comparison filter is invalid'}), 400
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    current = conn.execute('SELECT * FROM devices WHERE id = ?', (device_id,)).fetchone()
    if not current:
        conn.close()
        return jsonify({'items': [], 'total': 0, 'api_version': 'v1'}), 200
    query = 'SELECT * FROM devices WHERE id != ?'
    params = [device_id]
    if category == 'same':
        query += ' AND category = ?'
        params.append(current[2])
    if price_range == 'similar':
        query += ' AND price BETWEEN ? AND ?'
        params.extend([current[7] - 200, current[7] + 200])
    elif price_range == 'lower':
        query += ' AND price < ?'
        params.append(current[7])
    elif price_range == 'higher':
        query += ' AND price > ?'
        params.append(current[7])
    if performance == 'similar':
        query += ' AND cpu_speed BETWEEN ? AND ?'
        params.extend([current[3] - 0.5, current[3] + 0.5])
    elif performance == 'higher':
        query += ' AND cpu_speed > ?'
        params.append(current[3])
    rows = conn.execute(query + ' LIMIT 6', params).fetchall()
    conn.close()
    metadata_map = _catalogue_metadata_map([row[0] for row in rows])
    return jsonify({'items': [_api_device(row, use_case, work_profile, metadata_map.get(row[0])) for row in rows], 'total': len(rows), 'api_version': 'v1'})


@app.route('/api/v1/criteria', methods=['GET'])
@public_rate_limited
def api_criteria():
    """Return bounded, data-backed choices for the guided frontend."""
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    visibility_clause = '' if app.config['ALLOW_SAMPLE_DATA'] else " AND COALESCE(m.source_state, 'sample') != 'sample'"
    categories = [row[0] for row in conn.execute(
        f'''SELECT DISTINCT d.category FROM devices d
            LEFT JOIN device_catalogue_metadata m ON m.device_id = d.id
            WHERE d.category IS NOT NULL {visibility_clause} ORDER BY d.category'''
    ).fetchall()]
    known_brands = ('Acer', 'Apple', 'ASUS', 'Dell', 'Google', 'HP', 'Lenovo', 'Microsoft', 'Samsung')
    names = [str(row[0] or '').lower() for row in conn.execute(
        f'''SELECT d.name FROM devices d LEFT JOIN device_catalogue_metadata m ON m.device_id = d.id
            WHERE 1=1 {visibility_clause}''').fetchall()]
    brands = [brand for brand in known_brands if any(brand.lower() in name for name in names)]
    conn.close()
    return jsonify({
        'api_version': 'v1',
        'use_cases': [{'id': key, 'label': USE_CASE_LABELS[key]} for key in USE_CASES],
        'work_profiles': [
            {'id': 'general_office', 'label': 'General office'},
            {'id': 'remote_worker', 'label': 'Remote worker'},
            {'id': 'developer', 'label': 'Developer or technical user'},
            {'id': 'privileged_admin', 'label': 'Privileged administrator'},
            {'id': 'field_worker', 'label': 'Field or mobile worker'},
        ],
        'categories': categories,
        'operating_systems': ['Windows 11', 'macOS', 'ChromeOS', 'Android', 'iPadOS', 'Linux'],
        'brands': brands[:40],
    })


def serve_frontend(filename='index.html'):
    """Serve a built Vite app when present; templates remain the fallback."""
    dist = app.config['FRONTEND_DIST']
    if not os.path.isdir(dist):
        abort(404)
    requested = filename or 'index.html'
    path = os.path.join(dist, requested)
    if not os.path.isfile(path):
        requested = 'index.html'
    return send_from_directory(dist, requested)


@app.route('/app', defaults={'filename': 'index.html'})
@app.route('/app/', defaults={'filename': 'index.html'})
@app.route('/app/<path:filename>')
def frontend_app(filename):
    return serve_frontend(filename)


@app.route('/assets/<path:filename>')
def frontend_assets(filename):
    """Expose Vite's immutable assets when the bundle is mounted at root."""
    dist = app.config['FRONTEND_DIST']
    asset_path = os.path.join(dist, 'assets', filename)
    if not os.path.isfile(asset_path):
        abort(404)
    return send_from_directory(os.path.join(dist, 'assets'), filename)

@app.route("/", methods=["GET", "POST"])
def index():
    global form_submitted, error_occurred, devices
    if app.config['SERVE_FRONTEND_AT_ROOT'] and os.path.isdir(app.config['FRONTEND_DIST']):
        return serve_frontend('index.html')
    light_mode_image = 'static/images/backgrounds/2.jpg'
    dark_mode_image = 'static/images/backgrounds/1.png'
    form_submitted = False
    error_occurred = False
    
    # Fetch recommended devices from the database
    print("Getting recommended devices")
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
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
            # Retained legacy form handling never activates retailer scraping.
            # Provider workers populate the reviewed API catalogue instead.
            elif name and app.config['PROVIDER_SYNC_ENABLED'] and False:
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
                    
            else:  # Live search disabled or no search term: use local catalogue
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
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
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
    usage_to_table = {
        'Personal': 'PersonalUseSoftware',
        'Student': 'StudentUseSoftware',
        'Work': 'WorkUseSoftware',
        'Government': 'GovernmentUseSoftware'
    }

    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()

    table_name = usage_to_table.get(usage, 'PersonalUseSoftware')  # Default to PersonalUseSoftware if usage is not found

    query = f"SELECT Software FROM {table_name}"
    cursor.execute(query)

    software_entries = cursor.fetchall()

    query = "SELECT * FROM SecurityRecommendations"
    cursor.execute(query)
    security_entries = cursor.fetchall()

    conn.close()

    output_base = os.path.join(app.static_folder or os.path.join(app.root_path, 'static'), 'flowcharts', str(device['id']))
    os.makedirs(os.path.dirname(output_base), exist_ok=True)
    if graphviz is not None:
        try:
            dot = graphviz.Digraph(comment='Device Recommendations')
            dot.node('A', f'Device: {device["name"]}')
            dot.node('B', 'Recommended Software')
            dot.node('C', 'Security Measures')
            dot.edges(['AB', 'AC'])
            for i, entry in enumerate(software_entries, start=1):
                dot.node(f'S{i}', entry[0])
                dot.edge('B', f'S{i}')
            for i, entry in enumerate(security_entries, start=1):
                dot.node(f'C{i}', entry[1])
                dot.edge('C', f'C{i}')
            dot.render(output_base, format='svg', cleanup=True)
        except Exception as exc:
            print(f"Graphviz unavailable; using simple SVG fallback: {exc}")
            _write_flowchart_fallback(output_base, device, software_entries, security_entries)
    else:
        _write_flowchart_fallback(output_base, device, software_entries, security_entries)

    return output_base + '.svg'


def _write_flowchart_fallback(output_base, device, software_entries, security_entries):
    """Write a readable static SVG when the Graphviz binary is unavailable."""
    labels = [f'Device: {device["name"]}', 'Recommended software']
    labels.extend(entry[0] for entry in software_entries[:6])
    labels.append('Security measures')
    labels.extend(entry[1] for entry in security_entries[:6])
    rows = []
    for index, label in enumerate(labels):
        safe_label = html.escape(str(label)[:120])
        y = 36 + index * 28
        rows.append(f'<text x="24" y="{y}" fill="#17324d" font-family="Arial" font-size="15">{safe_label}</text>')
    height = max(70, 20 + len(rows) * 28)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" viewBox="0 0 760 {height}"><rect width="100%" height="100%" fill="#f4f8fb"/><rect x="10" y="10" width="740" height="{height - 20}" rx="12" fill="#dcecf5"/>{"".join(rows)}</svg>'
    with open(output_base + '.svg', 'w', encoding='utf-8') as handle:
        handle.write(svg)

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
    """Bootstrap the explicitly selected catalogue mode when the database is empty."""
    if app.config['ENABLE_LIVE_SCRAPING'] and not app.config['ALLOW_SAMPLE_DATA']:
        result = refresh_retailer_observation_catalogue()
        print(f"Retailer observation bootstrap: {result['status']} ({result['item_count']} products)")
        return
    if not app.config['ALLOW_SAMPLE_DATA']:
        print('Catalogue bootstrap skipped: no catalogue source is enabled')
        return
    try:
        print("Loading explicitly enabled local catalogue fixture...")
        real_devices = device_scraper.load_devices_from_csv('devices.csv')
        if not real_devices:
            real_devices = FALLBACK_DEVICE_DATA
        replace_catalogue(real_devices, feed_source='Local development fixture')
        print(f"Successfully populated database with {len(real_devices)} devices")
    except Exception as e:
        print(f"Error populating database: {e}")


def _retailer_search_terms():
    terms = [term.strip()[:80] for term in str(app.config['RETAILER_SEARCH_TERMS']).split(',') if term.strip()]
    return terms[:10] or ['laptop', 'tablet', 'desktop computer']


def _observed_operating_system(name):
    """Return only an OS family that the product name makes explicit."""
    lowered = str(name or '').lower()
    if 'chromebook' in lowered or 'chromeos' in lowered:
        return 'ChromeOS'
    if 'windows 11' in lowered:
        return 'Windows 11'
    if 'ipad' in lowered:
        return 'iPadOS'
    if 'macbook' in lowered or 'imac' in lowered:
        return 'macOS'
    if 'galaxy tab' in lowered or 'android' in lowered:
        return 'Android'
    return None


def build_retailer_observation_feed(observations=None):
    """Convert bounded retailer cards into a validated, clearly labelled feed."""
    checked_at = _utc_now()
    expires_at = (datetime.now(timezone.utc) + timedelta(
        hours=app.config['RETAILER_OBSERVATION_TTL_HOURS']
    )).replace(microsecond=0).isoformat()
    if observations is None:
        observations = device_scraper.collect_retailer_observations(
            _retailer_search_terms(), max_per_source=app.config['RETAILER_RESULT_LIMIT']
        )
    disclaimer = ('Unofficial retailer page observation; verify product, condition, stock, '
                  'specifications and price on the retailer site before purchase.')
    products_by_name = {}
    for observation in observations:
        name = str(observation.get('name') or '').strip()[:160]
        retailer = str(observation.get('retailer') or observation.get('source') or '').strip()[:80]
        product_url = str(observation.get('product_url') or '').strip()
        try:
            price = float(observation.get('price'))
        except (TypeError, ValueError):
            continue
        parsed_url = urlparse(product_url)
        if (not name or not retailer or price <= 0 or parsed_url.scheme != 'https' or
                not parsed_url.hostname or parsed_url.username or parsed_url.password or
                parsed_url.hostname.lower() not in {
                    'amazon.co.uk', 'www.amazon.co.uk', 'johnlewis.com', 'www.johnlewis.com'
                }):
            continue
        brand = str(observation.get('brand') or name.split(' ', 1)[0]).strip()[:80] or 'Unknown'
        key = re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()
        offer = {
            'provider': 'retailer_page_observation', 'vendor': retailer,
            'url': product_url, 'price': price, 'item_price': price,
            'total_price': price, 'currency': 'GBP',
            'availability': 'observed', 'stock_message': 'Shown on retailer search page',
            'condition': str(observation.get('condition') or 'new')[:30],
            'product_identifier': observation.get('product_identifier') or name,
            'checked_at': checked_at, 'expires_at': expires_at,
            'source_url': product_url, 'source_license': disclaimer,
            'is_affiliate': False, 'is_sponsored': False,
        }
        if key in products_by_name:
            existing = products_by_name[key]
            if not any(item['vendor'] == retailer and item['url'] == product_url for item in existing['offers']):
                existing['offers'].append(offer)
            existing['price'] = min(existing['price'], price)
            continue
        products_by_name[key] = {
            'name': name, 'brand': brand, 'model': name,
            'category': str(observation.get('category') or 'Laptops')[:60],
            'cpu_speed': max(0.0, float(observation.get('cpu_speed') or 0)),
            'ram': max(0, int(observation.get('ram') or 0)),
            'storage': max(0, int(observation.get('storage') or 0)),
            'screen_size': max(0.0, float(observation.get('screen_size') or 0)),
            'price': price, 'availability': 'observed',
            'source': f'{retailer} page observation', 'source_url': product_url,
            'price_checked_at': checked_at, 'expires_at': expires_at,
            'evidence_url': product_url, 'evidence_quality': 'vendor',
            'source_license': disclaimer, 'confidence': 'low',
            'freshness_hours': app.config['RETAILER_OBSERVATION_TTL_HOURS'],
            'operating_system': _observed_operating_system(name),
            'image_url': None, 'source_state': 'observed', 'offers': [offer],
        }
    payload = {
        'source': 'Retailer page observations',
        'retrieved_at': checked_at,
        'products': list(products_by_name.values())[:500],
    }
    if not payload['products']:
        return [], payload['source'], None, checked_at
    return validate_catalogue_feed(payload)


def _record_provider_run(result):
    try:
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        conn.execute(
            '''INSERT INTO provider_runs (provider, status, started_at, completed_at, item_count, error_summary)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (result['provider'], result['status'], result['started_at'], result.get('completed_at'),
             result.get('item_count', 0), result.get('error_summary'))
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        print(f"Could not record retailer observation run: {type(exc).__name__}")


def refresh_retailer_observation_catalogue(observations=None):
    """Refresh atomically; a failed observation never erases the last catalogue."""
    started_at = _utc_now()
    if not RETAILER_REFRESH_LOCK.acquire(blocking=False):
        return {'provider': 'retailer_page_observation', 'status': 'already_running',
                'started_at': started_at, 'completed_at': _utc_now(), 'item_count': 0}
    try:
        products, source, source_url, retrieved_at = build_retailer_observation_feed(observations)
        if not products:
            result = {'provider': 'retailer_page_observation', 'status': 'no_results',
                      'started_at': started_at, 'completed_at': _utc_now(), 'item_count': 0,
                      'error_summary': 'No valid retailer observations were returned; previous data was preserved.'}
        else:
            replace_catalogue(products, source, source_url, retrieved_at)
            result = {'provider': 'retailer_page_observation', 'status': 'completed',
                      'started_at': started_at, 'completed_at': _utc_now(), 'item_count': len(products)}
        _record_provider_run(result)
        return result
    except Exception as exc:
        result = {'provider': 'retailer_page_observation', 'status': 'failed',
                  'started_at': started_at, 'completed_at': _utc_now(), 'item_count': 0,
                  'error_summary': f'{type(exc).__name__}: retailer observation failed'[:200]}
        _record_provider_run(result)
        return result
    finally:
        RETAILER_REFRESH_LOCK.release()


def _retailer_refresh_loop():
    interval = app.config['RETAILER_REFRESH_INTERVAL_MINUTES'] * 60
    stop_event = threading.Event()
    while not stop_event.wait(interval):
        result = refresh_retailer_observation_catalogue()
        print(f"Scheduled retailer observation: {result['status']} ({result['item_count']} products)")


def start_retailer_refresh_worker():
    global RETAILER_REFRESH_THREAD
    if not app.config['ENABLE_LIVE_SCRAPING'] or RETAILER_REFRESH_THREAD:
        return
    RETAILER_REFRESH_THREAD = threading.Thread(
        target=_retailer_refresh_loop, name='retailer-observation-refresh', daemon=True
    )
    RETAILER_REFRESH_THREAD.start()

def populate_fallback_data():
    """Compatibility helper for local fixture tests; never an implicit fallback."""
    if not app.config['ALLOW_SAMPLE_DATA']:
        raise RuntimeError('sample data is disabled')
    replace_catalogue(FALLBACK_DEVICE_DATA, feed_source='Local development fixture')
    print(f"Populated database with {len(FALLBACK_DEVICE_DATA)} local fixture devices")


def replace_catalogue(products, feed_source='Curated local catalogue', feed_source_url=None, retrieved_at=None):
    """Atomically replace the catalogue and its evidence records.

    This function accepts only already-normalised operator/test feed records.
    It never calls a scraper or invents an offer, benchmark or vulnerability.
    """
    retrieved_at = retrieved_at or _utc_now()
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM device_offers')
        cursor.execute('DELETE FROM benchmark_results')
        cursor.execute('DELETE FROM security_evidence')
        cursor.execute('DELETE FROM support_lifecycle')
        cursor.execute('DELETE FROM device_catalogue_metadata')
        cursor.execute('DELETE FROM devices')
        for product in products:
            identity = product.get('identity') or _derived_identity(product.get('name'), product.get('category'))
            source_state = str(product.get('source_state') or (
                'sample' if 'fixture' in str(feed_source).lower() or 'sample' in str(feed_source).lower()
                else 'reviewed'
            ))[:24]
            cursor.execute('''INSERT INTO devices
                (name, category, cpu_speed, ram, storage, screen_size, price,
                 brand, model, variant, mpn, gtin, sku, region, release_date,
                 operating_system, source_state, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (product['name'], product['category'], product['cpu_speed'],
                 product['ram'], product['storage'], product['screen_size'], product.get('price'),
                 identity.get('brand'), identity.get('model'), identity.get('variant'),
                 identity.get('mpn'), identity.get('gtin'), identity.get('sku'), identity.get('region', 'GB'),
                 product.get('release_date'), product.get('operating_system'), source_state,
                 product.get('image_url')))
            device_id = cursor.lastrowid
            cursor.execute('''INSERT INTO device_catalogue_metadata
                (device_id, source, source_url, retrieved_at, price_checked_at,
                 availability, expires_at, support_until, warranty, image_license,
                 evidence_url, evidence_quality, source_state, source_license,
                 confidence, freshness_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (device_id, str(product.get('source') or feed_source)[:160],
                 product.get('source_url') or feed_source_url, retrieved_at,
                 product.get('price_checked_at') or retrieved_at,
                 str(product.get('availability') or 'unknown')[:40],
                 product.get('expires_at'), product.get('support_until'),
                 product.get('warranty'), product.get('image_license'),
                 product.get('evidence_url'), product.get('evidence_quality', 'reviewed'), source_state,
                 product.get('source_license'), product.get('confidence', 'medium'),
                 product.get('freshness_hours', app.config['CATALOGUE_TTL_HOURS'])))
            for offer in product.get('offers', []):
                cursor.execute('''INSERT INTO device_offers
                    (device_id, provider, vendor, seller, url, affiliate_url,
                     product_identifier, condition, price, item_price, delivery_price,
                     total_price, currency, availability, stock_message,
                     checked_at, expires_at, source_url, source_license,
                     is_affiliate, is_sponsored)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (device_id, offer.get('provider') or product.get('source') or feed_source,
                     offer['vendor'], offer.get('seller'), offer['url'], offer.get('affiliate_url'),
                     offer.get('product_identifier') or identity.get('gtin') or identity.get('mpn') or identity.get('model'),
                     offer.get('condition', 'new'), offer.get('price'), offer.get('item_price', offer.get('price')),
                     offer.get('delivery_price'), offer.get('total_price', offer.get('price')),
                     offer.get('currency', 'GBP'), offer.get('availability', 'unknown'), offer.get('stock_message'),
                     offer.get('checked_at') or retrieved_at, offer.get('expires_at'),
                     offer.get('source_url') or product.get('source_url') or feed_source_url,
                     offer.get('source_license') or product.get('source_license'),
                     int(bool(offer.get('is_affiliate'))), int(bool(offer.get('is_sponsored')))))
            for benchmark in product.get('benchmarks', []):
                cursor.execute('''INSERT INTO benchmark_results
                    (device_id, suite, version, workload, score, evidence_type,
                     source_url, licence, tested_at, confidence, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (device_id, benchmark.get('suite'), benchmark.get('version'), benchmark.get('workload'),
                     benchmark.get('score'), benchmark.get('evidence_type', 'unknown'), benchmark.get('source_url'),
                     benchmark.get('licence'), benchmark.get('tested_at') or retrieved_at,
                     benchmark.get('confidence', 'medium'), benchmark.get('notes')))
            for evidence in product.get('security_evidence', []):
                cursor.execute('''INSERT INTO security_evidence
                    (device_id, provider, cve_id, cpe, kev_status, affected_version,
                     fixed_version, source_url, checked_at, evidence_type, confidence, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (device_id, evidence.get('provider'), evidence.get('cve_id'), evidence.get('cpe'),
                     evidence.get('kev_status'), evidence.get('affected_version'), evidence.get('fixed_version'),
                     evidence.get('source_url'), evidence.get('checked_at') or retrieved_at,
                     evidence.get('evidence_type', 'independent_published'), evidence.get('confidence', 'medium'),
                     evidence.get('summary')))
            support = product.get('support_lifecycle')
            if support:
                cursor.execute('''INSERT INTO support_lifecycle
                    (device_id, operating_system, support_until, patch_cadence,
                     source_url, checked_at, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (device_id, support.get('operating_system') or product.get('operating_system'),
                     support.get('support_until'), support.get('patch_cadence'), support.get('source_url'),
                     support.get('checked_at') or retrieved_at, support.get('confidence', 'medium')))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def validate_catalogue_feed(payload):
    """Validate a product-only feed before it can replace the catalogue."""
    if not isinstance(payload, dict):
        raise ValueError('feed must be a JSON object')
    products = payload.get('products')
    if not isinstance(products, list) or not products or len(products) > 500:
        raise ValueError('feed must contain between 1 and 500 products')
    source = str(payload.get('source') or '').strip()
    if not source or len(source) > 160:
        raise ValueError('feed source is required and must be 160 characters or fewer')
    source_url = payload.get('source_url')
    if source_url:
        parsed = urlparse(str(source_url))
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('source_url must be an HTTPS attribution URL without credentials')
    retrieved_at = str(payload.get('retrieved_at') or _utc_now())
    normalised = []
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            raise ValueError(f'product {index + 1} must be an object')
        try:
            brand = str(product['brand']).strip()[:80]
            model = str(product['model']).strip()[:120]
            if not brand or not model:
                raise ValueError('brand and model are required')
            item = {
                'name': str(product['name']).strip()[:160],
                'category': str(product['category']).strip()[:60],
                'identity': {
                    'brand': brand, 'model': model,
                    'variant': str(product.get('variant') or '').strip()[:120] or None,
                    'mpn': str(product.get('mpn') or '').strip()[:80] or None,
                    'gtin': str(product.get('gtin') or '').strip()[:32] or None,
                    'sku': str(product.get('sku') or '').strip()[:80] or None,
                    'region': str(product.get('region') or 'GB').strip()[:8].upper(),
                },
                'cpu_speed': float(product.get('cpu_speed', 0)),
                'ram': int(product.get('ram', 0)),
                'storage': int(product.get('storage', 0)),
                'screen_size': float(product.get('screen_size', 0)),
                'price': float(product['price']) if product.get('price') is not None else None,
                'availability': str(product.get('availability') or 'unknown')[:40],
                'source': str(product.get('source') or source).strip()[:160],
                'source_url': product.get('source_url') or source_url,
                'price_checked_at': product.get('price_checked_at') or retrieved_at,
                'expires_at': product.get('expires_at'),
                'support_until': product.get('support_until'),
                'warranty': str(product.get('warranty') or '')[:160] or None,
                'image_license': str(product.get('image_license') or '')[:160] or None,
                'evidence_url': product.get('evidence_url'),
                'evidence_quality': str(product.get('evidence_quality') or 'reviewed')[:40],
                'source_license': str(product.get('source_license') or '')[:200] or None,
                'confidence': str(product.get('confidence') or 'medium')[:20],
                'freshness_hours': int(product.get('freshness_hours') or app.config['CATALOGUE_TTL_HOURS']),
                'release_date': product.get('release_date'),
                'operating_system': str(product.get('operating_system') or '')[:80] or None,
                'image_url': product.get('image_url'),
                'source_state': str(product.get('source_state') or 'reviewed')[:24],
                'benchmarks': product.get('benchmarks') or [],
                'security_evidence': product.get('security_evidence') or [],
                'support_lifecycle': product.get('support_lifecycle'),
                'offers': product.get('offers') or [],
            }
        except (KeyError, TypeError, ValueError):
            raise ValueError(f'product {index + 1} has invalid fields')
        for date_field in ('price_checked_at', 'expires_at', 'support_until'):
            if item[date_field] is not None and (not isinstance(item[date_field], str) or len(item[date_field]) > 80):
                raise ValueError(f'product {index + 1} has invalid {date_field}')
        for url_field in ('source_url', 'evidence_url'):
            if item[url_field]:
                parsed_url = urlparse(str(item[url_field]))
                if parsed_url.scheme != 'https' or not parsed_url.hostname or parsed_url.username or parsed_url.password:
                    raise ValueError(f'product {index + 1} has invalid {url_field}')
        if item['evidence_quality'] not in {'reviewed', 'vendor', 'independent', 'unknown'}:
            raise ValueError(f'product {index + 1} has invalid evidence_quality')
        if item['source_state'] not in {'verified', 'reviewed', 'observed', 'sample'}:
            raise ValueError(f'product {index + 1} has invalid source_state')
        if item['confidence'] not in {'high', 'medium', 'low', 'unknown'}:
            raise ValueError(f'product {index + 1} has invalid confidence')
        if item['image_url']:
            image_url = urlparse(str(item['image_url']))
            if image_url.scheme != 'https' or not image_url.hostname or image_url.username or image_url.password:
                raise ValueError(f'product {index + 1} has invalid image_url')
        offers = []
        if not isinstance(product.get('offers', []), list) or len(product.get('offers', [])) > 30:
            raise ValueError(f'product {index + 1} has invalid offers')
        for offer_index, offer in enumerate(product.get('offers', [])):
            if not isinstance(offer, dict):
                raise ValueError(f'product {index + 1} offer {offer_index + 1} must be an object')
            vendor = str(offer.get('vendor') or '').strip()[:80]
            url = offer.get('url')
            parsed_offer_url = urlparse(str(url or ''))
            if not vendor or parsed_offer_url.scheme != 'https' or not parsed_offer_url.hostname or parsed_offer_url.username or parsed_offer_url.password:
                raise ValueError(f'product {index + 1} offer {offer_index + 1} has invalid vendor or URL')
            price = offer.get('price')
            if price is not None:
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    raise ValueError(f'product {index + 1} offer {offer_index + 1} has invalid price')
                if price < 0:
                    raise ValueError(f'product {index + 1} offer {offer_index + 1} has invalid price')
            checked_at = offer.get('checked_at') or retrieved_at
            expires_at = offer.get('expires_at')
            for field_name, field_value in (('checked_at', checked_at), ('expires_at', expires_at)):
                if field_value is not None and (not isinstance(field_value, str) or len(field_value) > 80):
                    raise ValueError(f'product {index + 1} offer {offer_index + 1} has invalid {field_name}')
            offer_source_url = offer.get('source_url') or source_url
            if offer_source_url:
                parsed_offer_source = urlparse(str(offer_source_url))
                if parsed_offer_source.scheme != 'https' or not parsed_offer_source.hostname or parsed_offer_source.username or parsed_offer_source.password:
                    raise ValueError(f'product {index + 1} offer {offer_index + 1} has invalid source_url')
            affiliate_url = offer.get('affiliate_url')
            if affiliate_url:
                parsed_affiliate = urlparse(str(affiliate_url))
                if parsed_affiliate.scheme != 'https' or not parsed_affiliate.hostname or parsed_affiliate.username or parsed_affiliate.password:
                    raise ValueError(f'product {index + 1} offer {offer_index + 1} has invalid affiliate_url')
            for money_name in ('item_price', 'delivery_price', 'total_price'):
                if offer.get(money_name) is not None:
                    try:
                        if float(offer[money_name]) < 0:
                            raise ValueError
                    except (TypeError, ValueError):
                        raise ValueError(f'product {index + 1} offer {offer_index + 1} has invalid {money_name}')
            offers.append({
                'vendor': vendor, 'url': str(url), 'price': price,
                'provider': str(offer.get('provider') or source)[:80],
                'seller': str(offer.get('seller') or '')[:120] or None,
                'affiliate_url': offer.get('affiliate_url'),
                'product_identifier': str(offer.get('product_identifier') or item['identity']['gtin'] or item['identity']['mpn'] or item['identity']['model'])[:120],
                'condition': str(offer.get('condition') or 'new')[:30],
                'item_price': float(offer['item_price']) if offer.get('item_price') is not None else price,
                'delivery_price': float(offer['delivery_price']) if offer.get('delivery_price') is not None else None,
                'total_price': float(offer['total_price']) if offer.get('total_price') is not None else price,
                'stock_message': str(offer.get('stock_message') or '')[:160] or None,
                'source_license': str(offer.get('source_license') or item['source_license'] or '')[:200] or None,
                'is_affiliate': bool(offer.get('is_affiliate')),
                'is_sponsored': bool(offer.get('is_sponsored')),
                'currency': str(offer.get('currency') or 'GBP')[:3],
                'availability': str(offer.get('availability') or 'unknown')[:40],
                'checked_at': checked_at, 'expires_at': expires_at,
                'source_url': offer_source_url,
            })
        item['offers'] = offers
        for evidence in item['benchmarks']:
            if not isinstance(evidence, dict) or str(evidence.get('evidence_type') or 'unknown') not in {'measured', 'independent_published', 'vendor_claimed', 'specification_estimate', 'unknown'}:
                raise ValueError(f'product {index + 1} has invalid benchmark evidence')
            if evidence.get('source_url') and urlparse(str(evidence['source_url'])).scheme != 'https':
                raise ValueError(f'product {index + 1} has invalid benchmark source_url')
        for evidence in item['security_evidence']:
            if not isinstance(evidence, dict) or not evidence.get('provider'):
                raise ValueError(f'product {index + 1} has invalid security evidence')
            if evidence.get('source_url') and urlparse(str(evidence['source_url'])).scheme != 'https':
                raise ValueError(f'product {index + 1} has invalid security source_url')
        if (not item['name'] or not item['category'] or
                (item['price'] is not None and item['price'] < 0) or
                item['cpu_speed'] < 0 or item['ram'] < 0 or item['storage'] < 0 or item['screen_size'] < 0):
            raise ValueError(f'product {index + 1} has invalid values')
        normalised.append(item)
    return normalised, source, source_url, retrieved_at


@app.route('/admin/catalogue/import', methods=['POST'])
@admin_mutation_required
def import_catalogue_feed():
    try:
        products, source, source_url, retrieved_at = validate_catalogue_feed(request.get_json(silent=True))
        replace_catalogue(products, source, source_url, retrieved_at)
        return jsonify({'success': True, 'count': len(products), 'source': source, 'retrieved_at': retrieved_at}), 202
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'catalogue import failed'}), 500


def ensure_database_schema():
    """Create the small pilot schema when a clean deployment has no DB file."""
    database_dir = os.path.dirname(os.path.abspath(app.config['DATABASE_PATH']))
    os.makedirs(database_dir, exist_ok=True)
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS devices
        (id INTEGER PRIMARY KEY, name TEXT, category TEXT, cpu_speed REAL,
         ram INTEGER, storage INTEGER, screen_size REAL, price REAL)''')
    for table in ('PersonalUseSoftware', 'StudentUseSoftware', 'WorkUseSoftware', 'GovernmentUseSoftware'):
        cursor.execute(f'CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY, Software TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS SecurityRecommendations (id INTEGER PRIMARY KEY, Recommendation TEXT)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS device_catalogue_metadata
        (device_id INTEGER PRIMARY KEY, source TEXT NOT NULL, source_url TEXT,
         retrieved_at TEXT NOT NULL, price_checked_at TEXT, availability TEXT NOT NULL,
         expires_at TEXT, support_until TEXT, warranty TEXT, image_license TEXT,
         evidence_url TEXT, evidence_quality TEXT NOT NULL DEFAULT 'unknown',
         FOREIGN KEY(device_id) REFERENCES devices(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS device_offers
        (id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, vendor TEXT NOT NULL,
         url TEXT NOT NULL, price REAL, currency TEXT NOT NULL DEFAULT 'GBP',
         availability TEXT NOT NULL DEFAULT 'unknown', checked_at TEXT NOT NULL,
         expires_at TEXT, source_url TEXT,
         FOREIGN KEY(device_id) REFERENCES devices(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS benchmark_results
        (id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, suite TEXT NOT NULL,
         version TEXT, workload TEXT, score REAL, evidence_type TEXT NOT NULL,
         source_url TEXT, licence TEXT, tested_at TEXT NOT NULL,
         confidence TEXT NOT NULL DEFAULT 'unknown', notes TEXT,
         FOREIGN KEY(device_id) REFERENCES devices(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS security_evidence
        (id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, provider TEXT NOT NULL,
         cve_id TEXT, cpe TEXT, kev_status TEXT, affected_version TEXT,
         fixed_version TEXT, source_url TEXT, checked_at TEXT NOT NULL,
         evidence_type TEXT NOT NULL, confidence TEXT NOT NULL DEFAULT 'unknown',
         summary TEXT, FOREIGN KEY(device_id) REFERENCES devices(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS support_lifecycle
        (id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, operating_system TEXT,
         support_until TEXT, patch_cadence TEXT, source_url TEXT,
         checked_at TEXT NOT NULL, confidence TEXT NOT NULL DEFAULT 'unknown',
         FOREIGN KEY(device_id) REFERENCES devices(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS provider_runs
        (id INTEGER PRIMARY KEY, provider TEXT NOT NULL, status TEXT NOT NULL,
         started_at TEXT NOT NULL, completed_at TEXT, item_count INTEGER NOT NULL DEFAULT 0,
         error_summary TEXT, source_url TEXT)''')
    existing_columns = {row[1] for row in cursor.execute('PRAGMA table_info(devices)').fetchall()}
    for column, definition in (
        ('brand', 'TEXT'), ('model', 'TEXT'), ('variant', 'TEXT'), ('mpn', 'TEXT'),
        ('gtin', 'TEXT'), ('sku', 'TEXT'), ('region', "TEXT DEFAULT 'GB'"),
        ('release_date', 'TEXT'), ('operating_system', 'TEXT'), ('source_state', "TEXT DEFAULT 'sample'"),
        ('image_url', 'TEXT'),
    ):
        if column not in existing_columns:
            cursor.execute(f'ALTER TABLE devices ADD COLUMN {column} {definition}')
    existing_columns = {row[1] for row in cursor.execute('PRAGMA table_info(device_catalogue_metadata)').fetchall()}
    for column, definition in (
        ('expires_at', 'TEXT'), ('support_until', 'TEXT'), ('warranty', 'TEXT'),
        ('image_license', 'TEXT'), ('evidence_url', 'TEXT'),
        ('evidence_quality', "TEXT NOT NULL DEFAULT 'unknown'"),
        ('source_state', "TEXT NOT NULL DEFAULT 'sample'"), ('source_license', 'TEXT'),
        ('confidence', "TEXT NOT NULL DEFAULT 'unknown'"), ('freshness_hours', 'INTEGER'),
    ):
        if column not in existing_columns:
            cursor.execute(f'ALTER TABLE device_catalogue_metadata ADD COLUMN {column} {definition}')
    existing_columns = {row[1] for row in cursor.execute('PRAGMA table_info(device_offers)').fetchall()}
    for column, definition in (
        ('provider', "TEXT NOT NULL DEFAULT 'operator_feed'"), ('seller', 'TEXT'),
        ('affiliate_url', 'TEXT'), ('product_identifier', 'TEXT'), ('condition', "TEXT DEFAULT 'new'"),
        ('item_price', 'REAL'), ('delivery_price', 'REAL'), ('total_price', 'REAL'),
        ('stock_message', 'TEXT'), ('source_license', 'TEXT'),
        ('is_affiliate', 'INTEGER NOT NULL DEFAULT 0'), ('is_sponsored', 'INTEGER NOT NULL DEFAULT 0'),
    ):
        if column not in existing_columns:
            cursor.execute(f'ALTER TABLE device_offers ADD COLUMN {column} {definition}')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_device_offers_device_total_price ON device_offers(device_id, total_price)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_identity ON devices(brand, model, region)')
    if not cursor.execute('SELECT 1 FROM PersonalUseSoftware LIMIT 1').fetchone():
        cursor.executemany('INSERT INTO PersonalUseSoftware (Software) VALUES (?)',
                           [(name,) for name in ('Norton 360', 'Bitdefender Total Security', 'Avast Free')])
    if not cursor.execute('SELECT 1 FROM StudentUseSoftware LIMIT 1').fetchone():
        cursor.executemany('INSERT INTO StudentUseSoftware (Software) VALUES (?)',
                           [(name,) for name in ('Bitdefender Total Security', 'Avast Premium Security')])
    if not cursor.execute('SELECT 1 FROM WorkUseSoftware LIMIT 1').fetchone():
        cursor.executemany('INSERT INTO WorkUseSoftware (Software) VALUES (?)',
                           [(name,) for name in ('Bitdefender GravityZone', 'Sophos Intercept X')])
    if not cursor.execute('SELECT 1 FROM GovernmentUseSoftware LIMIT 1').fetchone():
        cursor.executemany('INSERT INTO GovernmentUseSoftware (Software) VALUES (?)',
                           [(name,) for name in ('Bitdefender GravityZone', 'Credential Guard')])
    if not cursor.execute('SELECT 1 FROM SecurityRecommendations LIMIT 1').fetchone():
        cursor.executemany('INSERT INTO SecurityRecommendations (Recommendation) VALUES (?)',
                           [(name,) for name in ('Secure Boot', 'Regular Patching', 'Multi-Factor Authentication (MFA)')])
    conn.commit()
    has_devices = cursor.execute('SELECT 1 FROM devices LIMIT 1').fetchone()
    if has_devices:
        cursor.execute('''INSERT OR IGNORE INTO device_catalogue_metadata
            (device_id, source, source_url, retrieved_at, price_checked_at, availability, source_state)
            SELECT id, 'Local legacy catalogue', NULL, ?, NULL, 'unknown', 'sample' FROM devices''', (_utc_now(),))
        cursor.execute("UPDATE device_catalogue_metadata SET source_state = 'sample' WHERE source IN ('Curated local catalogue', 'Local legacy catalogue') AND source_state IS NULL")
        conn.commit()
    conn.close()
    if not has_devices:
        populate_database_with_real_data()

def get_device_image_url(device_name, scraped_url=None):
    """Return a licensed HTTPS image URL, or no image when evidence is absent."""
    if scraped_url and urlparse(str(scraped_url)).scheme == 'https' and urlparse(str(scraped_url)).hostname:
        return scraped_url
    # Fixture imagery is intentionally opt-in and is never emitted by the
    # default production configuration.
    return '/static/images/1.jpg' if app.config.get('ALLOW_SAMPLE_DATA') else None

# Initialize the pilot schema without requiring an untracked local database.
print("Initializing database with device data...")
ensure_database_schema()
start_retailer_refresh_worker()
ensure_db_indexes()

@app.route("/api/image-proxy", methods=["GET"])
@public_rate_limited
def image_proxy():
    """
    Proxy for external device images to handle CORS and caching.
    Prevents broken image links and improves load reliability.
    """
    try:
        image_url = request.args.get('url', '')
        parsed = _allowed_outbound_url(
            image_url,
            'IMAGE_PROXY_ALLOWED_HOSTS',
            'm.media-amazon.com,images-na.ssl-images-amazon.com,images.unsplash.com'
        )
        # Only public HTTPS hosts explicitly allowlisted by the operator are fetched.
        if not parsed:
            return "Invalid image URL", 400
        
        response = requests.get(image_url, timeout=(3, 5), allow_redirects=False, stream=True)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').split(';', 1)[0].lower()
        if content_type not in {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}:
            return "Unsupported image type", 415
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > app.config['IMAGE_PROXY_MAX_BYTES']:
            return "Image too large", 413
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > app.config['IMAGE_PROXY_MAX_BYTES']:
                return "Image too large", 413
        response.close()
        
        # Return image with caching headers
        return bytes(body), 200, {
            'Content-Type': content_type,
            'Cache-Control': 'public, max-age=86400'  # Cache for 24 hours
        }
    except Exception as e:
        print(f"Image proxy error: {e}")
        # Return placeholder or 1x1 transparent GIF
        return b'', 404

@app.route("/search-live", methods=["POST"])
@public_rate_limited
def search_live():
    """Search the latest cached catalogue without triggering outbound requests."""
    try:
        data = request.get_json(silent=True) or {}
        search_term = data.get('query', '').strip()
        max_results = max(1, min(int(data.get('max_results', 20)), 50))
        
        if not search_term or len(search_term) < 2:
            return jsonify({'error': 'Search term too short'}), 400
        
        filters = _api_filters({'query': search_term, 'page_size': max_results})
        results, total = _api_catalogue(filters)
        return jsonify({
            'query': search_term, 'results': results, 'total_found': total,
            'source': 'cached_catalogue', 'catalogue_state': _catalogue_state(),
            'message': 'Results use the latest cached feed; retailer observations must be verified on the retailer site.'
        }), 200
        
    except Exception as e:
        print(f"Live search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/get-current-price", methods=["POST"])
@public_rate_limited
def get_current_price():
    """
    Get current pricing from specific retailer.
    Real-time price comparison across retailers.
    """
    try:
        data = request.get_json(silent=True) or {}
        device_name = data.get('device_name', '')
        retailer = str(data.get('retailer', '') or '').strip()[:80]
        
        if not device_name:
            return jsonify({'error': 'Device name required'}), 400
        
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        query = '''SELECT o.vendor, o.price, o.total_price, o.currency, o.availability,
                          o.checked_at, o.expires_at, o.url, d.name, m.source_state
                   FROM device_offers o JOIN devices d ON d.id = o.device_id
                   LEFT JOIN device_catalogue_metadata m ON m.device_id = d.id
                   WHERE LOWER(d.name) LIKE ?
                     AND (o.expires_at IS NULL OR o.expires_at > ?)'''
        params = [f'%{device_name.lower()[:100]}%', _utc_now()]
        if retailer:
            query += ' AND LOWER(o.vendor) LIKE ?'
            params.append(f'%{retailer.lower()}%')
        query += ' ORDER BY COALESCE(o.total_price, o.price) ASC LIMIT 1'
        row = conn.execute(query, params).fetchone()
        conn.close()
        if not row:
            return jsonify({'error': 'no current cached offer found'}), 404
        return jsonify({
            'device_name': row[8], 'retailer': row[0], 'price': row[1],
            'total_price': row[2] if row[2] is not None else row[1],
            'currency': row[3], 'availability': row[4], 'checked_at': row[5],
            'expires_at': row[6], 'link': row[7], 'source_state': row[9] or 'unknown',
            'message': 'Observed price; verify the final price and stock on the retailer site.'
        }), 200
        
    except Exception as e:
        print(f"Price fetch error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/refresh-devices", methods=["POST"])
@admin_mutation_required
def refresh_devices():
    """Operator-only refresh boundary for configured providers or observations."""
    provider = str((request.get_json(silent=True) or {}).get('provider') or '').strip()
    if provider in {'retailer_observation', 'retailer_page_observation'}:
        if not app.config['ENABLE_LIVE_SCRAPING']:
            return jsonify({'success': False, 'status': 'retailer_observation_disabled'}), 503
        result = refresh_retailer_observation_catalogue()
        return jsonify(result), 202 if result['status'] == 'completed' else 503
    if not app.config['PROVIDER_SYNC_ENABLED']:
        return jsonify({'success': False, 'status': 'provider_sync_disabled',
                        'message': 'Provider sync is disabled until approved adapters and credentials are configured.'}), 503
    result = run_provider(str(provider), enabled=app.config['PROVIDER_SYNC_ENABLED'])
    _record_provider_run(result)
    return jsonify(result), 503 if result['status'] != 'completed' else 202

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
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
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
@public_rate_limited
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
    """Compatibility worker; approved provider jobs replace this boundary."""
    global SCRAPE_THREAD
    print('[AsyncProvider] Background provider sync is not configured')
    with SCRAPE_LOCK:
        SCRAPE_THREAD = None

@app.route('/async-refresh', methods=['POST'])
@admin_mutation_required
def async_refresh():
    global SCRAPE_THREAD
    if not app.config['PROVIDER_SYNC_ENABLED']:
        return jsonify({'status': 'provider_sync_disabled',
                        'message': 'Provider sync is disabled until approved adapters are configured.'}), 503
    with SCRAPE_LOCK:
        if SCRAPE_THREAD and SCRAPE_THREAD.is_alive():
            return jsonify({'status': 'in_progress'}), 202
        SCRAPE_THREAD = threading.Thread(target=background_scrape, daemon=True)
        SCRAPE_THREAD.start()
    return jsonify({'status': 'started'}), 202


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8002))
    host = os.environ.get('HOST', '127.0.0.1')
    debug_mode = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    app.run(host=host, debug=debug_mode, port=port)
