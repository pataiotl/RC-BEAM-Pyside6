import sys
import os
import json
import pandas as pd
from io import BytesIO

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QLabel, QPushButton, QRadioButton, QComboBox, QLineEdit,
    QSpinBox, QDoubleSpinBox, QFileDialog, QTabWidget, QScrollArea,
    QGroupBox, QMessageBox, QTableView, QHeaderView, QListWidget,
    QListWidgetItem, QAbstractItemView, QTextBrowser
)
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QFont

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

# Import our custom modules
from beam_engine import (
    RebarGroup,
    get_rebar_group,
    calculate_beam_flexure,
    calculate_shear_torsion,
    calculate_development_length,
    calculate_skin_reinforcement,
    ZONES,
    BAR_OPTIONS,
    STIRRUP_OPTIONS,
    SKIN_BAR_OPTIONS,
)
from plotting import draw_beam_section, draw_force_diagrams
from calculation_steps import generate_calculation_html
from pdf_report import create_pdf_report
from utils import (
    DEFAULT_APP_STATE, load_workspace_excel, build_workspace_excel_bytes,
    governing_value_and_combo, safe_filename
)

from qt_models import PandasModel
from sap2000_api import get_selected_frames_forces

class StatusCard(QLabel):
    def __init__(self, kind, text):
        super().__init__(text)
        self.setWordWrap(True)
        if kind == "fail":
            bg, color, border = "#2a0a0a", "#f87171", "#991b1b"
        elif kind == "warn":
            bg, color, border = "#2a1f00", "#fbbf24", "#92400e"
        else:
            bg, color, border = "#052a14", "#22c55e", "#166534"
        self.setStyleSheet(f"background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 4px; padding: 6px; font-weight: bold;")

