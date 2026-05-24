import sys
import os
import json
import pandas as pd
from io import BytesIO

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QLabel, QPushButton, QRadioButton, QComboBox,
    QSpinBox, QDoubleSpinBox, QFileDialog, QTabWidget, QScrollArea,
    QGroupBox, QMessageBox, QTableView, QHeaderView
)
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QFont

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

# Import our custom modules
from engine import (
    ZONES, BAR_OPTIONS, STIRRUP_OPTIONS, SKIN_BAR_OPTIONS,
    calculate_beam_flexure, calculate_shear_torsion,
    calculate_development_length, calculate_skin_reinforcement, get_rebar_group
)
from plotting import draw_beam_section, draw_force_diagrams
from pdf_report import create_pdf_report
from utils import (
    DEFAULT_APP_STATE, load_workspace_excel, build_workspace_excel_bytes,
    governing_value_and_combo, safe_filename
)

class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            val = self._data.iloc[index.row(), index.column()]
            return str(val) if pd.notna(val) else ""
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])
            if orientation == Qt.Vertical:
                return str(self._data.index[section])
        return None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RC Beam Designer - PySide6")
        self.app_state = DEFAULT_APP_STATE.copy()
        self.inputs = {}
        self.forces = {zone: {"M": 0.0, "V": 0.0, "T": 0.0} for zone in ZONES}
        self.force_meta = {zone: {kind: "Manual input" for kind in ["M", "V", "T"]} for zone in ZONES}
        self.df_sap = None
        self.selected_frame_label = "Manual"
        
        self.init_ui()
        self.refresh_ui_from_state()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
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
        
        self.add_section_header("Force Input Source")
        self.rb_manual = QRadioButton("Manual Input")
        self.rb_sap = QRadioButton("SAP2000 CSV Upload")
        self.rb_manual.toggled.connect(self.on_input_mode_changed)
        
        rb_layout = QHBoxLayout()
        rb_layout.addWidget(self.rb_manual)
        rb_layout.addWidget(self.rb_sap)
        rb_layout.addStretch()
        self.scroll_layout.addLayout(rb_layout)
        
        # SAP input widget container
        self.sap_widget = QWidget()
        sap_layout = QVBoxLayout(self.sap_widget)
        btn_upload_sap = QPushButton("Upload SAP2000 CSV")
        btn_upload_sap.clicked.connect(self.upload_sap_csv)
        sap_layout.addWidget(btn_upload_sap)
        self.sap_status_label = QLabel("No SAP data loaded.")
        sap_layout.addWidget(self.sap_status_label)
        self.scroll_layout.addWidget(self.sap_widget)
        
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
        self.btn_run = QPushButton("Run full 3-zone detailing design")
        self.btn_run.setObjectName("primaryButton")
        self.btn_run.clicked.connect(self.run_design)
        self.scroll_layout.addWidget(self.btn_run)
        
        # Results Container
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_container.setVisible(False)
        self.scroll_layout.addWidget(self.results_container)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        self.setCentralWidget(main_widget)
        
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
        else:
            self.rb_manual.setChecked(True)
            
        self.update_forces_from_state()

    def on_input_mode_changed(self):
        if self.rb_sap.isChecked():
            self.app_state["input_mode"] = "SAP2000 CSV Upload"
            self.sap_widget.setVisible(True)
            self.manual_widget.setVisible(False)
            self.process_sap_data()
        else:
            self.app_state["input_mode"] = "Manual Input"
            self.sap_widget.setVisible(False)
            self.manual_widget.setVisible(True)
            self.update_forces_from_state()
            
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
                
            # For simplicity in PySide6, we just pick the first frame if grouping isn't fully built
            # In a full app, we'd add QComboBoxes to pick frames. We will auto-select the first for now.
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
                    
                self.df_sap = df
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

    def run_design(self):
        self.clear_layout(self.results_layout)
        self.results_container.setVisible(True)
        
        lbl = QLabel("Three-Zone Cross Sections and Calculations")
        lbl.setObjectName("sectionHeader")
        self.results_layout.addWidget(lbl)
        
        zones_layout = QHBoxLayout()
        self.last_zone_results = {}
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
            Vu = abs(self.forces[zone]["V"])
            Tu = abs(self.forces[zone]["T"])
            
            res_flex = calculate_beam_flexure(b, h, d, dt, d_prime, fc, fy, As_tens, As_comp)
            res_shear = calculate_shear_torsion(b, h, d, fc, fyt, fy, cover_clear, Vu, Tu, n_legs, bar_v, lambda_c, stirrup_spacing)
            skin = calculate_skin_reinforcement(h, d, skin_dia, skin_qty, skin_layers)
            
            top_bar_dia = BAR_OPTIONS[self.app_state.get(f"td1_{zone}", "DB25")]
            bot_bar_dia = BAR_OPTIONS[self.app_state.get(f"bd1_{zone}", "DB25")]
            dev_top = calculate_development_length(top_bar_dia, fy, fc, True, cover_clear, clear_space, lambda_c)
            dev_bot = calculate_development_length(bot_bar_dia, fy, fc, False, cover_clear, clear_space, lambda_c)
            
            dc_flex = round(Mu / res_flex["phi_Mn"], 2) if res_flex["phi_Mn"] > 0 else 999.9
            dc_pure_shear = Vu / res_shear["phi_Vn"] if res_shear.get("phi_Vn", 0) > 0 else 999.9
            dc_steel_force = res_shear.get("final_s", 0) / res_shear.get("s_calc", 9999) if res_shear.get("s_calc", 9999) > 0 else 0
            dc_shear = round(max(dc_pure_shear, dc_steel_force), 2)
            
            fig = draw_beam_section(b, h, cover_clear, bar_v, top_rg, bot_rg, res_flex, zone, skin, skin_dia, comp_face)
            canvas = FigureCanvas(fig)
            canvas.setFixedHeight(200)
            zone_col.addWidget(canvas)
            
            res_lbl = QLabel(f"<b>phi_Mn:</b> {res_flex['phi_Mn']} kNm (D/C: {dc_flex})<br>"
                             f"<b>phi_Vn:</b> {res_shear['phi_Vn']} kN (D/C: {round(dc_pure_shear,2)})<br>"
                             f"<b>Stirrups D/C:</b> {dc_shear}")
            zone_col.addWidget(res_lbl)
            
            stirrup_text = f"{n_legs}-DB{bar_v} @ {res_shear['final_s']} mm"
            self.last_zone_results[zone] = {
                "Mu": round(Mu, 1),
                "M_combo": self.force_meta[zone]["M"],
                "phi_Mn": res_flex["phi_Mn"],
                "DC_flex": dc_flex,
                "Vu": round(Vu, 1),
                "V_combo": self.force_meta[zone]["V"],
                "Tu": round(Tu, 1),
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
            self.last_summary.append({
                "Zone": zone,
                "Mu (kNm)": round(Mu, 1),
                "phiMn (kNm)": res_flex["phi_Mn"],
                "Flexure D/C": dc_flex,
                "Vu (kN)": round(Vu, 1),
                "phiVn (kN)": res_shear["phi_Vn"],
                "Stirrups": stirrup_text,
                "Strain class": res_flex["strain_class"],
            })
            
            zones_layout.addLayout(zone_col)
            
        self.results_layout.addLayout(zones_layout)
        
        if self.last_summary:
            df_sum = pd.DataFrame(self.last_summary)
            table = QTableView()
            model = PandasModel(df_sum)
            table.setModel(model)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setFixedHeight(120)
            self.results_layout.addWidget(table)
            
            btn_pdf = QPushButton("Download PDF calculation report")
            btn_pdf.setObjectName("primaryButton")
            btn_pdf.clicked.connect(self.download_pdf)
            self.results_layout.addWidget(btn_pdf)

    def download_pdf(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", f"Beam_{safe_filename(self.selected_frame_label)}_Report.pdf", "PDF Files (*.pdf)")
        if fname:
            try:
                b = self.app_state.get("b", 300)
                h = self.app_state.get("h", 600)
                fc = self.app_state.get("fc", 35)
                fy = self.app_state.get("fy", 500)
                fyt = self.app_state.get("fyt", 400)
                pdf_bytes = create_pdf_report(b, h, fc, fy, fyt, self.selected_frame_label, self.last_zone_results, self.app_state.get("input_mode"))
                with open(fname, 'wb') as f:
                    f.write(pdf_bytes)
                QMessageBox.information(self, "Success", "PDF Report saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save PDF: {e}")
