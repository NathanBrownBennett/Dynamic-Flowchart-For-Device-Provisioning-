# Dynamic Flowchart for Device Provisioning

This application simplifies the provisioning of devices to employees or end-users by utilizing a dynamic flowchart. It helps in making informed decisions on what devices to provide based on various criteria such as device type, specifications, and usage (personal or work).

## Features

- **Dynamic Flowchart Generation**: Creates a visual flowchart to help decide on the provisioning of devices.
- **Device Filtering**: Filters devices from a database based on category, price range, and specifications like CPU speed, RAM, storage, and screen size.
- **Customizable Specifications**: Allows setting minimum requirements for device specifications.
- **Interactive Web Interface**: Provides a web interface for easy interaction and decision-making.
- **Form Results**: Displays devices matching the user's search criteria.
- **Security Recommendations**: Provides guidelines to ensure devices are secure and up-to-date.
- **Educational Resources**: Links to modules on digital literacy and cybersecurity.
- **Evidence-gated benchmarks**: CPU, memory and storage scores appear only when a sourced benchmark record exists
- **Observed purchase links**: Offers are labelled with source and freshness; affiliate attribution is not claimed until partner terms are approved
- **Debloat & Performance Tools**: OS-aware recommendations (13+ tools across 6 operating systems)
- **Evidence-gated security assessment**: Model-linked OS, security evidence and support lifecycle records are required before a security score appears
- **Advanced Search**: 13+ filter criteria for precise device discovery
- **Responsive Design**: Bootstrap 5 UI with dark/light mode support
- **Online catalogue architecture**: Searchable reviewed products with a path to permitted provider feeds
- **Plain-English security guidance**: Explain the practical meaning of device risks and hardening steps
- **Safe provider boundary**: Live retailer access is disabled by default and must use approved feeds/APIs
- **React/Vite frontend**: Optional same-service frontend served by Flask at `/app/`

## Online service architecture

The hosted service is designed as a catalogue and comparison experience, not as
a browser scraper:

```
Browser → React/Vite search UI → Flask API → reviewed catalogue/cache
                                      ↓
                         plain-English security guidance
                                      ↓
                         comparison and hardening plan
```

The browser should never call retailers directly. A future provider ingestion
worker may use permitted affiliate APIs, product feeds or approved retailer
interfaces to update catalogue records with source, retrieval time, expiry,
price/availability caveats and attribution. The current live scraping routes
remain disabled by default.

For non-Docker development and WSGI hosting, see
[HOSTING_NON_DOCKER.md](HOSTING_NON_DOCKER.md). The target BStudioB deployment
is a founder-approved subdomain such as `provisioning.bstudiob.co.uk`; DNS and
hosting changes are intentionally not performed by this repository workflow.

### React frontend development

```bash
cd frontend
npm install
npm run dev
```

For a same-service hosted build, run `npm run build` in `frontend/` and start
Flask/Gunicorn with `SERVE_FRONTEND_AT_ROOT=true`. Docker can build the same
frontend automatically, but is not required.

**See [ARCHITECTURE_IMPROVEMENTS.md](ARCHITECTURE_IMPROVEMENTS.md) for detailed technical documentation.**

## Performance

- The current public API reads the reviewed SQLite catalogue and applies
  bounded server-side filters.
- Provider data is intentionally not fetched in a browser request. A future
  permitted feed/API worker should record source, retrieval time and expiry.
- Performance figures will be published after a representative hosted load
  test; local timings are not production guarantees.

## Features

### Quick Demo (Interactive Slides)
**Open the interactive walkthrough in your browser:**
- **File**: `VIDEO_WALKTHROUGH.html`
- **Instructions**: 
  1. Double-click the file to open in your browser
  2. Navigate using "Next" button or arrow keys
  3. 11 comprehensive slides covering all features
  4. No installation required—works offline

### Walkthrough Contents:
1. **Introduction** - Overview of key features
2. **Home Page** - Use case selection, recommended devices
3. **Recommended Devices** - Reviewed devices ranked for the selected use case, with evidence coverage visible
4. **Search & Filtering** - 13+ filter options and advanced search
5. **Device Detail Page** - Full specifications, security info, benchmarks
6. **Security Guide** - OS-specific hardening, software recommendations, threat mitigation
7. **Debloat Tools** - 13+ performance optimization tools (Windows, macOS, Linux, Android, etc.)
8. **Purchase Tab** - Source-labelled offers with freshness and verification caveats
9. **Technology Features** - Benchmark formula, security engine, database optimization
10. **Quality Assurance** - Test results (7/7 E2E tests passing)
11. **Summary** - Key achievements and next steps