class MiniMetric(QWidget):
    def __init__(self, label, value, delta, status="pass"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        self.setStyleSheet("background-color: #181c24; border: 1px solid #2a3044; border-radius: 6px;")
        
        lbl_title = QLabel(label)
        lbl_title.setStyleSheet("color: #e8eaf0; font-size: 10px; font-weight: bold; border: none;")
        
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        
        lbl_delta = QLabel(delta)
        if status == "fail":
            bg, txt, border = "#2a0a0a", "#f87171", "#991b1b"
        elif status == "warn":
            bg, txt, border = "#2a1f00", "#fbbf24", "#92400e"
        else:
            bg, txt, border = "#064e24", "#22c55e", "#166534"
        lbl_delta.setStyleSheet(f"color: {txt}; background-color: {bg}; border: 1px solid {border}; border-radius: 8px; padding: 2px 4px; font-size: 9px; font-weight: bold;")
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        layout.addWidget(lbl_delta)

class CheckRow(QWidget):
    def __init__(self, label, ok, detail, warn=False):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.setStyleSheet("background-color: #181c24; border: 1px solid #2a3044; border-radius: 6px;")
        
        lbl_title = QLabel(label)
        lbl_title.setStyleSheet("font-weight: bold; color: #e8eaf0; border: none;")
        lbl_title.setMinimumWidth(150)
        
        lbl_detail = QLabel(detail)
        lbl_detail.setStyleSheet("color: #98a2b8; font-family: monospace; font-size: 11px; border: none;")
        lbl_detail.setWordWrap(True)
        
        badge = QLabel("WARN" if warn else ("PASS" if ok else "FAIL"))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(50)
        if warn:
            badge.setStyleSheet("color: #fbbf24; background-color: #2a1f00; border: 1px solid #92400e; border-radius: 4px; padding: 3px; font-family: monospace; font-weight: bold;")
        elif ok:
            badge.setStyleSheet("color: #22c55e; background-color: #052a14; border: 1px solid #166534; border-radius: 4px; padding: 3px; font-family: monospace; font-weight: bold;")
        else:
            badge.setStyleSheet("color: #f87171; background-color: #2a0a0a; border: 1px solid #991b1b; border-radius: 4px; padding: 3px; font-family: monospace; font-weight: bold;")
            
        layout.addWidget(lbl_title, 1)
        layout.addWidget(lbl_detail, 2)
        layout.addWidget(badge, 0)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RC Beam Designer - PySide6")
        self.app_state = DEFAULT_APP_STATE.copy()
        self.app_state["group_name"] = "Manual"
        self.groups = {"Manual": self.app_state}
        self.active_group_id = "Manual"
        self.inputs = {}
        self.forces = {zone: {"M": 0.0, "V": 0.0, "T": 0.0} for zone in ZONES}
        self.force_meta = {zone: {kind: "Manual input" for kind in ["M", "V", "T"]} for zone in ZONES}
        self.df_sap = None
        self.selected_frame_label = "Manual"
        
        self.init_ui()
        self.refresh_ui_from_state()

    def init_ui(self):
        self.main_tabs = QTabWidget()
        self.setCentralWidget(self.main_tabs)
        
        # ----------------- INPUT TAB -----------------
        input_tab = QWidget()
        input_layout = QVBoxLayout(input_tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        # Hero Section
        hero = QWidget()
        hero_layout = QVBoxLayout(hero)
        hero.setObjectName("heroBox")
        title = QLabel("RC Beam Designer - ACI 318-19")
        title.setObjectName("heroTitle")
        sub = QLabel("Native PySide6 desktop workspace for preliminary flexure, shear, torsion, and detailing.")
        sub.setObjectName("heroSub")
        hero_layout.addWidget(title)
        hero_layout.addWidget(sub)
        self.scroll_layout.addWidget(hero)
        
        # Workspace I/O
        io_layout = QHBoxLayout()
        btn_load = QPushButton("Load Full Workspace (.xlsx)")
        btn_load.clicked.connect(self.load_workspace)
        btn_save = QPushButton("Save Full Workspace (.xlsx)")
        btn_save.clicked.connect(self.save_workspace)
        io_layout.addWidget(btn_load)
        io_layout.addWidget(btn_save)
        self.scroll_layout.addLayout(io_layout)
        
        self.add_section_header("Active Group Selection")
        self.group_combo = QComboBox()
        self.group_combo.addItem("Manual")
        self.group_combo.currentTextChanged.connect(self.on_group_changed)
        self.scroll_layout.addWidget(self.group_combo)
        
        self.add_section_header("Force Input Source")
        self.rb_manual = QRadioButton("Manual Input")
        self.rb_sap = QRadioButton("SAP2000 CSV Upload")
        self.rb_sap_live = QRadioButton("SAP2000 Live API")
        
        self.rb_manual.toggled.connect(self.on_input_mode_changed)
        self.rb_sap.toggled.connect(self.on_input_mode_changed)
        self.rb_sap_live.toggled.connect(self.on_input_mode_changed)
        
        rb_layout = QHBoxLayout()
        rb_layout.addWidget(self.rb_manual)
        rb_layout.addWidget(self.rb_sap)
        rb_layout.addWidget(self.rb_sap_live)
        rb_layout.addStretch()
        self.scroll_layout.addLayout(rb_layout)
        
        # SAP Live API widget container
        self.live_api_widget = QWidget()
        live_api_layout = QVBoxLayout(self.live_api_widget)
        btn_fetch_live = QPushButton("Connect & Fetch Selected Frames")
        btn_fetch_live.clicked.connect(self.fetch_live_api_data)
        live_api_layout.addWidget(btn_fetch_live)
        self.live_api_status_label = QLabel("Select frames in an active SAP2000 window, then fetch.")
        self.live_api_status_label.setWordWrap(True)
        live_api_layout.addWidget(self.live_api_status_label)
        self.scroll_layout.addWidget(self.live_api_widget)
        
        # SAP input widget container
        self.sap_widget = QWidget()
        sap_layout = QVBoxLayout(self.sap_widget)
        btn_upload_sap = QPushButton("Upload SAP2000 CSV")
        btn_upload_sap.clicked.connect(self.upload_sap_csv)
        sap_layout.addWidget(btn_upload_sap)
        self.sap_status_label = QLabel("No SAP data loaded.")
        sap_layout.addWidget(self.sap_status_label)
        self.scroll_layout.addWidget(self.sap_widget)
        
        # Shared data table and grouping widget (visible for both CSV and Live API)
        self.sap_data_widget = QWidget()
        sap_data_layout = QVBoxLayout(self.sap_data_widget)
        
        self.sap_table = QTableView()
        self.sap_table.setFixedHeight(150)
        sap_data_layout.addWidget(self.sap_table)
        
        # Frame selection list with checkboxes
        sap_data_layout.addWidget(QLabel("Select Frames:"))
        self.frame_list = QListWidget()
        self.frame_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.frame_list.setFixedHeight(120)
        sap_data_layout.addWidget(self.frame_list)
        
        # Select All / Remove All buttons
        frame_btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(self.select_all_frames)
        btn_clear = QPushButton("Remove All")
        btn_clear.clicked.connect(self.clear_frames)
        frame_btn_layout.addWidget(btn_select_all)
        frame_btn_layout.addWidget(btn_clear)
        frame_btn_layout.addStretch()
        sap_data_layout.addLayout(frame_btn_layout)
        
        # Group name + Create
        group_layout = QHBoxLayout()
        self.txt_group_name = QLineEdit()
        self.txt_group_name.setPlaceholderText("Group Name (e.g. B1)")
        btn_create_group = QPushButton("Create Group from Checked Frames")
        btn_create_group.clicked.connect(self.create_group)
        group_layout.addWidget(QLabel("Group Name:"))
        group_layout.addWidget(self.txt_group_name, 1)
        group_layout.addWidget(btn_create_group)
        sap_data_layout.addLayout(group_layout)
        
        self.scroll_layout.addWidget(self.sap_data_widget)
        
        # Manual input widget container
        self.manual_widget = QWidget()
        manual_layout = QVBoxLayout(self.manual_widget)
        self.beam_length_spin = self.create_double_spin("beam_length", "Beam span L (m)", min_val=1.0, step=0.5)
        manual_layout.addLayout(self.beam_length_spin)
        
        forces_grid = QGridLayout()
        for i, zone in enumerate(ZONES):
            forces_grid.addWidget(QLabel(f"<b>{zone}</b>"), 0, i)
            forces_grid.addLayout(self.create_double_spin(f"mu_{zone.lower()}", "Mu (kNm)", 0, 5), 1, i)
            forces_grid.addLayout(self.create_double_spin(f"vu_{zone.lower()}", "Vu (kN)", 0, 5), 2, i)
            forces_grid.addLayout(self.create_double_spin(f"tu_{zone.lower()}", "Tu (kNm)", 0, 1), 3, i)
        manual_layout.addLayout(forces_grid)
        self.scroll_layout.addWidget(self.manual_widget)
        
        # Force Diagram Canvas
        self.add_section_header("Bending and Shear Diagram")
        self.force_canvas = FigureCanvas(draw_force_diagrams(self.forces, self.app_state.get("beam_length", 6.0)))
        self.force_canvas.setFixedHeight(300)
        self.scroll_layout.addWidget(self.force_canvas)
        
        # Project Input Workspace
        self.add_section_header("Project Input Workspace")
        proj_layout = QHBoxLayout()
        
        props_group = QGroupBox("Section and Materials")
        props_form = QFormLayout()
        props_form.addRow("Width b (mm):", self.create_spin_widget("b", 150, 50))
        props_form.addRow("Total depth h (mm):", self.create_spin_widget("h", 200, 50))
        props_form.addRow("Concrete fc' (MPa):", self.create_spin_widget("fc", 20, 5))
        props_form.addRow("Main steel fy (MPa):", self.create_spin_widget("fy", 300, 10))
        self.cb_lambda = QComboBox()
        self.cb_lambda.addItems(["1.0 Normal weight", "0.85 Sand-lightweight", "0.75 All-lightweight"])
        self.cb_lambda.currentIndexChanged.connect(self.update_lambda)
        props_form.addRow("Concrete type lambda:", self.cb_lambda)
        props_group.setLayout(props_form)
        proj_layout.addWidget(props_group)
        
        trans_group = QGroupBox("Transverse Steel & Skin Bars")
        trans_form = QFormLayout()
        trans_form.addRow("Stirrup fy (MPa):", self.create_spin_widget("fyt", 240, 10))
        self.cb_stirrup = self.create_combo_widget("bar_v_name", list(STIRRUP_OPTIONS.keys()))
        trans_form.addRow("Stirrup size:", self.cb_stirrup)
        trans_form.addRow("Stirrup legs:", self.create_spin_widget("n_legs", 2, 1))
        trans_form.addRow("Clear cover (mm):", self.create_spin_widget("cover_clear", 20, 5))
        trans_form.addRow("Clear spacing (mm):", self.create_spin_widget("clear_space", 20, 5))
        trans_form.addRow("Stirrup spacing (mm):", self.create_spin_widget("stirrup_spacing", 25, 25))
        trans_form.addRow("Skin bars/layer:", self.create_spin_widget("skin_bar_qty", 0, 1))
        self.cb_skin = self.create_combo_widget("skin_bar_name", list(SKIN_BAR_OPTIONS.keys()))
        trans_form.addRow("Skin bar size:", self.cb_skin)
        trans_form.addRow("Skin layers:", self.create_spin_widget("skin_layers", 1, 1))
        trans_group.setLayout(trans_form)
        proj_layout.addWidget(trans_group)
        
        self.scroll_layout.addLayout(proj_layout)
        
        # Zone Reinforcement Tabs
        self.add_section_header("Zone Reinforcement")
        self.tabs = QTabWidget()
        for zone in ZONES:
            tab = QWidget()
            tab_layout = QHBoxLayout(tab)
            
            top_form = QFormLayout()
            top_form.addRow(QLabel("<b>Top Bars</b>"))
            for i in range(1, 4):
                n_spin = self.create_spin_widget(f"t{i}_{zone}", 0, 1)
                size_cb = self.create_combo_widget(f"td{i}_{zone}", list(BAR_OPTIONS.keys()))
                row_layout = QHBoxLayout()
                row_layout.addWidget(n_spin)
                row_layout.addWidget(size_cb)
                top_form.addRow(f"L{i}:", row_layout)
                
            bot_form = QFormLayout()
            bot_form.addRow(QLabel("<b>Bottom Bars</b>"))
            for i in range(1, 4):
                n_spin = self.create_spin_widget(f"b{i}_{zone}", 0, 1)
                size_cb = self.create_combo_widget(f"bd{i}_{zone}", list(BAR_OPTIONS.keys()))
                row_layout = QHBoxLayout()
                row_layout.addWidget(n_spin)
                row_layout.addWidget(size_cb)
                bot_form.addRow(f"L{i}:", row_layout)
            
            tab_layout.addLayout(top_form)
            tab_layout.addLayout(bot_form)
            self.tabs.addTab(tab, zone)
            
        self.scroll_layout.addWidget(self.tabs)
        
        # Run Design
        run_layout = QHBoxLayout()
        self.btn_run = QPushButton("Design Active Group")
        self.btn_run.setObjectName("primaryButton")
        self.btn_run.clicked.connect(lambda checked=False: self.run_design())
        run_layout.addWidget(self.btn_run)
        
        self.btn_run_all = QPushButton("Design All Groups")
        self.btn_run_all.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_run_all.clicked.connect(lambda checked=False: self.run_all_groups_design())
        run_layout.addWidget(self.btn_run_all)
        
        self.scroll_layout.addLayout(run_layout)
        
        scroll.setWidget(scroll_content)
        input_layout.addWidget(scroll)
        self.main_tabs.addTab(input_tab, "Input")
        
        # ----------------- RESULTS TAB -----------------
        self.results_tab = QWidget()
        self.results_tab_layout = QVBoxLayout(self.results_tab)
        
        res_header = QHBoxLayout()
        res_header.addWidget(QLabel("Select Group:"))
        self.results_group_combo = QComboBox()
        self.results_group_combo.currentTextChanged.connect(self.on_results_group_changed)
        res_header.addWidget(self.results_group_combo, 1)
        self.results_tab_layout.addLayout(res_header)
        
        res_scroll = QScrollArea()
        res_scroll.setWidgetResizable(True)
        res_scroll_content = QWidget()
        self.results_layout = QVBoxLayout(res_scroll_content)
        
        # We keep self.results_container for compatibility with existing code
        self.results_container = QWidget()
        self.results_inner_layout = QVBoxLayout(self.results_container)
        self.results_layout.addWidget(self.results_container)
        
        res_scroll.setWidget(res_scroll_content)
        self.results_tab_layout.addWidget(res_scroll)
        
        self.main_tabs.addTab(self.results_tab, "Results")
        
        # ----------------- EXPORT TAB -----------------
        self.export_tab = QWidget()
        self.export_tab_layout = QVBoxLayout(self.export_tab)
        
        self.export_tab_layout.addWidget(QLabel("Select Groups to Export:"))
        self.export_list = QListWidget()
        self.export_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.export_tab_layout.addWidget(self.export_list)
        
        exp_btn_layout1 = QHBoxLayout()
        btn_sel_all = QPushButton("Select All")
        btn_sel_all.clicked.connect(lambda: self.set_export_list_state(Qt.Checked))
        btn_unsel_all = QPushButton("Remove All")
        btn_unsel_all.clicked.connect(lambda: self.set_export_list_state(Qt.Unchecked))
        exp_btn_layout1.addWidget(btn_sel_all)
        exp_btn_layout1.addWidget(btn_unsel_all)
        exp_btn_layout1.addStretch()
        self.export_tab_layout.addLayout(exp_btn_layout1)
        
        exp_btn_layout2 = QHBoxLayout()
        btn_exp_sel = QPushButton("Export Selected")
        btn_exp_sel.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_exp_sel.clicked.connect(self.export_selected_groups_pdf)
        btn_exp_all = QPushButton("Export All")
        btn_exp_all.setStyleSheet("background-color: #7c3aed; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_exp_all.clicked.connect(self.export_all_groups_pdf)
        exp_btn_layout2.addWidget(btn_exp_sel)
        exp_btn_layout2.addWidget(btn_exp_all)
        self.export_tab_layout.addLayout(exp_btn_layout2)
        
        self.main_tabs.addTab(self.export_tab, "Export")
        
        # ----------------- CALCULATIONS TAB -----------------
        self.calc_tab = QWidget()
        self.calc_tab_layout = QVBoxLayout(self.calc_tab)
        
        calc_header = QHBoxLayout()
        calc_header.addWidget(QLabel("Select Group:"))
        self.calc_group_combo = QComboBox()
        self.calc_group_combo.currentTextChanged.connect(self.on_calc_dropdowns_changed)
        calc_header.addWidget(self.calc_group_combo)
        
        calc_header.addWidget(QLabel("Select Zone:"))
        self.calc_zone_combo = QComboBox()
        self.calc_zone_combo.addItems(["Left", "Mid", "Right"])
        self.calc_zone_combo.currentTextChanged.connect(self.on_calc_dropdowns_changed)
        calc_header.addWidget(self.calc_zone_combo)
        calc_header.addStretch()
        
        self.calc_tab_layout.addLayout(calc_header)
        
        self.calc_browser = QTextBrowser()
        self.calc_tab_layout.addWidget(self.calc_browser)
        
        self.main_tabs.addTab(self.calc_tab, "Calculations")
        
        # Hide tabs initially
        self.main_tabs.setTabVisible(1, False)
        self.main_tabs.setTabVisible(2, False)
        self.main_tabs.setTabVisible(3, False)
        
        self.rb_manual.setChecked(True)

    def add_section_header(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        self.scroll_layout.addWidget(lbl)
        
    def create_double_spin(self, key, label, min_val, step):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        spin = QDoubleSpinBox()
        spin.setMinimum(min_val)
        spin.setMaximum(99999)
        spin.setSingleStep(step)
        spin.valueChanged.connect(lambda v, k=key: self.update_state(k, v))
        self.inputs[key] = spin
        layout.addWidget(spin)
        return layout

    def create_spin_widget(self, key, min_val, step):
        spin = QSpinBox()
        spin.setMinimum(min_val)
        spin.setMaximum(9999)
        spin.setSingleStep(step)
        spin.valueChanged.connect(lambda v, k=key: self.update_state(k, v))
        self.inputs[key] = spin
        return spin
        
    def create_combo_widget(self, key, options):
        cb = QComboBox()
        cb.addItems(options)
        cb.currentTextChanged.connect(lambda v, k=key: self.update_state(k, v))
        self.inputs[key] = cb
        return cb

    def update_state(self, key, value):
        self.app_state[key] = value
        if key in ["beam_length"] or key.startswith(("mu_", "vu_", "tu_")):
            self.update_forces_from_state()

    def update_lambda(self, index):
        values = [1.0, 0.85, 0.75]
        self.app_state["lambda_c"] = values[index]

    def refresh_ui_from_state(self):
        # Update inputs based on app_state without triggering signals to avoid loops
        for key, widget in self.inputs.items():
            widget.blockSignals(True)
            val = self.app_state.get(key)
            if isinstance(widget, QDoubleSpinBox) or isinstance(widget, QSpinBox):
                if val is not None:
                    widget.setValue(float(val))
            elif isinstance(widget, QComboBox):
                if val is not None:
                    idx = widget.findText(str(val))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
            widget.blockSignals(False)

        lam = self.app_state.get("lambda_c", 1.0)
        idx = 0 if lam == 1.0 else (1 if lam == 0.85 else 2)
        self.cb_lambda.blockSignals(True)
        self.cb_lambda.setCurrentIndex(idx)
        self.cb_lambda.blockSignals(False)

        if self.app_state.get("input_mode") == "SAP2000 CSV Upload":
            self.rb_sap.setChecked(True)
        elif self.app_state.get("input_mode") == "SAP2000 Live API":
            self.rb_sap_live.setChecked(True)
        else:
            self.rb_manual.setChecked(True)
            
        self.update_forces_from_state()

    def on_input_mode_changed(self):
        if self.rb_sap.isChecked():
            self.app_state["input_mode"] = "SAP2000 CSV Upload"
            self.sap_widget.setVisible(True)
            self.live_api_widget.setVisible(False)
            self.sap_data_widget.setVisible(True)
            self.manual_widget.setVisible(False)
            self.process_sap_data()
        elif self.rb_sap_live.isChecked():
            self.app_state["input_mode"] = "SAP2000 Live API"
            self.sap_widget.setVisible(False)
            self.live_api_widget.setVisible(True)
            self.sap_data_widget.setVisible(True)
            self.manual_widget.setVisible(False)
            self.process_sap_data()
        else:
            self.app_state["input_mode"] = "Manual Input"
            self.sap_widget.setVisible(False)
            self.live_api_widget.setVisible(False)
            self.sap_data_widget.setVisible(False)
            self.manual_widget.setVisible(True)
            self.update_forces_from_state()
            
        self.refresh_group_combo()
        
    def refresh_group_combo(self):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        mode = self.app_state.get("input_mode", "Manual Input")
        for g_name in self.groups:
            if g_name == "Manual" and mode != "Manual Input":
                continue
            self.group_combo.addItem(g_name)
            
        if self.active_group_id in [self.group_combo.itemText(i) for i in range(self.group_combo.count())]:
            self.group_combo.setCurrentText(self.active_group_id)
        elif self.group_combo.count() > 0:
            self.group_combo.setCurrentIndex(0)
            self.on_group_changed(self.group_combo.currentText())
        self.group_combo.blockSignals(False)
            
    
    def on_group_changed(self, group_name):
        if group_name and group_name in self.groups:
            self.active_group_id = group_name
            self.app_state = self.groups[group_name]
            # Restore per-group forces if stored
            if "_forces" in self.app_state:
                self.forces = self.app_state["_forces"]
                self.force_meta = self.app_state["_force_meta"]
            # Update UI fields to match new app_state
            self.update_forces_from_state()
            self.refresh_ui_from_state()

    def get_checked_frames(self):
        """Return list of frame IDs that are checked in the frame_list."""
        checked = []
        for i in range(self.frame_list.count()):
            item = self.frame_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked

    def select_all_frames(self):
        for i in range(self.frame_list.count()):
            self.frame_list.item(i).setCheckState(Qt.Checked)
            
    def clear_frames(self):
        for i in range(self.frame_list.count()):
            self.frame_list.item(i).setCheckState(Qt.Unchecked)

    def create_group(self):
        if self.df_sap is None or self.df_sap.empty:
            QMessageBox.warning(self, "No Data", "Please load SAP data first.")
            return
            
        checked_frames = self.get_checked_frames()
        group_name = self.txt_group_name.text().strip()
        
        if not checked_frames:
            QMessageBox.warning(self, "No Frames", "Please check at least one frame in the list.")
            return
        if not group_name:
            QMessageBox.warning(self, "No Name", "Please enter a group name (e.g. B1).")
            return
            
        df_group = self.df_sap[self.df_sap["Frame"].astype(str).isin(checked_frames)]
        if df_group.empty:
            QMessageBox.warning(self, "Not Found", "None of the checked frames were found in the data.")
            return
            
        # Calculate envelope forces for each zone
        new_state = self.app_state.copy()
        new_state["group_name"] = group_name
        new_state["input_mode"] = self.app_state["input_mode"]
        
        # Build per-zone force dicts for this group
        grp_forces = {zone: {"M": 0.0, "V": 0.0, "T": 0.0} for zone in ZONES}
        grp_meta = {zone: {"M": f"{group_name} envelope", "V": f"{group_name} envelope", "T": f"{group_name} envelope"} for zone in ZONES}

        stations = sorted(df_group["Station"].unique())
        if len(stations) >= 3:
            st_left, st_mid, st_right = stations[0], stations[len(stations)//2], stations[-1]
            new_state["beam_length"] = st_right - st_left
            
            for zone, st in zip(["Left", "Mid", "Right"], [st_left, st_mid, st_right]):
                df_st = df_group[df_group["Station"] == st]
                if not df_st.empty:
                    grp_forces[zone]["M"] = float(df_st["M3"].abs().max())
                    grp_forces[zone]["V"] = float(df_st["V2"].abs().max())
                    grp_forces[zone]["T"] = float(df_st["T"].abs().max())
                    # Also store in state for persistence
                    new_state[f"mu_{zone.lower()}"] = grp_forces[zone]["M"]
                    new_state[f"vu_{zone.lower()}"] = grp_forces[zone]["V"]
                    new_state[f"tu_{zone.lower()}"] = grp_forces[zone]["T"]
        
        # Persist forces and meta inside the group state so they survive group switching
        new_state["_forces"] = grp_forces
        new_state["_force_meta"] = grp_meta

        self.groups[group_name] = new_state
        self.refresh_group_combo()
        self.group_combo.setCurrentText(group_name)
        QMessageBox.information(self, "Success", f"Group '{group_name}' created with {len(checked_frames)} frames.")

    def on_results_group_changed(self, group_name):
        if not group_name or group_name not in self.groups:
            return
        
        # Load the state of the selected group and run design for it to render the results
        prev_group = self.active_group_id
        prev_forces = {z: dict(v) for z, v in self.forces.items()}
        prev_meta = {z: dict(v) for z, v in self.force_meta.items()}

        self.app_state = self.groups[group_name]
        # Restore per-group forces
        if "_forces" in self.app_state:
            self.forces = self.app_state["_forces"]
            self.force_meta = self.app_state["_force_meta"]
        self.update_forces_from_state()
        self.run_design(switch_tab=False)
        self.on_calc_dropdowns_changed()

        # Restore previous group
        self.app_state = self.groups[prev_group]
        self.forces = prev_forces
        self.force_meta = prev_meta
        self.update_forces_from_state()

    def set_export_list_state(self, state):
        for i in range(self.export_list.count()):
            self.export_list.item(i).setCheckState(state)

    def _get_groups_for_output(self):
        groups_to_show = []
        mode = self.app_state.get("input_mode", "Manual Input")
        for g_name in self.groups:
            if g_name == "Manual" and mode != "Manual Input":
                continue
            groups_to_show.append(g_name)
        return groups_to_show

    def _unlock_and_populate_tabs(self):
        # Make tabs visible
        self.main_tabs.setTabVisible(1, True)
        self.main_tabs.setTabVisible(2, True)
        self.main_tabs.setTabVisible(3, True)
        
        groups_to_show = self._get_groups_for_output()
        
        # Populate Results tab combo
        self.results_group_combo.blockSignals(True)
        self.results_group_combo.clear()
        self.results_group_combo.addItems(groups_to_show)
        if self.active_group_id in groups_to_show:
            self.results_group_combo.setCurrentText(self.active_group_id)
        self.results_group_combo.blockSignals(False)
        
        # Populate Calculations tab combo
        self.calc_group_combo.blockSignals(True)
        self.calc_group_combo.clear()
        self.calc_group_combo.addItems(groups_to_show)
        if self.active_group_id in groups_to_show:
            self.calc_group_combo.setCurrentText(self.active_group_id)
        self.calc_group_combo.blockSignals(False)
        self.on_calc_dropdowns_changed()
        
        # Populate Export tab checklist
        self.export_list.clear()
        for g in groups_to_show:
            item = QListWidgetItem(g)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.export_list.addItem(item)

    def _build_all_groups_pdf(self):
        """Run design on every group and return PDF bytes."""
        pdf_groups = []
        prev_group = self.active_group_id
        
        for g_name, g_state in self.groups.items():
            if g_name == "Manual" and self.app_state.get("input_mode") != "Manual Input":
                continue
            
            self.app_state = g_state
            if "_forces" in g_state:
                self.forces = g_state["_forces"]
                self.force_meta = g_state["_force_meta"]
            self.update_forces_from_state()
            self.run_design()
            
            group_data = {
                "group_name": g_name,
                "b": self.app_state.get("b", 300),
                "h": self.app_state.get("h", 600),
                "fc": self.app_state.get("fc", 35),
                "fy": self.app_state.get("fy", 500),
                "fyt": self.app_state.get("fyt", 400),
                "zone_data": self.last_zone_results.copy()
            }
            pdf_groups.append(group_data)
            
        # Restore active group
        self.app_state = self.groups[prev_group]
        self.update_forces_from_state()
        self.run_design()
        return pdf_groups

    def run_all_groups_design(self):
        """Design every group and show results for the last active one."""
        if len(self.groups) <= 1 and "Manual" in self.groups:
            QMessageBox.information(self, "Info", "Only the Manual group exists. Create groups from SAP data first, or use 'Design Active Group'.")
            return
        self._build_all_groups_pdf()
        self._unlock_and_populate_tabs()
        self.main_tabs.setCurrentIndex(1)
        QMessageBox.information(self, "Done", f"All {len(self.groups)} groups have been designed successfully.")

    def export_selected_groups_pdf(self):
        """Design and export only the checked groups in the Export tab."""
        checked = []
        for i in range(self.export_list.count()):
            item = self.export_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        
        if not checked:
            QMessageBox.warning(self, "Warning", "No groups selected for export.")
            return
            
        pdf_groups = []
        prev_group = self.active_group_id
        
        for g_name in checked:
            if g_name in self.groups:
                self.app_state = self.groups[g_name]
                self.update_forces_from_state()
                self.run_design(switch_tab=False)
                
                group_data = {
                    "group_name": g_name,
                    "b": self.app_state.get("b", 300),
                    "h": self.app_state.get("h", 600),
                    "fc": self.app_state.get("fc", 35),
                    "fy": self.app_state.get("fy", 500),
                    "fyt": self.app_state.get("fyt", 400),
                    "zone_data": self.last_zone_results.copy()
                }
                pdf_groups.append(group_data)
                
        # Restore active group
        self.app_state = self.groups[prev_group]
        self.update_forces_from_state()
        self.run_design(switch_tab=False)
        
        from pdf_report import create_pdf_report
        pdf_bytes = create_pdf_report(pdf_groups, self.app_state.get("input_mode", "Manual Input"))
        
        fname, _ = QFileDialog.getSaveFileName(self, "Save Selected Groups PDF", "Selected_Groups_Report.pdf", "PDF Files (*.pdf)")
        if fname:
            with open(fname, "wb") as f:
                f.write(pdf_bytes)
            QMessageBox.information(self, "Exported", f"PDF with {len(pdf_groups)} group(s) saved to {fname}")

    def export_all_groups_pdf(self):
        """Design every group and export a multi-page PDF."""
        pdf_groups = self._build_all_groups_pdf()
        
        from pdf_report import create_pdf_report
        pdf_bytes = create_pdf_report(pdf_groups, self.app_state.get("input_mode", "Manual Input"))
        
        fname, _ = QFileDialog.getSaveFileName(self, "Save All Groups PDF", "All_Groups_Report.pdf", "PDF Files (*.pdf)")
        if fname:
            with open(fname, "wb") as f:
                f.write(pdf_bytes)
            QMessageBox.information(self, "Exported", f"PDF with {len(pdf_groups)} group(s) saved to {fname}")

    def update_forces_from_state(self):
        if self.app_state.get("input_mode") == "Manual Input":
            for zone in ZONES:
                self.forces[zone]["M"] = self.app_state.get(f"mu_{zone.lower()}", 0.0)
                self.forces[zone]["V"] = self.app_state.get(f"vu_{zone.lower()}", 0.0)
                self.forces[zone]["T"] = self.app_state.get(f"tu_{zone.lower()}", 0.0)
                self.force_meta[zone] = {"M": "Manual", "V": "Manual", "T": "Manual"}
            self.selected_frame_label = "Manual"
            self.update_force_diagram()

    def update_force_diagram(self):
        fig = draw_force_diagrams(self.forces, self.app_state.get("beam_length", 6.0), self.df_sap, self.selected_frame_label)
        self.force_canvas.figure = fig
        self.force_canvas.draw()

    def upload_sap_csv(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open SAP2000 CSV", "", "CSV Files (*.csv)")
        if fname:
            try:
                df_raw = pd.read_csv(fname)
                self.app_state["sap_raw_json"] = df_raw.to_json(orient="split")
                self.process_sap_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load CSV: {str(e)}")

    def fetch_live_api_data(self):
        try:
            self.live_api_status_label.setText("Connecting to SAP2000...")
            df_raw = get_selected_frames_forces()
            self.app_state["sap_raw_json"] = df_raw.to_json(orient="split")
            self.live_api_status_label.setText(f"Success! Fetched forces for {len(df_raw['Frame'].unique())} frames.")
            self.process_sap_data()
        except Exception as e:
            self.live_api_status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(self, "API Error", str(e))

    def process_sap_data(self):
        sap_json = self.app_state.get("sap_raw_json", "")
        if not sap_json:
            self.sap_status_label.setText("No SAP data loaded.")
            self.df_sap = None
            return
            
        try:
            df_raw = pd.read_json(BytesIO(sap_json.encode('utf-8')), orient="split")
            if "Frame" in df_raw.columns and str(df_raw["Frame"].iloc[0]).strip().lower() == "text":
                df_raw = df_raw.drop(0).reset_index(drop=True)
            for col in ["Station", "P", "V2", "V3", "T", "M2", "M3"]:
                if col in df_raw.columns:
                    df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")
                    
            if "Frame" not in df_raw.columns:
                self.sap_status_label.setText("CSV must contain a Frame column.")
                return
                
            available_frames = sorted(df_raw["Frame"].dropna().astype(str).unique().tolist())
            if not available_frames:
                self.sap_status_label.setText("No frame IDs found.")
                return
            
            # Store full raw data for grouping
            self.df_sap = df_raw
            
            # Populate data table and frame checklist
            self.sap_table.setModel(PandasModel(df_raw.head(100)))
            self.frame_list.clear()
            for f in available_frames:
                item = QListWidgetItem(str(f))
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.frame_list.addItem(item)
            
            # Auto-analyze first frame for immediate display
            selected = available_frames[0]
            self.sap_status_label.setText(f"Loaded frames: {len(available_frames)}. Currently analyzing Frame {selected}")
            self.selected_frame_label = selected
            
            df = df_raw[df_raw["Frame"].astype(str) == selected].copy()
            if "OutputCase" not in df.columns:
                df["OutputCase"] = "Manual"
            if not df.empty and {"Station", "V2", "T", "M3"}.issubset(df.columns):
                df["V2_abs"] = df["V2"].abs()
                df["T_abs"] = df["T"].abs()
                beam_length = max(float(df["Station"].max()), 1.0)
                self.app_state["beam_length"] = beam_length
                
                df_left = df[df["Station"] <= 0.1 * beam_length]
                df_right = df[df["Station"] >= 0.9 * beam_length]
                df_mid = df[(df["Station"] > 0.3 * beam_length) & (df["Station"] < 0.7 * beam_length)]
                
                zone_frames = {"Left": df_left, "Mid": df_mid if not df_mid.empty else df, "Right": df_right}
                for zone, zdf in zone_frames.items():
                    self.forces[zone]["M"], self.force_meta[zone]["M"] = governing_value_and_combo(zdf, "M3")
                    self.forces[zone]["V"], self.force_meta[zone]["V"] = governing_value_and_combo(zdf, "V2", "V2_abs")
                    self.forces[zone]["T"], self.force_meta[zone]["T"] = governing_value_and_combo(zdf, "T", "T_abs")
                
            self.update_force_diagram()
        except Exception as e:
            self.sap_status_label.setText(f"Error parsing SAP data: {e}")

    def load_workspace(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load Workspace", "", "Excel Files (*.xlsx)")
        if fname:
            try:
                with open(fname, 'rb') as f:
                    updates, sap_json = load_workspace_excel(f.read())
                for k, v in updates.items():
                    self.app_state[k] = v
                if sap_json:
                    self.app_state["sap_raw_json"] = sap_json
                self.refresh_ui_from_state()
                QMessageBox.information(self, "Success", "Workspace loaded successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load workspace: {e}")

    def save_workspace(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Workspace", "rc_beam_workspace.xlsx", "Excel Files (*.xlsx)")
        if fname:
            try:
                excel_bytes = build_workspace_excel_bytes(
                    self.app_state, self.app_state.get("input_mode"),
                    self.app_state.get("beam_length"), self.forces, self.force_meta,
                    self.selected_frame_label, self.app_state.get("sap_raw_json", ""),
                    getattr(self, 'last_summary', []), getattr(self, 'last_zone_results', {})
                )
                with open(fname, 'wb') as f:
                    f.write(excel_bytes)
                QMessageBox.information(self, "Success", "Workspace saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save workspace: {e}")

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def run_design(self, switch_tab=True):
        if self.app_state.get("input_mode") == "Manual Input":
            self.update_forces_from_state()
            
        self.clear_layout(self.results_inner_layout)
        
        
        lbl = QLabel("Three-Zone Cross Sections and Calculations")
        lbl.setObjectName("sectionHeader")
        self.results_inner_layout.addWidget(lbl)
        
        zones_layout = QHBoxLayout()
        self.last_zone_results = {}
        self.last_zone_raw_results = {}
        self.last_summary = []
        
        b = self.app_state.get("b", 300)
        h = self.app_state.get("h", 600)
        fc = self.app_state.get("fc", 35)
        fy = self.app_state.get("fy", 500)
        fyt = self.app_state.get("fyt", 400)
        lambda_c = self.app_state.get("lambda_c", 1.0)
        cover_clear = self.app_state.get("cover_clear", 40)
        clear_space = self.app_state.get("clear_space", 25)
        stirrup_spacing = self.app_state.get("stirrup_spacing", 150)
        bar_v = STIRRUP_OPTIONS[self.app_state.get("bar_v_name", "DB10")]
        n_legs = self.app_state.get("n_legs", 2)
        skin_qty = self.app_state.get("skin_bar_qty", 2)
        skin_name = self.app_state.get("skin_bar_name", "DB12")
        skin_dia = SKIN_BAR_OPTIONS[skin_name]
        skin_layers = self.app_state.get("skin_layers", 2)
        
        for zone in ZONES:
            zone_col = QVBoxLayout()
            title = QLabel(f"<b>{zone} Section</b>")
            zone_col.addWidget(title)
            
            top_rg = get_rebar_group(
                self.app_state.get(f"t1_{zone}", 0), BAR_OPTIONS[self.app_state.get(f"td1_{zone}", "DB25")],
                self.app_state.get(f"t2_{zone}", 0), BAR_OPTIONS[self.app_state.get(f"td2_{zone}", "DB20")],
                self.app_state.get(f"t3_{zone}", 0), BAR_OPTIONS[self.app_state.get(f"td3_{zone}", "DB20")],
                cover_clear, bar_v, clear_space
            )
            bot_rg = get_rebar_group(
                self.app_state.get(f"b1_{zone}", 0), BAR_OPTIONS[self.app_state.get(f"bd1_{zone}", "DB25")],
                self.app_state.get(f"b2_{zone}", 0), BAR_OPTIONS[self.app_state.get(f"bd2_{zone}", "DB20")],
                self.app_state.get(f"b3_{zone}", 0), BAR_OPTIONS[self.app_state.get(f"bd3_{zone}", "DB20")],
                cover_clear, bar_v, clear_space
            )
            
            if top_rg.width_req > b or bot_rg.width_req > b:
                err = QLabel(f"Bars do not fit in {b} mm width.")
                err.setStyleSheet("color: #f87171;")
                zone_col.addWidget(err)
                self.last_zone_results[zone] = None
                zones_layout.addLayout(zone_col)
                continue
                
            if zone == "Mid":
                As_tens, As_comp = bot_rg.area, top_rg.area
                d = h - bot_rg.centroid
                dt = h - bot_rg.extreme_fiber
                d_prime = top_rg.centroid
                comp_face = "top"
            else:
                As_tens, As_comp = top_rg.area, bot_rg.area
                d = h - top_rg.centroid
                dt = h - top_rg.extreme_fiber
                d_prime = bot_rg.centroid
                comp_face = "bottom"
                
            Mu = abs(self.forces[zone]["M"])
            Vu_design = abs(self.forces[zone]["V"])
            Tu_design = abs(self.forces[zone]["T"])
            m_combo = self.force_meta[zone]["M"]
            v_combo = self.force_meta[zone]["V"]
            t_combo = self.force_meta[zone]["T"]
            
            res_flex = calculate_beam_flexure(b, h, d, dt, d_prime, fc, fy, As_tens, As_comp)
            res_shear = calculate_shear_torsion(b, h, d, fc, fyt, fy, cover_clear, Vu_design, Tu_design, n_legs, bar_v, lambda_c, stirrup_spacing)
            skin = calculate_skin_reinforcement(h, d, skin_dia, skin_qty, skin_layers)
            
            top_bar_dia = BAR_OPTIONS[self.app_state.get(f"td1_{zone}", "DB25")]
            bot_bar_dia = BAR_OPTIONS[self.app_state.get(f"bd1_{zone}", "DB25")]
            dev_top = calculate_development_length(top_bar_dia, fy, fc, True, cover_clear, clear_space, lambda_c)
            dev_bot = calculate_development_length(bot_bar_dia, fy, fc, False, cover_clear, clear_space, lambda_c)
            
            dc_flex = round(Mu / res_flex["phi_Mn"], 2) if res_flex["phi_Mn"] > 0 else 999.9
            dc_pure_shear = Vu_design / res_shear["phi_Vn"] if res_shear.get("phi_Vn", 0) > 0 else 999.9
            dc_steel_force = res_shear.get("final_s", 0) / res_shear.get("s_calc", 9999) if res_shear.get("s_calc", 9999) > 0 else 0
            dc_shear = round(max(dc_pure_shear, dc_steel_force), 2)
            
            flex_ok = (
                res_flex["converged"]
                and res_flex["passes_As_min"]
                and res_flex["is_ductile"]
                and res_flex["passes_As_max_tc"]
                and res_flex["phi_Mn"] >= Mu
            )
            shear_ok = res_shear["phi_Vn"] >= Vu_design and res_shear["spacing_ok"] and not res_shear["section_fails"]

            if flex_ok and shear_ok:
                zone_col.addWidget(StatusCard("pass", f"{zone} passes flexure and shear/torsion preliminary checks."))
            elif res_flex["phi_Mn"] >= Mu and shear_ok:
                zone_col.addWidget(StatusCard("warn", f"{zone} has enough strength, but detailing or ductility needs review."))
            else:
                zone_col.addWidget(StatusCard("fail", f"{zone} fails one or more required checks."))

            flex_ui = "pass" if dc_flex <= 1.0 else "fail"
            dc_pure_shear_rounded = round(dc_pure_shear, 2)
            shear_ui = "pass" if dc_pure_shear_rounded <= 1.0 else "fail"
            stirrup_ui = "pass" if dc_shear <= 1.0 else "fail"
            stirrup_value = f"{n_legs}-DB{bar_v}"
            stirrup_label = f"@ {res_shear['final_s']} mm | D/C {dc_shear}"
            strain_ui = "pass" if res_flex["strain_class"] == "Tension-controlled" else ("warn" if res_flex["strain_class"] == "Transition zone" else "fail")

            metrics_layout = QGridLayout()
            metrics_layout.addWidget(MiniMetric("phi Mn", f"{res_flex['phi_Mn']} kNm", f"{m_combo} | D/C {dc_flex}", flex_ui), 0, 0)
            metrics_layout.addWidget(MiniMetric("phi Vn", f"{res_shear['phi_Vn']} kN", f"{v_combo} | D/C {dc_pure_shear_rounded}", shear_ui), 0, 1)
            metrics_layout.addWidget(MiniMetric("Stirrups", stirrup_value, stirrup_label, stirrup_ui), 1, 0)
            metrics_layout.addWidget(MiniMetric("Strain", f"{res_flex['eps_t']}", res_flex["strain_class"], strain_ui), 1, 1)
            zone_col.addLayout(metrics_layout)

            fig = draw_beam_section(b, h, cover_clear, bar_v, top_rg, bot_rg, res_flex, zone, skin, skin_dia, comp_face)
            canvas = FigureCanvas(fig)
            canvas.setFixedHeight(200)
            zone_col.addWidget(canvas)
            
            lbl_checks = QLabel("<b>ACI Style Checks</b>")
            lbl_checks.setStyleSheet("color: #98a2b8; margin-top: 10px; border-bottom: 1px solid #2a3044;")
            zone_col.addWidget(lbl_checks)

            zone_col.addWidget(CheckRow("Flexure phiMn >= Mu", res_flex["phi_Mn"] >= Mu, f"{m_combo}; {res_flex['phi_Mn']} >= {Mu:.1f} kNm"))
            zone_col.addWidget(CheckRow("Minimum As", res_flex["passes_As_min"], f"As = {As_tens:.1f}; As,min = {res_flex['As_min']} mm2"))
            zone_col.addWidget(CheckRow("Tension-controlled", res_flex["is_ductile"], f"eps_t = {res_flex['eps_t']}; phi = {res_flex['phi']}", warn=not res_flex["is_ductile"] and res_flex["phi_Mn"] >= Mu))
            zone_col.addWidget(CheckRow("Max As tension-controlled", res_flex["passes_As_max_tc"], f"As = {As_tens:.1f}; As,max,tc = {res_flex['As_max_tc']} mm2"))
            zone_col.addWidget(CheckRow("Shear phiVn >= Vu", res_shear["phi_Vn"] >= Vu_design, f"{v_combo}; {res_shear['phi_Vn']} >= {Vu_design:.1f} kN"))
            zone_col.addWidget(CheckRow("Max Shear/Torsion Web Crushing", not res_shear["section_fails"], f"Stress = {res_shear['combined_stress']:.2f} MPa <= Limit = {res_shear['stress_limit']:.2f} MPa"))
            zone_col.addWidget(CheckRow("Transverse spacing", res_shear["spacing_ok"], f"s use = {res_shear['final_s']} mm; s exact = {res_shear['s_exact']} mm; s max = {res_shear['s_max']} mm"))
            zone_col.addWidget(CheckRow("Torsion threshold", not res_shear["needs_torsion"], f"{t_combo}; Tu = {Tu_design:.1f} kNm; phiTth = {res_shear['T_th']} kNm", warn=res_shear["needs_torsion"]))

            if not skin["required"]:
                skin_detail = f"{skin['layers']} layer(s) of {skin['bars_per_layer']}-DB{skin_dia}; h = {h:.0f} mm <= 900 mm, not required"
            else:
                skin_detail = f"{skin['layers']} layer(s) of {skin['bars_per_layer']}-DB{skin_dia}; s = {skin['spacing']} <= {skin['s_limit']} mm"
            zone_col.addWidget(CheckRow("ACI side-face skin bars", skin["spacing_ok"], skin_detail))

            if res_shear["needs_torsion"]:
                gross_perimeter = 2 * (b + h)
                face_ratio = b / gross_perimeter
                side_ratio = (2 * h) / gross_perimeter
                Al_req_face = res_shear["Al_req"] * face_ratio
                Al_req_sides = res_shear["Al_req"] * side_ratio

                flex_utilization = Mu / res_flex["phi_Mn"] if res_flex["phi_Mn"] > 0 else 1.0
                As_flex_req = As_tens * min(flex_utilization, 1.0)
                tension_face_prov = bot_rg.area if zone == "Mid" else top_rg.area
                tension_face_req = As_flex_req + Al_req_face
                tension_face_ok = tension_face_prov >= tension_face_req

                side_face_prov = skin["area_total"]
                side_face_ok = side_face_prov >= Al_req_sides
                torsion_long_ok = tension_face_ok and side_face_ok

                if torsion_long_ok:
                    torsion_long_detail = f"Tension face and sides OK. Al req side: {Al_req_sides:.0f} mm2, face: {Al_req_face:.0f} mm2"
                else:
                    torsion_long_detail = f"FAIL: tension face {tension_face_prov:.0f}/{tension_face_req:.0f} mm2. Sides {side_face_prov:.0f}/{Al_req_sides:.0f} mm2"
            else:
                torsion_long_ok = True
                torsion_long_detail = "Tu <= phiTth; longitudinal torsion steel not required"
            
            zone_col.addWidget(CheckRow("Face-by-face torsion steel Al", torsion_long_ok, torsion_long_detail))

            # Add Calculation Summary Button & Table
            calc_data = [
                ("d", f"{d:.1f} mm", "Effective depth"),
                ("d'", f"{d_prime:.1f} mm", "Compression steel depth"),
                ("Governing Mu combo", m_combo, f"Mu = {Mu:.1f} kNm"),
                ("Governing Vu combo", v_combo, f"Vu = {Vu_design:.1f} kN"),
                ("Governing Tu combo", t_combo, f"Tu = {Tu_design:.1f} kNm"),
                ("c / a", f"{res_flex['c']} / {res_flex['a']} mm", "Neutral axis and stress block"),
                ("Mn / phiMn", f"{res_flex['Mn']} / {res_flex['phi_Mn']} kNm", "Nominal and design moment"),
                ("lambda_s", res_shear["lambda_s"], "Size effect factor shown for reference"),
                ("Aoh / ph", f"{res_shear['Aoh']:.0f} mm2 / {res_shear['ph']:.0f} mm", "Torsion cage geometry"),
                ("Al torsion", f"{res_shear['Al_req']} mm2", "Required if torsion governs"),
                ("Skin bars", skin_detail, "ACI 318 side-face longitudinal reinforcement for h > 900 mm"),
                ("Skin Al for torsion", f"{skin['area_total']} mm2", "Counted only if enclosed and developed"),
                ("Top ldh / lap", f"{dev_top['ldh']} / {dev_top['lap']} mm", "Development lengths"),
                ("Bottom lap", f"{dev_bot['lap']} mm", "Development length"),
            ]
            
            btn_calc = QPushButton(f"Toggle Calculation Summary - {zone}")
            btn_calc.setStyleSheet("background-color: #1e2330; color: #e8eaf0; text-align: left; padding: 5px;")
            table_calc = QTableView()
            table_calc.setModel(PandasModel(pd.DataFrame(calc_data, columns=["Parameter", "Value", "Note"])))
            table_calc.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table_calc.verticalHeader().hide()
            table_calc.setFixedHeight(250)
            table_calc.setVisible(False)
            
            btn_calc.clicked.connect(lambda checked, t=table_calc: t.setVisible(not t.isVisible()))
            
            zone_col.addWidget(btn_calc)
            zone_col.addWidget(table_calc)
            
            stirrup_status = "OK" if shear_ok else "FAIL"
            stirrup_text = f"{n_legs}-DB{bar_v} @ {res_shear['final_s']} mm ({stirrup_status}, D/C: {dc_shear})"
            self.last_zone_results[zone] = {
                "Mu": round(Mu, 1),
                "M_combo": self.force_meta[zone]["M"],
                "phi_Mn": res_flex["phi_Mn"],
                "DC_flex": dc_flex,
                "Vu": round(Vu_design, 1),
                "V_combo": self.force_meta[zone]["V"],
                "Tu": round(Tu_design, 1),
                "T_combo": self.force_meta[zone]["T"],
                "DC_shear": dc_shear,
                "phi_Vn": res_shear["phi_Vn"],
                "stirrups": stirrup_text,
                "torsion_status": "Required" if res_shear["needs_torsion"] else "Below threshold",
                "Al_req": res_shear["Al_req"],
                "skin_Al": skin["area_total"],
                "skin_detail": f"{skin_layers} layers of {skin_qty}-{skin_name}",
                "eps_t": res_flex["eps_t"],
                "phi": res_flex["phi"],
                "strain_class": res_flex["strain_class"],
                "dev_top": dev_top["ldh"],
                "dev_top_lap": dev_top["lap"],
                "dev_bot": dev_bot["lap"],
            }
            self.last_zone_raw_results[zone] = {
                "flex": res_flex,
                "shear": res_shear,
                "skin": skin,
            }
            self.last_summary.append({
                "Zone": zone,
                "Mu (kNm)": round(Mu, 1),
                "phiMn (kNm)": res_flex["phi_Mn"],
                "Flexure D/C": dc_flex,
                "Vu (kN)": round(Vu_design, 1),
                "phiVn (kN)": res_shear["phi_Vn"],
                "Stirrups": stirrup_text,
                "Strain class": res_flex["strain_class"],
            })
            
            zones_layout.addLayout(zone_col)
            
        self.results_inner_layout.addLayout(zones_layout)
        
        if self.last_summary:
            df_sum = pd.DataFrame(self.last_summary)
            table = QTableView()
            model = PandasModel(df_sum)
            table.setModel(model)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setFixedHeight(120)
            self.results_inner_layout.addWidget(table)
            
            btn_pdf = QPushButton("Download PDF calculation report")
            btn_pdf.setObjectName("primaryButton")
            btn_pdf.clicked.connect(self.download_pdf)
            self.results_inner_layout.addWidget(btn_pdf)


        if switch_tab:
            self._unlock_and_populate_tabs()
            self.main_tabs.setCurrentIndex(1)
            
    def on_calc_dropdowns_changed(self, *args):
        group_name = self.calc_group_combo.currentText()
        zone = self.calc_zone_combo.currentText()
        
        if not group_name or not zone or not hasattr(self, 'last_zone_raw_results'):
            return
            
        # Ensure we have the raw results for the selected group
        # If it doesn't match active group, we temporarily calculate it
        if group_name != self.app_state.get("group_name", self.selected_frame_label):
            prev_group = self.active_group_id
            prev_forces = {z: dict(v) for z, v in self.forces.items()}
            prev_meta = {z: dict(v) for z, v in self.force_meta.items()}
            
            self.app_state = self.groups[group_name]
            if "_forces" in self.app_state:
                self.forces = self.app_state["_forces"]
                self.force_meta = self.app_state["_force_meta"]
            self.update_forces_from_state()
            self.run_design(switch_tab=False)
            
            self.app_state = self.groups[prev_group]
            self.forces = prev_forces
            self.force_meta = prev_meta
            self.update_forces_from_state()

        if zone in self.last_zone_raw_results:
            raw = self.last_zone_raw_results[zone]
            html = generate_calculation_html(
                zone, 
                self.groups[group_name], 
                self.groups[group_name].get("_forces", self.forces)[zone], 
                raw["flex"], 
                raw["shear"], 
                raw["skin"]
            )
            self.calc_browser.setHtml(html)

    def download_pdf(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", f"Beam_{safe_filename(self.selected_frame_label)}_Report.pdf", "PDF Files (*.pdf)")
        if fname:
            try:
                group_data = {
                    "group_name": self.app_state.get("group_name", self.selected_frame_label),
                    "b": self.app_state.get("b", 300),
                    "h": self.app_state.get("h", 600),
                    "fc": self.app_state.get("fc", 35),
                    "fy": self.app_state.get("fy", 500),
                    "fyt": self.app_state.get("fyt", 400),
                    "zone_data": self.last_zone_results.copy()
                }
                pdf_bytes = create_pdf_report([group_data], self.app_state.get("input_mode"))
                with open(fname, 'wb') as f:
                    f.write(pdf_bytes)
                QMessageBox.information(self, "Success", "PDF Report saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save PDF: {e}")
