# PySide6 RC Beam Designer

This directory contains the desktop application for the RC Beam Designer built with PySide6.

## Running the App

To run the app, ensure your virtual environment is active and all dependencies are installed:

```powershell
pip install -r requirements.txt
python run_pyside6.py
```

Alternatively, double-click `start_app.bat` on Windows.

## Architecture

- `run_pyside6.py`: Main entry point.
- `main_window.py`: PySide6 QMainWindow layout and event handlers.
- `beam_engine.py`: ACI 318 engineering formulas.
- `qt_models.py`: PandasTableModel for Qt integration.
- `plotting.py` and `pdf_report.py`: Output generation.