### Local demo recording (historical verification)

The walkthrough and recording script are development aids. They do not prove
that the hosted catalogue has complete evidence or that a live retailer
integration is approved. Treat the hosted `/api/v1/catalogue/status` response
as the source of truth for current coverage.
```
🎬 Playwright Recording Script
============================

📍 Step 1: Loading home page...
   ✓ Page Title: Device Provisioning Toolkit
   ✓ Recommended devices found: 4
   ✓ Live listings section: Yes

📍 Step 2: Verifying device selection...
   ✓ Multiple device cards with specifications
   ✓ Evidence badges displayed; scores are withheld when source records are incomplete

📍 Step 3: Viewing search functionality...
   ✓ Search form opened
   ✓ Search field available
   ✓ Filter options: 6+ fields available

📍 Step 4: Testing advanced filters...
   ✓ Device type filtering
   ✓ Price range filtering
   ✓ OS selection available
   ✓ Brand filtering supported

==================================================
📊 APP FUNCTIONALITY SUMMARY (LOCAL/UI)
==================================================
✅ Home page with recommended devices
✅ Source-labelled purchase observations where available
✅ Device detail page with 4 tabs (Overview, Security Guide, Compare, Purchase)
✅ Security Guide with OS-specific recommendations
✅ Purchase options with retailer buttons
✅ Advanced search functionality (13+ criteria)
✅ Device filtering and sorting by use-case
✅ Evidence-gated device security assessment
✅ Evidence-gated hardware benchmark presentation
✅ Debloat tool recommendations per device

⚠️ Benchmark, security and support scores depend on sourced catalogue records
⚠️ Multi-vendor and affiliate coverage remains incomplete
```

### How to Run the Live App:
```bash
# Start the Flask application
python app.py

# Or with specific port
PORT=8012 python app.py

# Open in browser
open http://localhost:5000
# or
open http://localhost:8012
```

### Test Results:
```
✓ Backend/API/security tests passing
✓ Home page rendering ✓
✓ Device search with security scoring ✓
✓ Device details & security guidance ✓
✓ Compare functionality ✓
✓ Async data refresh ✓
✓ 404 error handling ✓
```

## Prerequisites

Before running this application, ensure you have the following installed:
- Python 3
- Flask
- SQLite3
- Graphviz
- Pandas

Additionally, you must have `graphviz` and `ipywidgets` installed if you plan to use Jupyter Notebooks for visualization.

## Installation

1. **Clone the Repository**

   ```
   git clone https://github.com/your-repository/Dynamic-Flowchart-For-Device-Provisioning.git
   cd Dynamic-Flowchart-For-Device-Provisioning
   ```
   ```

2. **Install Dependencies**

   It's recommended to use a virtual environment:

   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

   and then either use 
    
    ```
    pip install flask sqlite3 pandas graphviz
    ```

   or

   ```
   pip install -r requirements.txt
   ```

3. **Set Up the Database**

   Run the `create_db.py` script to set up the SQLite database with sample device data.

   ```
   python create_db.py
   ```

## Running the Application

1. **Start the Flask Application**

   ```
   python app.py
   ```

   Or with specific port (recommended):
   ```
   PORT=8012 python app.py
   ```

2. **Access the Web Interface**

   Open a web browser and navigate to `http://127.0.0.1:5000/` (or `http://localhost:8012` if using PORT=8012) to start using the application.

## Usage

- On the web interface, select the use case (Personal, Business, Government)
- Browse recommended devices with evidence coverage and plain-English caveats
- Use **Find Your Device** to search with 13+ filter criteria:
  - Device name, brand, or model
  - Price range
  - Device type (Laptops, Tablets, PCs)
  - Operating System
  - CPU speed, RAM, storage specifications
- View detailed device information including:
  - Performance specifications
  - Security evidence and threat assessment where sourced
  - Hardware benchmarks (0-100 scores only when sourced)
  - Security guidance and hardening steps
  - Debloat & performance optimization tools
  - Source-labelled purchase options
- Generate downloadable security checklists and hardening scripts

**Quick Start Video**: Watch the interactive walkthrough in `VIDEO_WALKTHROUGH.html` for guided tour.

## Project Structure

