import sys
import ctypes
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from main_window import MainWindow

import os

if __name__ == "__main__":
    # Tell Windows this is a distinct app so the custom taskbar icon works
    myappid = 'rcbeamdesigner.pyside6.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "assets", "logo.ico")
    app.setWindowIcon(QIcon(logo_path))

    font = QFont("Segoe UI", 9)
    app.setFont(font)

    DARK_STYLESHEET = """
    /* ─── Base ─────────────────────────────────────────────────────────── */
    QWidget {
        background-color: #0D1117;
        color: #C9D1D9;
        font-family: "Segoe UI", "Inter", "Roboto", Arial, sans-serif;
        font-size: 9pt;
    }
    QMainWindow, QDialog {
        background-color: #0D1117;
    }

    /* ─── Scroll Area ───────────────────────────────────────────────────── */
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    QScrollArea > QWidget > QWidget {
        background-color: transparent;
    }

    /* ─── Scrollbars ────────────────────────────────────────────────────── */
    QScrollBar:vertical {
        background: #161B22;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #30363D;
        border-radius: 4px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #58A6FF;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar:horizontal {
        background: #161B22;
        height: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:horizontal {
        background: #30363D;
        border-radius: 4px;
        min-width: 20px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #58A6FF;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }

    /* ─── Tab Widget ─────────────────────────────────────────────────────── */
    QTabWidget::pane {
        border: 1px solid #21262D;
        border-top: none;
        background-color: #0D1117;
    }
    QTabBar {
        background: transparent;
    }
    QTabBar::tab {
        background: #161B22;
        color: #8B949E;
        border: 1px solid #21262D;
        border-bottom: none;
        padding: 8px 20px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-weight: 500;
        min-width: 80px;
    }
    QTabBar::tab:selected {
        background: #0D1117;
        color: #58A6FF;
        border-color: #21262D;
        border-bottom: 2px solid #58A6FF;
        font-weight: bold;
    }
    QTabBar::tab:hover:!selected {
        background: #1C2128;
        color: #C9D1D9;
    }

    /* ─── Push Buttons ───────────────────────────────────────────────────── */
    QPushButton {
        background-color: #21262D;
        color: #C9D1D9;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #30363D;
        border-color: #58A6FF;
        color: #E6EDF3;
    }
    QPushButton:pressed {
        background-color: #161B22;
    }
    QPushButton:disabled {
        color: #484F58;
        border-color: #21262D;
        background-color: #161B22;
    }

    QPushButton#primaryButton {
        background-color: #1F6FEB;
        color: #FFFFFF;
        border: 1px solid #388BFD;
        font-weight: bold;
        padding: 8px 20px;
        font-size: 10pt;
    }
    QPushButton#primaryButton:hover {
        background-color: #388BFD;
        border-color: #58A6FF;
    }
    QPushButton#primaryButton:pressed {
        background-color: #1158C7;
    }

    QPushButton#successButton {
        background-color: #238636;
        color: #FFFFFF;
        border: 1px solid #2EA043;
        font-weight: bold;
        padding: 8px 20px;
    }
    QPushButton#successButton:hover {
        background-color: #2EA043;
        border-color: #3FB950;
    }

    QPushButton#warningButton {
        background-color: #9E6A03;
        color: #FFFFFF;
        border: 1px solid #D29922;
        font-weight: bold;
        padding: 8px 20px;
    }
    QPushButton#warningButton:hover {
        background-color: #D29922;
    }

    /* ─── Inputs ─────────────────────────────────────────────────────────── */
    QLineEdit, QSpinBox, QDoubleSpinBox {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 5px 8px;
        color: #C9D1D9;
        selection-background-color: #1F6FEB;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
        border: 1px solid #58A6FF;
        background-color: #0D1117;
    }
    QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
        border-color: #484F58;
    }
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        background-color: #21262D;
        border: none;
        width: 16px;
    }
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
        background-color: #30363D;
    }

    /* ─── ComboBox ───────────────────────────────────────────────────────── */
    QComboBox {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 5px 8px;
        color: #C9D1D9;
        min-width: 80px;
    }
    QComboBox:focus {
        border-color: #58A6FF;
    }
    QComboBox:hover {
        border-color: #484F58;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QComboBox QAbstractItemView {
        background-color: #161B22;
        border: 1px solid #30363D;
        color: #C9D1D9;
        selection-background-color: #1F6FEB;
        outline: none;
    }

    /* ─── RadioButton ────────────────────────────────────────────────────── */
    QRadioButton {
        color: #C9D1D9;
        spacing: 6px;
    }
    QRadioButton::indicator {
        width: 14px;
        height: 14px;
        border-radius: 7px;
        border: 2px solid #30363D;
        background: #161B22;
    }
    QRadioButton::indicator:checked {
        background-color: #1F6FEB;
        border-color: #58A6FF;
    }
    QRadioButton::indicator:hover {
        border-color: #58A6FF;
    }

    /* ─── GroupBox ───────────────────────────────────────────────────────── */
    QGroupBox {
        border: 1px solid #21262D;
        border-radius: 8px;
        margin-top: 14px;
        padding: 12px 8px 8px 8px;
        background-color: #161B22;
        font-weight: bold;
        color: #8B949E;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 8px;
        color: #58A6FF;
        font-size: 8pt;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* ─── Table ──────────────────────────────────────────────────────────── */
    QTableView {
        background-color: #161B22;
        border: 1px solid #21262D;
        border-radius: 6px;
        gridline-color: #21262D;
        color: #C9D1D9;
        alternate-background-color: #1C2128;
        selection-background-color: #1F6FEB;
    }
    QHeaderView::section {
        background-color: #1C2128;
        color: #8B949E;
        border: none;
        border-bottom: 1px solid #30363D;
        padding: 6px;
        font-weight: bold;
        font-size: 8pt;
        text-transform: uppercase;
    }
    QTableView::item:selected {
        background-color: #1F6FEB;
        color: #FFFFFF;
    }

    /* ─── List Widget ────────────────────────────────────────────────────── */
    QListWidget {
        background-color: #161B22;
        border: 1px solid #21262D;
        border-radius: 6px;
        color: #C9D1D9;
        outline: none;
    }
    QListWidget::item {
        padding: 4px 8px;
        border-radius: 4px;
    }
    QListWidget::item:hover {
        background-color: #1C2128;
    }
    QListWidget::item:selected {
        background-color: #1F6FEB;
        color: #FFFFFF;
    }

    /* ─── TextBrowser ────────────────────────────────────────────────────── */
    QTextBrowser {
        background-color: #161B22;
        border: 1px solid #21262D;
        border-radius: 6px;
        color: #C9D1D9;
    }

    /* ─── Labels ─────────────────────────────────────────────────────────── */
    QLabel {
        color: #C9D1D9;
        background: transparent;
    }
    QLabel#heroTitle {
        font-size: 20pt;
        font-weight: 700;
        color: #E6EDF3;
        background: transparent;
    }
    QLabel#heroSub {
        font-size: 10pt;
        color: #8B949E;
        background: transparent;
    }
    QLabel#sectionHeader {
        font-size: 8pt;
        font-weight: bold;
        color: #58A6FF;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 4px 0px 2px 0px;
        background: transparent;
        border-bottom: 1px solid #21262D;
    }

    /* ─── Tooltip ────────────────────────────────────────────────────────── */
    QToolTip {
        background-color: #1C2128;
        color: #C9D1D9;
        border: 1px solid #30363D;
        border-radius: 4px;
        padding: 4px 8px;
    }
    """

    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())
