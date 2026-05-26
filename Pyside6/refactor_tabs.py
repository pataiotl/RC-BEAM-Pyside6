import re
import os

filepath = "Pyside6/main_window.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Modify init_ui to use a QTabWidget as central widget
new_init = """    def init_ui(self):
        self.main_tabs = QTabWidget()
        self.setCentralWidget(self.main_tabs)
        
        # ----------------- INPUT TAB -----------------
        input_tab = QWidget()
        input_layout = QVBoxLayout(input_tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)"""

content = re.sub(r'    def init_ui\(self\):\n        main_widget = QWidget\(\)\n        main_layout = QVBoxLayout\(main_widget\)\n        \n        scroll = QScrollArea\(\)\n        scroll\.setWidgetResizable\(True\)\n        scroll_content = QWidget\(\)\n        self\.scroll_layout = QVBoxLayout\(scroll_content\)', new_init, content)

# 2. Update Run Design area in Input Tab
new_run_design = """        # Run Design
        run_layout = QHBoxLayout()
        self.btn_run = QPushButton("Design Active Group")
        self.btn_run.setObjectName("primaryButton")
        self.btn_run.clicked.connect(self.run_design)
        run_layout.addWidget(self.btn_run)
        
        self.btn_run_all = QPushButton("Design All Groups")
        self.btn_run_all.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_run_all.clicked.connect(self.run_all_groups_design)
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
        
        # Hide tabs initially
        self.main_tabs.setTabVisible(1, False)
        self.main_tabs.setTabVisible(2, False)
        
        self.rb_manual.setChecked(True)"""

old_run_design = """        # Run Design
        run_layout = QHBoxLayout()
        self.btn_run = QPushButton("Design Active Group")
        self.btn_run.setObjectName("primaryButton")
        self.btn_run.clicked.connect(self.run_design)
        run_layout.addWidget(self.btn_run)
        
        self.btn_run_all = QPushButton("Design All Groups")
        self.btn_run_all.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_run_all.clicked.connect(self.run_all_groups_design)
        run_layout.addWidget(self.btn_run_all)
        
        self.btn_export_pdf = QPushButton("Export All Groups PDF")
        self.btn_export_pdf.setStyleSheet("background-color: #7c3aed; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_export_pdf.clicked.connect(self.export_all_groups_pdf)
        run_layout.addWidget(self.btn_export_pdf)
        
        self.scroll_layout.addLayout(run_layout)
        
        # Results Container
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_container.setVisible(False)
        self.scroll_layout.addWidget(self.results_container)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        self.setCentralWidget(main_widget)
        
        self.rb_manual.setChecked(True)"""

content = content.replace(old_run_design, new_run_design)

# 3. Replace results display logic in render_results
content = content.replace("self.results_layout.addWidget", "self.results_inner_layout.addWidget")
content = content.replace("clear_layout(self.results_layout)", "clear_layout(self.results_inner_layout)")
content = content.replace("self.results_container.setVisible(True)", "")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