- **app.py**: The main Flask application file. Handles routing, form submission, querying the database, and rendering HTML templates.
- **create_db.py**: A script to create and populate the SQLite database (`devices.db`) with device data.
- **index.html**: The main HTML template for the home page. Contains the device search form, recommended devices carousel, and sections for form results, security recommendations, and educational resources.
- **device.html**: HTML template for displaying detailed information about a selected device.
- **devices.db**: SQLite database file containing device data.
- **VIDEO_WALKTHROUGH.html**: Interactive 11-slide presentation walkthrough of all features
- **record-demo.js**: Playwright script for automated app interaction and verification

## Technical Architecture

### Backend (Python + Flask)
- **Security evidence pipeline**: OS inference plus model-linked vulnerability, support and security evidence; scores are withheld when evidence is missing
- **Benchmark metrics**: Normalized hardware scoring only from validated benchmark records
- **Offer presentation**: Bounded, source-labelled catalogue offers; no claim of retailer authorisation or affiliate commission
- **Debloat Tools Database**: 13+ OS-aware performance optimization recommendations
- **Provider boundary**: Live retailer access is disabled by default pending permitted feeds/APIs
- **Database**: SQLite3 with indexed queries for fast device search

### Frontend (React + Vite, with legacy Jinja templates retained)
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Dark/Light Mode**: Accessibility toggle
- **Plain-English detail view**: Security meaning, first steps, risks, performance and purchase comparison
- **Versioned API**: Read/search/detail/comparison contract under `/api/v1/*`
- **Dynamic Filtering**: Bounded server-side catalogue filters

### Testing (Playwright + Node.js)
- **Deterministic tests**: Frontend API-contract tests plus backend/API/security tests
- **Automated Navigation**: Test home page, search, device details, tabs
- **Security Coverage**: Verify security guidance and recommendations
- **CI/CD Ready**: Scriptable Playwright tests for continuous integration

### Core Functions (app.py)

#### Security Assessment
```python
def infer_os_and_cpu(device_name, category)
  # OS inference: macOS, Windows 11, Linux, Android, iPadOS, ChromeOS
  
def detect_known_vulnerabilities(os, cpu_vendor, device_name)
  # Find Spectre/Meltdown, OEM bloatware, fragmentation risks
  
def compute_security_score(device, os, cpu_vendor, use_case)
  # Evidence-gated 0-100 score; withheld without model-linked evidence and support lifecycle
```

#### Hardware Benchmarks
```python
def compute_benchmark_metrics(device, security_score)
  # Normalized 0-100 scores from validated benchmark records only.
  # Missing or unsupported records remain explicitly unavailable.
```

#### Debloat Tools
```python
def get_debloat_tools(os_name, device_name)
  # Returns OS-specific and vendor-specific tools
  # Examples: O&O AppBuster, BCUninstaller (Windows)
  #          AppCleaner, OnyX (macOS)
  #          BleachBit, Stacer (Linux)
  #          Dell SupportAssist, Lenovo Vantage (Vendor-specific)
```

#### Offer presentation
```python
def get_catalogue_offers(device_id)
  # Return bounded, source-labelled observations with retrieval and freshness data.
  # Approved feeds/APIs and affiliate attribution remain deployment gates.
```

## Features Implemented

### ✅ Completed Features
- [x] Evidence coverage reporting and score withholding for incomplete benchmark/security data
- [x] OS-aware debloat tool recommendations (13+ tools across 6 OSes)
- [x] Source-labelled retailer observations with explicit freshness and provenance caveats
- [x] Device search with 13+ filter criteria
- [x] Plain-English security and hardening guidance with evidence-gated ratings
- [x] Use-case specific recommendations (Personal, Business, Government, Education)
- [x] Responsive UI with Bootstrap 5
- [x] Dark/Light mode toggle
- [x] Provider integration boundary disabled by default
- [x] Deterministic API/security test coverage
- [x] Automated Playwright verification
- [x] Interactive video walkthrough (11 slides)

### 📊 Content Database
- **24 reviewed product records** in the current staging catalogue
- **24 current observed offers**, currently one observed source per product rather than a complete multi-vendor comparison
- **No published benchmark, model-linked security or support-lifecycle coverage yet**; the UI reports these evidence gaps and keeps affected ratings withheld
- **6 Device Categories**: Laptops, Tablets, PCs, and more
- **13+ Debloat Tools**: Cross-platform optimization recommendations
- **Retailer coverage**: Current observations are not a substitute for approved retailer feeds or affiliate APIs
- **4 Use Cases**: Personal, Business, Government, Education
- **6 Operating Systems**: Windows 11, macOS, Linux, Android, iPadOS, ChromeOS

