# Testing the New Live Search APIs

This guide shows you how to test the new dynamic search and real-time pricing features.

## Prerequisites

1. Flask app running on `http://127.0.0.1:8002`
   ```bash
   cd /path/to/Dynamic-Flowchart-For-Device-Provisioning-
   python3 app.py
   ```

2. `curl` command available (built-in on macOS/Linux)

## API Endpoints

### 1. Live Search API

**Endpoint:** `POST /search-live`

**Purpose:** Search for devices across retailers and get fresh market results

**Example 1: Search for MacBook**
```bash
curl -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MacBook Pro",
    "max_results": 5
  }'
```

**Example 2: Search for Dell Laptops**
```bash
curl -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Dell XPS",
    "max_results": 10
  }'
```

**Example 3: Search for Budget Gaming Laptop**
```bash
curl -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{
    "query": "ASUS TUF Gaming Laptop",
    "max_results": 5
  }'
```

**Response Format:**
```json
{
  "query": "MacBook Pro",
  "results": [
    {
      "id": null,
      "name": "Apple MacBook Pro 14\" M3",
      "category": "Laptops",
      "cpu_speed": 3.5,
      "ram": 16,
      "storage": 512,
      "screen_size": 14.0,
      "price": 1899,
      "image": "https://example.com/image.jpg",
      "source": "Amazon UK",
      "os": "macOS",
      "cpu_vendor": "Apple Silicon",
      "security": {
        "score": 78,
        "level": "Good",
        "findings": ["Speculative execution side-channels (Spectre/Meltdown class)"],
        "mitigations": ["Ensure firmware (microcode) and OS patches are up to date"],
        "recommendations": {
          "software": ["Jamf Pro (MDM)", "FileVault", "Little Snitch"],
          "settings": ["Enable Gatekeeper and System Integrity Protection"],
          "hardware": ["FIDO2 security keys", "Privacy screen"]
        }
      },
      "benchmark": {
        "cpu_index": 70,
        "memory_index": 25,
        "storage_index": 26,
        "overall_index": 46
      },
      "debloat_tools": [
        {
          "name": "AppCleaner",
          "url": "https://freemacsoft.net/appcleaner/",
          "description": "Thoroughly removes apps and residual files."
        }
      ],
      "retailer_links": {
        "amazon": "https://www.amazon.co.uk/s?k=MacBook+Pro",
        "apple": "https://www.apple.com/uk/shop"
      },
      "allowed": true
    }
  ],
  "total_found": 5,
  "source": "live_web_search"
}
```

### 2. Get Current Price API

**Endpoint:** `POST /get-current-price`

**Purpose:** Get real-time pricing from a specific retailer

**Example 1: Amazon Price**
```bash
curl -X POST http://127.0.0.1:8002/get-current-price \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "MacBook Pro 14",
    "retailer": "amazon"
  }'
```

**Example 2: Currys Price**
```bash
curl -X POST http://127.0.0.1:8002/get-current-price \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "Dell XPS 13",
    "retailer": "currys"
  }'
```

**Response Format:**
```json
{
  "device": "MacBook Pro 14",
  "retailer": "amazon",
  "price": 1899,
  "link": "https://www.amazon.co.uk/s?k=MacBook+Pro",
  "available": true,
  "timestamp": 1712762400
}
```

### 3. Form-Based Search (Web UI)

**Endpoint:** `POST /`

**Purpose:** Traditional form submission with live scraping enabled

**Example: Search via HTML Form**
```bash
curl -X POST http://127.0.0.1:8002/ \
  -d "searchBar=MacBook&price_range_min=800&price_range_max=2000&cpu_speed=3.0&ram=8&storage=256&screen_size=13&use=Work"
```

**What happens:**
1. Checks if "MacBook" is in search cache (valid for 5 minutes)
2. If not cached, scrapes Amazon/Currys for fresh results
3. Filters by specified criteria (price, specs)
4. Applies security scoring based on use case (Work)
5. Falls back to database if scraping fails
6. Returns enriched results with security recommendations

## Testing Workflow

### Test 1: Cache Performance
```bash
# First search (cache miss - will scrape web)
time curl -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{"query":"MacBook", "max_results":5}' > /tmp/result1.json

# Expected: ~5-15 seconds (web scraping)
# Check /tmp/result1.json for results

# Second search immediately after (cache hit)
time curl -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{"query":"MacBook", "max_results":5}' > /tmp/result2.json

# Expected: ~50ms (dict lookup)
# Results should match result1.json
```

### Test 2: Fallback Behavior
```bash
# Search for generic/non-existent product (likely no web results)
curl -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{"query":"xyzunknowndevice2024", "max_results":5}'

# Expected Response:
# {
#   "query": "xyzunknowndevice2024",
#   "results": [],
#   "message": "No devices found for this search term",
#   "source": "live_web_search"
# }
```

