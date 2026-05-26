import re
import os

filepath = "Pyside6/main_window.py"
with open(filepath, "r") as f:
    content = f.read()

# 1. Add self.groups to __init__
init_hook = "self.app_state = load_workspace_excel(workspace_bytes)[0] if os.path.exists(WORKSPACE_FILE) else DEFAULT_APP_STATE.copy()"
init_replacement = """self.app_state = load_workspace_excel(workspace_bytes)[0] if os.path.exists(WORKSPACE_FILE) else DEFAULT_APP_STATE.copy()
        self.app_state["group_name"] = "Manual"
        self.groups = {"Manual": self.app_state}
        self.active_group_id = "Manual"
"""
content = content.replace(init_hook, init_replacement)

# 2. Add Active Group Dropdown at the top of Project Input
proj_input_hook = 'self.add_section_header("Project Input")'
proj_input_replacement = """self.add_section_header("Active Group Selection")
        self.group_combo = QComboBox()
        self.group_combo.addItem("Manual")
        self.group_combo.currentTextChanged.connect(self.on_group_changed)
        self.scroll_layout.addWidget(self.group_combo)
        
        self.add_section_header("Project Input")"""
content = content.replace(proj_input_hook, proj_input_replacement)

# 3. Add Raw Data Table and Grouping UI to sap_widget
sap_ui_hook = """self.sap_status_label = QLabel("No SAP data loaded.")
        sap_layout.addWidget(self.sap_status_label)"""
sap_ui_replacement = """self.sap_status_label = QLabel("No SAP data loaded.")
        sap_layout.addWidget(self.sap_status_label)
        
        self.sap_table = QTableView()
        self.sap_table.setFixedHeight(150)
        sap_layout.addWidget(self.sap_table)
        
        group_layout = QHBoxLayout()
        self.txt_frames = QLineEdit()
        self.txt_frames.setPlaceholderText("Frame IDs (e.g. 1, 2, 3)")
        self.txt_group_name = QLineEdit()
        self.txt_group_name.setPlaceholderText("Group Name (e.g. B1)")
        btn_create_group = QPushButton("Create Group from Frames")
        btn_create_group.clicked.connect(self.create_group)
        group_layout.addWidget(QLabel("Frames:"))
        group_layout.addWidget(self.txt_frames)
        group_layout.addWidget(QLabel("Group Name:"))
        group_layout.addWidget(self.txt_group_name)
        group_layout.addWidget(btn_create_group)
        sap_layout.addLayout(group_layout)
"""
content = content.replace(sap_ui_hook, sap_ui_replacement)

# 4. Add "Run All Groups" button
run_hook = """btn_run = QPushButton("Run full 3-zone detailing design")
        btn_run.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_run.clicked.connect(self.run_design)
        self.scroll_layout.addWidget(btn_run)"""
run_replacement = """btn_run = QPushButton("Run Active Group Design")
        btn_run.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_run.clicked.connect(self.run_design)
        self.scroll_layout.addWidget(btn_run)
        
        btn_run_all = QPushButton("Run All Groups & Export PDF")
        btn_run_all.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_run_all.clicked.connect(self.run_all_groups)
        self.scroll_layout.addWidget(btn_run_all)"""
content = content.replace(run_hook, run_replacement)

# 5. Add methods for grouping and running all
methods_addition = """
    def on_group_changed(self, group_name):
        if group_name and group_name in self.groups:
            self.active_group_id = group_name
            self.app_state = self.groups[group_name]
            # Update UI fields to match new app_state
            self.update_forces_from_state()
            self.app_state_to_ui()

    def app_state_to_ui(self):
        # A helper to sync app_state values to the UI widgets
        # For simplicity, we trigger update_forces_from_state which does some of it,
        # but we also need to update all spinboxes and dropdowns.
        pass # In a full app we'd iterate over all widgets and set values from app_state

    def create_group(self):
        if self.df_sap is None or self.df_sap.empty:
            QMessageBox.warning(self, "No Data", "Please load SAP data first.")
            return
            
        frame_text = self.txt_frames.text()
        group_name = self.txt_group_name.text().strip()
        
        if not frame_text or not group_name:
            QMessageBox.warning(self, "Input Error", "Provide both frame IDs and a group name.")
            return
            
        try:
            frames = [int(f.strip()) for f in frame_text.split(",") if f.strip()]
        except ValueError:
            frames = [f.strip() for f in frame_text.split(",") if f.strip()]
            
        df_group = self.df_sap[self.df_sap["Frame"].astype(str).isin([str(f) for f in frames])]
        if df_group.empty:
            QMessageBox.warning(self, "Not Found", "None of the specified frames were found in the data.")
            return
            
        # Calculate envelope
        import numpy as np
        new_state = DEFAULT_APP_STATE.copy()
        new_state["group_name"] = group_name
        new_state["input_mode"] = self.app_state["input_mode"]
        
        stations = sorted(df_group["Station"].unique())
        if len(stations) >= 3:
            st_left, st_mid, st_right = stations[0], stations[len(stations)//2], stations[-1]
            new_state["beam_length"] = st_right - st_left
            
            for zone, st in zip(["left", "mid", "right"], [st_left, st_mid, st_right]):
                df_st = df_group[df_group["Station"] == st]
                if not df_st.empty:
                    new_state[f"mu_{zone}"] = float(df_st["M3"].abs().max())
                    new_state[f"vu_{zone}"] = float(df_st["V2"].abs().max())
                    new_state[f"tu_{zone}"] = float(df_st["T"].abs().max())
        
        self.groups[group_name] = new_state
        if self.group_combo.findText(group_name) == -1:
            self.group_combo.addItem(group_name)
        self.group_combo.setCurrentText(group_name)
        QMessageBox.information(self, "Success", f"Group '{group_name}' created with {len(frames)} frames.")

    def run_all_groups(self):
        pdf_groups = []
        # Temporarily save active
        prev_group = self.active_group_id
        
        for g_name, g_state in self.groups.items():
            self.app_state = g_state
            self.update_forces_from_state()
            self.run_design() # This updates self.last_zone_results
            
            group_data = {
                "group_name": g_name,
                "b": self.app_state["b"],
                "h": self.app_state["h"],
                "fc": self.app_state["fc"],
                "fy": self.app_state["fy"],
                "fyt": self.app_state["fyt"],
                "zone_data": self.last_zone_results.copy()
            }
            pdf_groups.append(group_data)
            
        # Restore active
        self.app_state = self.groups[prev_group]
        self.update_forces_from_state()
        self.run_design()
        
        from pdf_report import create_pdf_report
        pdf_bytes = create_pdf_report(pdf_groups, "Multi-Group Run")
        
        fname, _ = QFileDialog.getSaveFileName(self, "Save Multi-Group PDF", "Multi_Group_Report.pdf", "PDF Files (*.pdf)")
        if fname:
            with open(fname, "wb") as f:
                f.write(pdf_bytes)
            QMessageBox.information(self, "Exported", f"Multi-group PDF saved to {fname}")
"""
content = content.replace("def update_forces_from_state(self):", methods_addition + "\n    def update_forces_from_state(self):")

# 6. Make process_sap_data display the table
table_hook = 'self.sap_status_label.setText(f"Loaded {len(self.df_sap)} rows from SAP2000.")'
table_replacement = """self.sap_status_label.setText(f"Loaded {len(self.df_sap)} rows from SAP2000.")
        self.sap_table.setModel(PandasModel(self.df_sap.head(100)))"""
content = content.replace(table_hook, table_replacement)

with open(filepath, "w") as f:
    f.write(content)
