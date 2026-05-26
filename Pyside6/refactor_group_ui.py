import os

filepath = "Pyside6/main_window.py"
with open(filepath, "r") as f:
    content = f.read()

# 1. Update the layout in __init__
old_layout = """        group_layout = QHBoxLayout()
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
        sap_data_layout.addLayout(group_layout)"""

new_layout = """        group_layout1 = QHBoxLayout()
        self.cb_frames = QComboBox()
        btn_add_frame = QPushButton("Add")
        btn_add_frame.clicked.connect(self.add_frame_to_selection)
        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(self.select_all_frames)
        btn_clear = QPushButton("Remove All")
        btn_clear.clicked.connect(self.clear_frames)
        group_layout1.addWidget(QLabel("Available Frames:"))
        group_layout1.addWidget(self.cb_frames, 1)
        group_layout1.addWidget(btn_add_frame)
        group_layout1.addWidget(btn_select_all)
        group_layout1.addWidget(btn_clear)
        
        group_layout2 = QHBoxLayout()
        self.txt_frames = QLineEdit()
        self.txt_frames.setPlaceholderText("Selected Frames")
        self.txt_group_name = QLineEdit()
        self.txt_group_name.setPlaceholderText("Group Name (e.g. B1)")
        btn_create_group = QPushButton("Create Group")
        btn_create_group.clicked.connect(self.create_group)
        
        group_layout2.addWidget(QLabel("Selected:"))
        group_layout2.addWidget(self.txt_frames, 1)
        group_layout2.addWidget(QLabel("Group Name:"))
        group_layout2.addWidget(self.txt_group_name, 1)
        group_layout2.addWidget(btn_create_group)
        
        sap_data_layout.addLayout(group_layout1)
        sap_data_layout.addLayout(group_layout2)"""

content = content.replace(old_layout, new_layout)

# 2. Add the unique frames populate logic
process_sap_data_end = """self.sap_table.setModel(PandasModel(self.df_sap.head(100)))"""
process_sap_data_new = """self.sap_table.setModel(PandasModel(self.df_sap.head(100)))
            
            # Populate combobox
            unique_frames = self.df_sap["Frame"].unique()
            self.cb_frames.clear()
            self.cb_frames.addItems([str(f) for f in unique_frames])"""

content = content.replace(process_sap_data_end, process_sap_data_new)

# 3. Add the helper methods
methods = """
    def add_frame_to_selection(self):
        frame = self.cb_frames.currentText()
        if not frame: return
        current = self.txt_frames.text().strip()
        if current:
            existing = [f.strip() for f in current.split(",")]
            if frame not in existing:
                self.txt_frames.setText(current + f", {frame}")
        else:
            self.txt_frames.setText(frame)
            
    def select_all_frames(self):
        if self.df_sap is not None and not self.df_sap.empty:
            unique_frames = self.df_sap["Frame"].unique()
            self.txt_frames.setText(", ".join([str(f) for f in unique_frames]))
            
    def clear_frames(self):
        self.txt_frames.clear()

"""
content = content.replace("    def create_group(self):", methods + "    def create_group(self):")

with open(filepath, "w") as f:
    f.write(content)
