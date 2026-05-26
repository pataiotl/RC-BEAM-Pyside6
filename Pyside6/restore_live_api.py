import os

filepath = "Pyside6/main_window.py"
with open(filepath, "r") as f:
    content = f.read()

# 1. Imports
content = content.replace("from qt_models import PandasModel", "from qt_models import PandasModel\nfrom sap2000_api import get_selected_frames_forces")

# 2. Add rb_sap_live
old_rb = """        self.add_section_header("Force Input Source")
        self.rb_manual = QRadioButton("Manual Input")
        self.rb_sap = QRadioButton("SAP2000 CSV Upload")
        self.rb_manual.toggled.connect(self.on_input_mode_changed)
        
        rb_layout = QHBoxLayout()
        rb_layout.addWidget(self.rb_manual)
        rb_layout.addWidget(self.rb_sap)
        rb_layout.addStretch()
        self.scroll_layout.addLayout(rb_layout)"""

new_rb = """        self.add_section_header("Force Input Source")
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
        self.scroll_layout.addWidget(self.live_api_widget)"""

content = content.replace(old_rb, new_rb)

# 3. Handle input mode toggle
old_toggle = """        if self.app_state.get("input_mode") == "SAP2000 CSV Upload":
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
            self.update_forces_from_state()"""

new_toggle = """        if self.app_state.get("input_mode") == "SAP2000 CSV Upload":
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
            self.manual_widget.setVisible(False)
            self.process_sap_data()
        elif self.rb_sap_live.isChecked():
            self.app_state["input_mode"] = "SAP2000 Live API"
            self.sap_widget.setVisible(False)
            self.live_api_widget.setVisible(True)
            self.manual_widget.setVisible(False)
            self.process_sap_data()
        else:
            self.app_state["input_mode"] = "Manual Input"
            self.sap_widget.setVisible(False)
            self.live_api_widget.setVisible(False)
            self.manual_widget.setVisible(True)
            self.update_forces_from_state()"""

content = content.replace(old_toggle, new_toggle)

# 4. Add fetch_live_api_data
old_process = """    def process_sap_data(self):"""
new_process = """    def fetch_live_api_data(self):
        try:
            self.live_api_status_label.setText("Connecting to SAP2000...")
            df_raw = get_selected_frames_forces()
            self.app_state["sap_raw_json"] = df_raw.to_json(orient="split")
            self.live_api_status_label.setText(f"Success! Fetched forces for {len(df_raw['Frame'].unique())} frames.")
            self.process_sap_data()
        except Exception as e:
            self.live_api_status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(self, "API Error", str(e))

    def process_sap_data(self):"""
content = content.replace(old_process, new_process)

with open(filepath, "w") as f:
    f.write(content)
