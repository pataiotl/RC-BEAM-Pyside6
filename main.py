import sys
from PySide6.QtWidgets import QApplication
from gui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set a global dark stylesheet inspired by the Streamlit version
    dark_stylesheet = """
    QWidget {
        background-color: #0f1117;
        color: #e8eaf0;
        font-family: Arial, sans-serif;
    }
    QMainWindow {
        background-color: #0f1117;
    }
    QPushButton {
        background-color: #1e2330;
        border: 1px solid #2a3044;
        border-radius: 4px;
        padding: 5px 10px;
    }
    QPushButton:hover {
        background-color: #2a3044;
    }
    QPushButton#primaryButton {
        background-color: #4f8ef7;
        color: white;
        font-weight: bold;
    }
    QPushButton#primaryButton:hover {
        background-color: #3b76e0;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #181c24;
        border: 1px solid #2a3044;
        border-radius: 3px;
        padding: 3px;
        color: #e8eaf0;
    }
    QGroupBox {
        border: 1px solid #2a3044;
        border-radius: 5px;
        margin-top: 1ex;
        background-color: #181c24;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 0 3px;
        color: #98a2b8;
    }
    QTabWidget::pane {
        border: 1px solid #2a3044;
    }
    QTabBar::tab {
        background: #1e2330;
        border: 1px solid #2a3044;
        padding: 5px;
    }
    QTabBar::tab:selected {
        background: #181c24;
        border-bottom-color: #4f8ef7;
    }
    QScrollArea {
        border: none;
    }
    QLabel#heroTitle {
        font-size: 24px;
        font-weight: bold;
        color: #e8eaf0;
    }
    QLabel#heroSub {
        font-size: 14px;
        color: #98a2b8;
    }
    QLabel#sectionHeader {
        font-size: 12px;
        font-weight: bold;
        color: #98a2b8;
        text-transform: uppercase;
        border-bottom: 1px solid #2a3044;
    }
    """
    app.setStyleSheet(dark_stylesheet)
    
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())
