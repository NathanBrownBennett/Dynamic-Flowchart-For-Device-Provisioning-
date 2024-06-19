# Dynamic Flowchart for Device Provisioning

This application simplifies the provisioning of devices to employees or end-users by utilizing a dynamic flowchart. It helps in making informed decisions on what devices to provide based on various criteria such as device type, specifications, and usage (personal or work).

## Features

- **Dynamic Flowchart Generation**: Creates a visual flowchart to help decide on the provisioning of devices.
- **Device Filtering**: Filters devices from a database based on category, price range, and specifications like CPU speed, RAM, storage, and screen size.
- **Customizable Specifications**: Allows setting minimum requirements for device specifications.
- **Interactive Web Interface**: Provides a web interface for easy interaction and decision-making.

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

## Contributing

Contributions are welcome! Please feel free to submit pull requests, report bugs, or suggest features.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