### Test 3: Multi-Retailer Pricing
```bash
# Get same device from different retailers
for retailer in amazon currys; do
  echo "=== $retailer ==="
  curl -s -X POST http://127.0.0.1:8002/get-current-price \
    -H "Content-Type: application/json" \
    -d "{\"device_name\":\"MacBook Pro\", \"retailer\":\"$retailer\"}" | jq '.price'
done

# Expected: Different prices from each retailer
# Can be used for price comparison
```

### Test 4: Security Scoring with Use Cases
```bash
# Search results filtered by use case

# Personal use (least strict)
curl -s -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{"query":"budget laptop", "max_results":3}' | jq '.results[0].security.score'

# Work use (moderate requirements)  
curl -s -X POST http://127.0.0.1:8002/ \
  -d "searchBar=laptop&use=Work" | grep -o '"score":[0-9]*' | head -1

# Government use (strict requirements)
curl -s -X POST http://127.0.0.1:8002/ \
  -d "searchBar=laptop&ram=16&cpu_speed=3.5&use=Government" | grep allowed
```

## Monitoring & Debugging

### Check Cache Status
```bash
# View Flask logs while testing
tail -f /tmp/flask.log

# Look for:
# [CACHE] Using cached search results for: MacBook
# [LIVE SEARCH] Searching for: MacBook
# [LIVE SEARCH] Found X results for 'MacBook'
```

### Parse JSON Results
```bash
# Pretty print results
curl -s -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{"query":"MacBook", "max_results":1}' | jq '.'

# Get just the device names
curl -s -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{"query":"MacBook", "max_results":5}' | jq '.results[].name'

# Get security scores
curl -s -X POST http://127.0.0.1:8002/search-live \
  -H "Content-Type: application/json" \
  -d '{"query":"MacBook", "max_results":5}' | jq '.results[] | {name: .name, security_score: .security.score}'
```

## Known Limitations

### Web Scraping
- **Amazon/Currys blocks requests** after multiple rapid tests
  - **Workaround**: Wait 30 seconds between tests or use different devices

- **HTML structure changes** break selectors
  - **Expected behavior**: No results returned, falls back to database

- **JavaScript-rendered content** not captured by BeautifulSoup
  - **Workaround**: Run from browser (works), or use Selenium (slower)

### Retailers Not Scraped
These retailers need API integration:
- John Lewis (requires authentication)
- Brand direct stores (Apple, Microsoft, Dell, etc.)
- Scan, Newegg, eBay (different HTML structures)

## Recommended Testing Sequence

1. **Option 1: Quick Test (2 minutes)**
   ```bash
   # Test 1: API endpoint
   curl -X POST http://127.0.0.1:8002/search-live \
     -H "Content-Type: application/json" \
     -d '{"query":"Dell", "max_results":3}'
   
   # Test 2: Form search
   curl -X POST http://127.0.0.1:8002/ \
     -d "searchBar=HP&use=Personal"
   ```

2. **Option 2: Full Test (10 minutes)**
   - Run cache performance test (3 min)
   - Test fallback behavior (2 min)
   - Test security scoring (3 min)
   - Test pricing APIs (2 min)

3. **Option 3: Load Test (30 minutes)**
   - Stress test cache with concurrent requests
   - Test scraper rate limiting
   - Monitor memory/CPU usage
   - Verify graceful degradation

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `"No devices found"` | Normal if Amazon blocks request. Wait 30s and retry. |
| `timeout` | Scraper took >30s. Web might be slow. Check internet connection. |
| `empty results array` | Search term too obscure. Try common device names (MacBook, Dell, HP). |
| `"allowed": false` | Device doesn't meet use-case requirements (e.g., low RAM for Government). |
| Price is `0` | Retailer link validation failed. Try different retailer. |

## Performance Benchmarks

### Typical Response Times

```
Scenario                        Time        Cost
─────────────────────────────────────────────────
Cache hit (same search)         50ms        Database lookup
Web scrape (first search)       5-15s       Network + parsing
Fallback (if scrape fails)      200ms       Database query
Security scoring (per device)   10ms        CPU bound
Result caching                  1ms         Memory write
─────────────────────────────────────────────────
Total first search              5-15s       (one-time per device)
Total cached search             50ms        (2-3x faster)
```

## Next Steps

- Implement Selenium for JavaScript-heavy sites
- Add more retailers (John Lewis, eBay, Scan)
- Set up rotating proxies to avoid blocking
- Implement CAPTCHA solving (automated or manual)
- Add price history tracking
- Create price change alerts for users
