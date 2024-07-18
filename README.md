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

2. **Access the Web Interface**

   Open a web browser and navigate to `http://127.0.0.1:5000/` to start using the application.

## Usage

- On the web interface, select the device type, specify the price range, and set the minimum specifications required for the device.
- Submit the form to view the available devices that match the criteria.
- The application will generate a dynamic flowchart based on the selection, guiding you through the device provisioning process.

-- Watch "Demo Video.mov" to assist you if needed

## Project Structure

- **app.py**: The main Flask application file. Handles routing, form submission, querying the database, and rendering HTML templates.
- **create_db.py**: A script to create and populate the SQLite database (`devices.db`) with device data.
- **index.html**: The main HTML template for the home page. Contains the device search form, recommended devices carousel, and sections for form results, security recommendations, and educational resources.
- **device.html**: HTML template for displaying detailed information about a selected device.
- **devices.db**: SQLite database file containing device data.

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

This project is licensed under the MIT License - see the LICENSE file for details.