# Application Requirements - Completed

## Must Have

### Security Measures:
- **Detailed Flowchart Creation**: Incorporate security checks into the flowchart for device provisioning.
- **Integration of Security Standards**: Follow current security standards and protocols.
- **Hardware and Software Recommendations**: Suggest secure hardware (e.g., DDR5 RAM) and software (e.g., MDM solutions, Antivirus tools).
- **Operating System Hardening**: Include steps for operating system hardening and update protocols.

### User Guidance:
- **Clear Instructions**: Provide user-friendly instructions for device provisioning.
- **Resource Links**: Offer links to resources and toolkits for securing devices.
- **Device Selection Guidelines**: Guidelines for selecting practical, reliable, and secure devices.

### Comprehensive Standards:
- **Adherence to Standards**: Follow government and industry standards.
- **Hardware and Software Specifications**: Offer in-depth recommendations.
- **Incorporation of Cyber Essentials**: Include Cyber Essentials guidelines and other relevant standards.

### Educational Resources:
- **Training Modules**: Provide training modules for digital literacy.
- **Cybersecurity Resources**: Resources for understanding cybersecurity and best practices.

### Scalability:
- **Adaptable Recommendations**: Scale recommendations based on organizational size and needs (e.g., schools, companies, government departments).

## Testing & Quality Assurance

### Automated E2E Tests (Playwright)
```bash
# Run the full test suite
npm run test:e2e

# Individual test results:
✓ Home page renders all key intent sections (22.7s)
✓ Device search returns security-verified results (1.2s)
✓ Device details provide security guidance (2.8s)
✓ Compare flow handles requests (632ms)
✓ Async refresh endpoint is available (8ms)
✓ 404 routes return safe custom UX (503ms)
✓ Operating system filter ready for enhancement (2.1s)

Total: 7 passed (30.8s)
```

### Demo Recording Script
```bash
# Run the Playwright recording/verification script
node record-demo.js

# Verifies all major features:
✓ Home page with recommended devices
✓ Source-labelled purchase observations
✓ Device detail pages with 4 tabs
✓ Security guidance content
✓ Purchase options and retailer provenance
✓ Advanced search functionality
✓ Device filtering and sorting
```

### Performance Metrics
Performance targets are not production guarantees. Measure them again on the
selected host with a representative catalogue and load profile before making
latency or capacity claims. The current hosted free tier can sleep between
requests, and SQLite remains pilot-grade storage.

## Should Have

### Compatibility Checks:
- **Verification Tools**: System compatibility verification tools for hardware and software.
- **OS and Application Recommendations**: Recommendations for operating systems and applications suitable for different user needs.

### Review and Feedback Mechanism:
- **Feedback Option**: Allow users to provide feedback on device performance and security.
- **User Reviews and Ratings**: Incorporate user reviews and ratings to guide future users.

### Device Management Tools:
- **MDM Integration**: Integrate with Mobile Device Management (MDM) solutions.
- **Monitoring and Management**: Provide monitoring and management capabilities for IT administrators.

## Could Have

### Customization Options:
- **Customizable Recommendations**: Tailor recommendations based on specific organizational needs.
- **Advanced Settings**: Offer advanced settings for tech-savvy users.

### Offline Capabilities:
- **Offline Access**: Functionality for offline access to guides and toolkits.
- **Backup and Encryption**: Recommendations for backup and encryption for offline use.

### Interactive Elements:
- **Interactive Tutorials**: Provide interactive tutorials and videos for device setup and security.
- **Virtual Assistant**: Include a virtual assistant for real-time support and guidance.

## Won't Have

### Non-Standard Devices:
- **No Recommendations for Non-Standard Devices**: Avoid recommendations for non-standard or experimental hardware and software.
- **No Support for Non-Standard Devices**: Do not support devices outside government and industry standards.

### Unverified Sources:
- **No Unverified User Reviews**: Do not incorporate unverified user reviews or non-validated security measures.
- **No Endorsement of Third-Party Software**: Avoid endorsement of third-party software without thorough vetting.

## Contributing

Contributions are welcome! Please feel free to submit pull requests, report bugs, or suggest features.

## License

This project is licensed exclusively to the repository owner. See the LICENSE file for details.
