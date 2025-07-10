# Functional Specification: Dynamic Flowchart for Device Provisioning

## Overview
This project provides an interactive toolkit to help organisations and individuals select appropriate computing devices. It combines a web application built with Flask, dynamic flowchart generation using GraphViz, and a SQLite database containing device details. Users can filter devices based on their requirements and view recommendations, security guidance and links to purchase hardware.

## Goals
- Offer a simple workflow for determining which devices meet user-defined specifications.
- Display device information, images and pricing sourced from a local database or scraped data.
- Provide security best practices and software recommendations for each device category.
- Support personal and business use cases, including government or enterprise procurement scenarios.

## User Stories
1. **As a visitor**, I can search available devices by name or filter by category, price range and minimum specifications.
2. **As a visitor**, I see a visual flowchart that helps me navigate the provisioning process and highlights recommended hardware.
3. **As a visitor**, I can view a detailed page for each device with security advice and retailer links for purchasing.
4. **As an administrator**, I can refresh the database with updated hardware information from external sources.

## System Components
### Flask Web Application
- Routes defined in `app.py` handle form submissions, database queries and page rendering.
- Templates in the `templates/` folder supply the user interface using Bootstrap styling and JavaScript for interactivity.
- Device comparison, security recommendations and flowchart image generation are triggered within these routes.

### Device Database
- `devices.db` is a SQLite database populated by `create_db.py` or the refresh endpoint in `app.py`.
- Tables hold device attributes such as CPU speed, RAM, storage and screen size.
- Additional tables provide software suggestions and security recommendations for different usage types.

### Flowchart Generation
- GraphViz is used to render device selection flowcharts as SVG images.
- For dynamic use, the `Device_Provisioning_Dynamic_Flowchart.py` script demonstrates a Solara-based interface generating graphs on demand.
- Within the Flask application, flowcharts illustrate recommended software and security measures for each device.

### Static Assets
- Images in `static/images` act as placeholders for device thumbnails and backgrounds.
- CSS stylesheets ensure a responsive layout and support light and dark themes.

## Key Features
- **Search and Filtering** – Users filter by price, CPU speed, RAM, storage, screen size and more.
- **Recommended Devices** – Default recommendations are shown on the home page if no search filters are applied.
- **Device Details** – Each device page displays specifications, security features and retailer links.
- **Flowchart Visualisation** – A dynamically generated diagram guides users through device provisioning steps.
- **Data Refresh** – The `/refresh-devices` endpoint updates the database with scraped data or fallback samples.
- **Comparison Tool** – Users can compare a selected device to similar options based on price and performance.

## Non-Goals
- The project does not provide an exhaustive catalogue of hardware from all manufacturers.
- It avoids integrating unverified third-party reviews or unsupported software recommendations.

## Future Enhancements
- Expand scraping logic in `device_scraper.py` to collect real-time information from reliable retailers.
- Implement authentication and role-based permissions for administrative actions.
- Add offline capabilities so key guidance is accessible without an internet connection.

