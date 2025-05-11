# OpenOBS-PyGUI

OpenOBS-PyGUI is a Python-based graphical user interface (GUI) application for OpenOBS. It provides real-time spectrum plotting and sensor data visualization.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/tedlanghorst/OpenOBS-PyGUI.git
   cd OpenOBS-PyGUI
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python src/main.py
   ```

## Packaging

To package the application into an executable, use PyInstaller:

```bash
pip install pyinstaller
bash rebuild.sh
```

This will create a standalone executable in the `dist/` directory.
