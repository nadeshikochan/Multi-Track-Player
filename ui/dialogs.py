"""
设置对话框
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QComboBox, QSpinBox, QTabWidget,
    QWidget, QFileDialog, QCheckBox, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtGui import QFont


class SettingsDialog(QDialog):
    """基本设置对话框"""
    
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        self.setWindowTitle("设置")
        self.setFixedSize(600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a24; }
            QLabel { color: #e0e0e0; }
            QLineEdit { 
                background: #2a2a3a; border: 2px solid #3a3a4a; 
                border-radius: 8px; padding: 10px; color: #e0e0e0; 
            }
            QLineEdit:focus { border-color: #7c5ce0; }
            QPushButton { 
                background: #7c5ce0; color: white; 
                border: none; border-radius: 8px; 
                padding: 10px 20px; font-weight: bold; 
            }
            QPushButton:hover { background: #9c7cf0; }
            QPushButton#browseBtn { background: #4a4a5e; }
            QGroupBox { 
                color: #a0a0a0; border: 1px solid #3a3a4a; 
                border-radius: 8px; margin-top: 12px; 
            }
            QTabWidget::pane { border: 1px solid #3a3a4a; border-radius: 8px; }
            QTabBar::tab { 
                background: #2a2a3a; color: #a0a0a0; 
                padding: 10px 20px; border-radius: 8px 8px 0 0; 
            }
            QTabBar::tab:selected { background: #3a3a4a; color: #ffffff; }
            QSpinBox, QCheckBox { color: #e0e0e0; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        tabs = QTabWidget()
        basic_tab = self._create_basic_tab()
        tabs.addTab(basic_tab, "📁 基本设置")
        api_tab = self._create_api_tab()
        tabs.addTab(api_tab, "🌐 API设置")
        layout.addWidget(tabs)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("browseBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
    def _create_basic_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        
        music_group = QGroupBox("单曲文件夹 (原始歌曲)")
        music_layout = QHBoxLayout(music_group)
        self.music_path_edit = QLineEdit(self.config.get('music_path', ''))
        music_layout.addWidget(self.music_path_edit)
        browse_music = QPushButton("浏览...")
        browse_music.setObjectName("browseBtn")
        browse_music.clicked.connect(lambda: self._browse_folder(self.music_path_edit))
        music_layout.addWidget(browse_music)
        layout.addWidget(music_group)
        
        stems_group = QGroupBox("多音轨文件夹 (分离后)")
        stems_layout = QHBoxLayout(stems_group)
        self.stems_path_edit = QLineEdit(self.config.get('stems_path', ''))
        stems_layout.addWidget(self.stems_path_edit)
        browse_stems = QPushButton("浏览...")
        browse_stems.setObjectName("browseBtn")
        browse_stems.clicked.connect(lambda: self._browse_folder(self.stems_path_edit))
        stems_layout.addWidget(browse_stems)
        layout.addWidget(stems_group)
        
        layout.addStretch()
        return widget
        
    def _create_api_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        
        rec_group = QGroupBox("歌曲推荐API服务器")
        rec_layout = QHBoxLayout(rec_group)
        rec_layout.addWidget(QLabel("端口:"))
        self.rec_port_spin = QSpinBox()
        self.rec_port_spin.setRange(1024, 65535)
        self.rec_port_spin.setValue(self.config.get('recommendation_port', 23331))
        self.rec_port_spin.setStyleSheet("background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 8px; padding: 8px;")
        rec_layout.addWidget(self.rec_port_spin)
        self.rec_enabled = QCheckBox("启用")
        self.rec_enabled.setChecked(self.config.get('recommendation_enabled', True))
        rec_layout.addWidget(self.rec_enabled)
        rec_layout.addStretch()
        layout.addWidget(rec_group)
        
        # 推荐系统设置
        rec_settings_group = QGroupBox("推荐系统设置")
        rec_settings_layout = QVBoxLayout(rec_settings_group)
        
        pool_layout = QHBoxLayout()
        pool_layout.addWidget(QLabel("随机推荐池大小:"))
        self.rec_pool_spin = QSpinBox()
        self.rec_pool_spin.setRange(5, 100)
        self.rec_pool_spin.setValue(self.config.get('recommendation_pool_size', 20))
        self.rec_pool_spin.setStyleSheet("background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 8px; padding: 8px;")
        self.rec_pool_spin.setToolTip("从推荐排名前N首中随机选择下一首播放，避免总是播放同一首")
        pool_layout.addWidget(self.rec_pool_spin)
        pool_layout.addStretch()
        rec_settings_layout.addLayout(pool_layout)
        
        pool_note = QLabel("💡 值越大，播放越随机；值越小，越接近推荐排名第一的歌曲")
        pool_note.setStyleSheet("color: #808080; font-size: 11px;")
        rec_settings_layout.addWidget(pool_note)
        
        layout.addWidget(rec_settings_group)
        
        # 音源说明
        source_group = QGroupBox("在线音乐")
        source_layout = QVBoxLayout(source_group)
        
        note = QLabel("💡 在线音乐功能使用导入的音源脚本\n\n"
                      "请点击主界面的「📦 音源管理」按钮导入音源脚本文件(.js)\n\n"
                      "支持的音源类型:\n"
                      "• 新澜音源 (支持酷我、酷狗、QQ、网易云、咪咕)\n"
                      "• LX Music 自定义音源\n"
                      "• 其他兼容音源脚本")
        note.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        note.setWordWrap(True)
        source_layout.addWidget(note)
        layout.addWidget(source_group)
        
        layout.addStretch()
        return widget
        
    def _browse_folder(self, edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", edit.text())
        if folder:
            edit.setText(folder)
            
    def get_config(self) -> dict:
        self.config['music_path'] = self.music_path_edit.text()
        self.config['stems_path'] = self.stems_path_edit.text()
        self.config['recommendation_port'] = self.rec_port_spin.value()
        self.config['recommendation_enabled'] = self.rec_enabled.isChecked()
        self.config['recommendation_pool_size'] = self.rec_pool_spin.value()
        return self.config


class MSSTDialog(QDialog):
    """MSST音轨分离设置对话框"""
    
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        self.setWindowTitle("MSST 音轨分离设置")
        self.setFixedSize(750, 700)
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a24; }
            QLabel { color: #e0e0e0; font-size: 13px; }
            QLineEdit, QComboBox { background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 8px; padding: 10px; color: #e0e0e0; }
            QLineEdit:focus, QComboBox:focus { border-color: #7c5ce0; }
            QPushButton { background: #7c5ce0; color: white; border: none; border-radius: 8px; padding: 10px 20px; font-weight: bold; }
            QPushButton:hover { background: #9c7cf0; }
            QPushButton#browseBtn { background: #4a4a5e; }
            QPushButton#checkBtn { background: #2d8a4e; }
            QGroupBox { color: #a0a0a0; border: 1px solid #3a3a4a; border-radius: 8px; margin-top: 12px; padding-top: 8px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # MSST路径
        msst_group = QGroupBox("MSST WebUI 安装路径")
        msst_layout = QHBoxLayout(msst_group)
        self.msst_path_edit = QLineEdit(self.config.get('msst_path', ''))
        self.msst_path_edit.setPlaceholderText("例如: D:\\MSST-WebUI")
        msst_layout.addWidget(self.msst_path_edit)
        browse_msst = QPushButton("浏览...")
        browse_msst.setObjectName("browseBtn")
        browse_msst.clicked.connect(lambda: self._browse_folder(self.msst_path_edit))
        msst_layout.addWidget(browse_msst)
        layout.addWidget(msst_group)
        
        # Python路径（重要！MSST通常使用自己的Python环境）
        python_group = QGroupBox("Python解释器路径 (MSST的虚拟环境)")
        python_layout = QVBoxLayout(python_group)
        python_input_layout = QHBoxLayout()
        self.python_path_edit = QLineEdit(self.config.get('msst_python_path', ''))
        self.python_path_edit.setPlaceholderText("例如: D:\\MSST-WebUI\\venv\\Scripts\\python.exe")
        python_input_layout.addWidget(self.python_path_edit)
        browse_python = QPushButton("浏览...")
        browse_python.setObjectName("browseBtn")
        browse_python.clicked.connect(self._browse_python)
        python_input_layout.addWidget(browse_python)
        python_layout.addLayout(python_input_layout)
        python_note = QLabel("⚠️ 重要: 必须指定MSST使用的Python解释器(安装了torch的环境)")
        python_note.setStyleSheet("color: #f0a050; font-size: 11px;")
        python_layout.addWidget(python_note)
        layout.addWidget(python_group)
        
        # 检查按钮
        check_btn = QPushButton("🔍 检查MSST环境")
        check_btn.setObjectName("checkBtn")
        check_btn.clicked.connect(self._check_msst_environment)
        layout.addWidget(check_btn)
        
        self.check_result = QLabel("")
        self.check_result.setStyleSheet("color: #808080; font-size: 11px;")
        self.check_result.setWordWrap(True)
        layout.addWidget(self.check_result)
        
        # 输出路径
        output_group = QGroupBox("分离音轨保存路径")
        output_layout = QHBoxLayout(output_group)
        self.stems_path_edit = QLineEdit(self.config.get('stems_path', ''))
        output_layout.addWidget(self.stems_path_edit)
        browse_output = QPushButton("浏览...")
        browse_output.setObjectName("browseBtn")
        browse_output.clicked.connect(lambda: self._browse_folder(self.stems_path_edit))
        output_layout.addWidget(browse_output)
        layout.addWidget(output_group)
        
        # 模型类型
        model_type_group = QGroupBox("模型类型")
        model_type_layout = QHBoxLayout(model_type_group)
        self.model_type_combo = QComboBox()
        self.model_type_combo.addItems(["bs_roformer", "mel_band_roformer", "htdemucs", "mdx23c", "segm_models", "scnet", "single_stem_models"])
        self.model_type_combo.setCurrentText(self.config.get('model_type', 'bs_roformer'))
        model_type_layout.addWidget(self.model_type_combo)
        layout.addWidget(model_type_group)
        
        # 配置文件
        config_group = QGroupBox("模型配置文件 (*.yaml)")
        config_layout = QHBoxLayout(config_group)
        self.config_path_edit = QLineEdit(self.config.get('config_path', ''))
        config_layout.addWidget(self.config_path_edit)
        browse_config = QPushButton("浏览...")
        browse_config.setObjectName("browseBtn")
        browse_config.clicked.connect(self._browse_config)
        config_layout.addWidget(browse_config)
        layout.addWidget(config_group)
        
        # 模型文件
        model_group = QGroupBox("模型权重文件 (*.ckpt / *.th)")
        model_layout = QHBoxLayout(model_group)
        self.model_path_edit = QLineEdit(self.config.get('model_path', ''))
        model_layout.addWidget(self.model_path_edit)
        browse_model = QPushButton("浏览...")
        browse_model.setObjectName("browseBtn")
        browse_model.clicked.connect(self._browse_model)
        model_layout.addWidget(browse_model)
        layout.addWidget(model_group)
        
        # 输出格式
        format_group = QGroupBox("输出格式")
        format_layout = QHBoxLayout(format_group)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["wav", "flac", "mp3"])
        self.format_combo.setCurrentText(self.config.get('output_format', 'wav'))
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        layout.addWidget(format_group)
        
        # 压缩设置
        compress_group = QGroupBox("音轨压缩设置 (分离后自动压缩)")
        compress_layout = QVBoxLayout(compress_group)
        
        # 启用压缩
        self.compress_enabled = QCheckBox("分离后自动压缩音轨 (约1:10压缩比)")
        self.compress_enabled.setChecked(self.config.get('compress_stems', True))
        compress_layout.addWidget(self.compress_enabled)
        
        compress_options_layout = QHBoxLayout()
        
        # 压缩格式
        compress_options_layout.addWidget(QLabel("压缩格式:"))
        self.compress_format_combo = QComboBox()
        self.compress_format_combo.addItems(["m4a", "ogg", "opus", "mp3"])
        self.compress_format_combo.setCurrentText(self.config.get('compress_format', 'm4a'))
        self.compress_format_combo.setToolTip("m4a: 兼容性最好\nogg: 开源格式\nopus: 压缩效率最高\nmp3: 通用格式")
        compress_options_layout.addWidget(self.compress_format_combo)
        
        compress_options_layout.addSpacing(20)
        
        # 压缩比特率
        compress_options_layout.addWidget(QLabel("比特率:"))
        self.compress_bitrate_combo = QComboBox()
        self.compress_bitrate_combo.addItems(["48k", "64k", "96k", "128k"])
        self.compress_bitrate_combo.setCurrentText(self.config.get('compress_bitrate', '64k'))
        self.compress_bitrate_combo.setToolTip("64k: 推荐，平衡音质和大小\n48k: 更小文件，适合人声\n96k: 更高音质\n128k: 接近原始音质")
        compress_options_layout.addWidget(self.compress_bitrate_combo)
        
        compress_options_layout.addStretch()
        compress_layout.addLayout(compress_options_layout)
        
        compress_note = QLabel("💡 压缩需要安装FFmpeg。WAV/FLAC文件将被压缩，原始文件会被删除。")
        compress_note.setStyleSheet("color: #808080; font-size: 11px;")
        compress_layout.addWidget(compress_note)
        
        layout.addWidget(compress_group)
        
        note = QLabel("💡 提示: 配置文件和模型文件可以从MSST的configs和pretrain目录中选择")
        note.setStyleSheet("color: #808080; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("browseBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
    def _browse_folder(self, edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", edit.text())
        if folder:
            edit.setText(folder)
            
    def _browse_python(self):
        """浏览Python解释器"""
        msst_path = self.msst_path_edit.text()
        # 尝试找到可能的venv目录
        if msst_path:
            venv_path = os.path.join(msst_path, "venv", "Scripts")
            if os.path.exists(venv_path):
                start_dir = venv_path
            else:
                start_dir = msst_path
        else:
            start_dir = ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Python解释器", start_dir, 
            "Python解释器 (python.exe python);;所有文件 (*)"
        )
        if file_path:
            self.python_path_edit.setText(file_path)
            
    def _browse_config(self):
        msst_path = self.msst_path_edit.text()
        start_dir = os.path.join(msst_path, "configs") if msst_path else ""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择配置文件", start_dir, "YAML文件 (*.yaml)")
        if file_path:
            self.config_path_edit.setText(file_path)
            
    def _browse_model(self):
        msst_path = self.msst_path_edit.text()
        start_dir = os.path.join(msst_path, "pretrain") if msst_path else ""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", start_dir, "模型文件 (*.ckpt *.th)")
        if file_path:
            self.model_path_edit.setText(file_path)
            
    def _check_msst_environment(self):
        msst_path = self.msst_path_edit.text()
        python_path = self.python_path_edit.text()
        
        if not msst_path:
            self.check_result.setText("❌ 请先设置MSST路径")
            self.check_result.setStyleSheet("color: #e05050;")
            return
        if not os.path.exists(msst_path):
            self.check_result.setText(f"❌ MSST路径不存在: {msst_path}")
            self.check_result.setStyleSheet("color: #e05050;")
            return
            
        required = ["inference", "configs", "pretrain"]
        missing = [d for d in required if not os.path.exists(os.path.join(msst_path, d))]
        if missing:
            self.check_result.setText(f"❌ 缺少目录: {', '.join(missing)}")
            self.check_result.setStyleSheet("color: #e05050;")
            return
            
        infer_file = os.path.join(msst_path, "inference", "msst_infer.py")
        if not os.path.exists(infer_file):
            self.check_result.setText("❌ 找不到 inference/msst_infer.py")
            self.check_result.setStyleSheet("color: #e05050;")
            return
            
        # 检查Python解释器
        if not python_path:
            self.check_result.setText("⚠️ MSST目录结构正确，但未设置Python解释器路径\n\n请设置MSST使用的Python解释器(venv/Scripts/python.exe)")
            self.check_result.setStyleSheet("color: #f0a050;")
            return
            
        if not os.path.exists(python_path):
            self.check_result.setText(f"❌ Python解释器不存在: {python_path}")
            self.check_result.setStyleSheet("color: #e05050;")
            return
            
        self.check_result.setText("✅ MSST环境检查通过!\n\nPython解释器: " + python_path)
        self.check_result.setStyleSheet("color: #50e050;")
            
    def get_config(self) -> dict:
        return {
            'msst_path': self.msst_path_edit.text(),
            'msst_python_path': self.python_path_edit.text(),
            'stems_path': self.stems_path_edit.text(),
            'model_type': self.model_type_combo.currentText(),
            'config_path': self.config_path_edit.text(),
            'model_path': self.model_path_edit.text(),
            'output_format': self.format_combo.currentText(),
            'compress_stems': self.compress_enabled.isChecked(),
            'compress_format': self.compress_format_combo.currentText(),
            'compress_bitrate': self.compress_bitrate_combo.currentText()
        }


class OnlineSearchDialog(QDialog):
    """在线音乐搜索对话框"""
    
    def __init__(self, lx_client, parent=None):
        super().__init__(parent)
        self.lx_client = lx_client
        self.selected_song = None
        self.search_results = []
        self.setWindowTitle("在线音乐搜索")
        self.setFixedSize(900, 650)
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a24; }
            QLabel { color: #e0e0e0; }
            QLineEdit { background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 8px; padding: 10px; color: #e0e0e0; }
            QPushButton { background: #7c5ce0; color: white; border: none; border-radius: 8px; padding: 10px 20px; font-weight: bold; }
            QPushButton:hover { background: #9c7cf0; }
            QComboBox { background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 8px; padding: 8px; color: #e0e0e0; }
            QTableWidget { background: #1a1a24; border: none; gridline-color: #3a3a4a; color: #e0e0e0; }
            QTableWidget::item:selected { background: #7c5ce0; }
            QHeaderView::section { background: #2a2a3a; color: #a0a0a0; padding: 8px; border: none; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入歌曲名或歌手名...")
        self.search_edit.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_edit, 1)
        
        self.source_combo = QComboBox()
        self.source_combo.addItems(["酷我音乐", "酷狗音乐", "QQ音乐", "网易云音乐", "咪咕音乐"])
        self.source_combo.setFixedWidth(120)
        search_layout.addWidget(self.source_combo)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["320k", "128k", "flac", "flac24bit", "hires"])
        self.quality_combo.setFixedWidth(100)
        self.quality_combo.setToolTip("选择音质")
        search_layout.addWidget(self.quality_combo)
        
        search_btn = QPushButton("🔍 搜索")
        search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["歌曲名", "歌手", "专辑", "时长"])
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.result_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.result_table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.result_table)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #808080;")
        layout.addWidget(self.status_label)
        
        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background: #4a4a5e;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        play_btn = QPushButton("▶ 播放选中")
        play_btn.clicked.connect(self._on_play)
        btn_layout.addWidget(play_btn)
        layout.addLayout(btn_layout)
        
    def _get_source_code(self) -> str:
        sources = {'酷我音乐': 'kw', '酷狗音乐': 'kg', 'QQ音乐': 'tx', '网易云音乐': 'wy', '咪咕音乐': 'mg'}
        return sources.get(self.source_combo.currentText(), 'kw')
        
    def _do_search(self):
        keyword = self.search_edit.text().strip()
        if not keyword:
            return
        self.status_label.setText("搜索中...")
        self.result_table.setRowCount(0)
        source = self._get_source_code()
        self.search_results = self.lx_client.search(keyword, source)
        if not self.search_results:
            self.status_label.setText("未找到结果")
            return
        self.result_table.setRowCount(len(self.search_results))
        for i, song in enumerate(self.search_results):
            self.result_table.setItem(i, 0, QTableWidgetItem(song.name))
            self.result_table.setItem(i, 1, QTableWidgetItem(song.artist))
            self.result_table.setItem(i, 2, QTableWidgetItem(song.album))
            mins = int(song.duration // 60)
            secs = int(song.duration % 60)
            self.result_table.setItem(i, 3, QTableWidgetItem(f"{mins}:{secs:02d}"))
        self.status_label.setText(f"找到 {len(self.search_results)} 首歌曲")
        
    def _on_double_click(self):
        self._on_play()
        
    def _on_play(self):
        row = self.result_table.currentRow()
        if 0 <= row < len(self.search_results):
            self.selected_song = self.search_results[row]
            self.selected_song.quality = self.quality_combo.currentText()
            self.accept()
            
    def get_selected_song(self):
        return self.selected_song
    
    def get_selected_quality(self) -> str:
        return self.quality_combo.currentText()


class CustomSourceDialog(QDialog):
    """自定义音源管理对话框"""
    
    def __init__(self, source_manager, parent=None):
        super().__init__(parent)
        self.source_manager = source_manager
        self.setWindowTitle("自定义音源管理")
        self.setFixedSize(700, 550)
        self.setup_ui()
        self.refresh_source_list()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a24; }
            QLabel { color: #e0e0e0; }
            QLineEdit { background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 8px; padding: 10px; color: #e0e0e0; }
            QLineEdit:focus { border-color: #7c5ce0; }
            QPushButton { background: #7c5ce0; color: white; border: none; border-radius: 8px; padding: 10px 20px; font-weight: bold; }
            QPushButton:hover { background: #9c7cf0; }
            QPushButton#secondaryBtn { background: #4a4a5e; }
            QPushButton#dangerBtn { background: #e05050; }
            QTableWidget { background: #1a1a24; border: none; gridline-color: #3a3a4a; color: #e0e0e0; }
            QTableWidget::item:selected { background: #7c5ce0; }
            QHeaderView::section { background: #2a2a3a; color: #a0a0a0; padding: 8px; border: none; }
            QGroupBox { color: #a0a0a0; border: 1px solid #3a3a4a; border-radius: 8px; margin-top: 12px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 标题
        title = QLabel("🎵 自定义音源管理")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)
        
        desc = QLabel("导入和管理自定义音源，类似洛雪音乐的音源机制")
        desc.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(desc)
        
        # 导入区域
        import_group = QGroupBox("导入音源")
        import_layout = QVBoxLayout(import_group)
        
        # 本地导入
        local_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择本地音源脚本文件 (.js)")
        local_layout.addWidget(self.file_path_edit)
        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.clicked.connect(self._browse_source_file)
        local_layout.addWidget(browse_btn)
        import_local_btn = QPushButton("本地导入")
        import_local_btn.clicked.connect(self._import_from_file)
        local_layout.addWidget(import_local_btn)
        import_layout.addLayout(local_layout)
        
        # 在线导入
        online_layout = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("输入音源脚本URL")
        online_layout.addWidget(self.url_edit)
        import_url_btn = QPushButton("在线导入")
        import_url_btn.clicked.connect(self._import_from_url)
        online_layout.addWidget(import_url_btn)
        import_layout.addLayout(online_layout)
        
        layout.addWidget(import_group)
        
        # 音源列表
        list_label = QLabel("已安装的音源:")
        list_label.setStyleSheet("color: #a0a0a0; margin-top: 8px;")
        layout.addWidget(list_label)
        
        self.source_table = QTableWidget()
        self.source_table.setColumnCount(5)
        self.source_table.setHorizontalHeaderLabels(["名称", "版本", "作者", "描述", "状态"])
        self.source_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.source_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.source_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.source_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.source_table)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        
        activate_btn = QPushButton("✓ 设为活动音源")
        activate_btn.clicked.connect(self._activate_source)
        action_layout.addWidget(activate_btn)
        
        config_btn = QPushButton("⚙ 配置API")
        config_btn.setObjectName("secondaryBtn")
        config_btn.clicked.connect(self._configure_api)
        action_layout.addWidget(config_btn)
        
        remove_btn = QPushButton("🗑 删除")
        remove_btn.setObjectName("dangerBtn")
        remove_btn.clicked.connect(self._remove_source)
        action_layout.addWidget(remove_btn)
        
        action_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self.refresh_source_list)
        action_layout.addWidget(refresh_btn)
        
        layout.addLayout(action_layout)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
    def _browse_source_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择音源脚本", "", 
            "JavaScript文件 (*.js);;所有文件 (*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            
    def _import_from_file(self):
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "提示", "请先选择音源脚本文件")
            return
            
        success, message, _ = self.source_manager.import_source_from_file(file_path)
        if success:
            QMessageBox.information(self, "导入成功", message)
            self.file_path_edit.clear()
            self.refresh_source_list()
        else:
            QMessageBox.warning(self, "导入失败", message)
            
    def _import_from_url(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入音源脚本URL")
            return
            
        success, message, _ = self.source_manager.import_source_from_url(url)
        if success:
            QMessageBox.information(self, "导入成功", message)
            self.url_edit.clear()
            self.refresh_source_list()
        else:
            QMessageBox.warning(self, "导入失败", message)
            
    def refresh_source_list(self):
        """刷新音源列表"""
        self.source_manager.scan_sources_dir()
        sources = self.source_manager.get_all_sources()
        active = self.source_manager.get_active_source()
        
        self.source_table.setRowCount(len(sources))
        for i, source in enumerate(sources):
            self.source_table.setItem(i, 0, QTableWidgetItem(source.name))
            self.source_table.setItem(i, 1, QTableWidgetItem(source.version))
            self.source_table.setItem(i, 2, QTableWidgetItem(source.author))
            self.source_table.setItem(i, 3, QTableWidgetItem(source.description))
            
            status = "✓ 活动" if active and active.name == source.name else ""
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor("#50e050") if status else QColor("#808080"))
            self.source_table.setItem(i, 4, status_item)
            
    def _activate_source(self):
        row = self.source_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个音源")
            return
            
        source_name = self.source_table.item(row, 0).text()
        success, message = self.source_manager.set_active_source(source_name)
        if success:
            QMessageBox.information(self, "设置成功", message)
            self.refresh_source_list()
        else:
            QMessageBox.warning(self, "设置失败", message)
            
    def _configure_api(self):
        row = self.source_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个音源")
            return
            
        source_name = self.source_table.item(row, 0).text()
        config = self.source_manager.get_api_config(source_name)
        
        dialog = SourceAPIConfigDialog(source_name, config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            self.source_manager.set_api_config(
                source_name, 
                new_config.get('api_url', ''),
                new_config.get('api_key', '')
            )
            QMessageBox.information(self, "保存成功", "API配置已保存")
            
    def _remove_source(self):
        row = self.source_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个音源")
            return
            
        source_name = self.source_table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除音源 '{source_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.source_manager.remove_source(source_name)
            if success:
                QMessageBox.information(self, "删除成功", message)
                self.refresh_source_list()
            else:
                QMessageBox.warning(self, "删除失败", message)


# 需要导入QColor
from PyQt6.QtGui import QColor


class SourceAPIConfigDialog(QDialog):
    """音源API配置对话框"""
    
    def __init__(self, source_name: str, config: dict, parent=None):
        super().__init__(parent)
        self.source_name = source_name
        self.config = config or {}
        self.setWindowTitle(f"配置 - {source_name}")
        self.setFixedSize(500, 250)
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a24; }
            QLabel { color: #e0e0e0; }
            QLineEdit { background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 8px; padding: 10px; color: #e0e0e0; }
            QLineEdit:focus { border-color: #7c5ce0; }
            QPushButton { background: #7c5ce0; color: white; border: none; border-radius: 8px; padding: 10px 20px; font-weight: bold; }
            QPushButton:hover { background: #9c7cf0; }
            QPushButton#secondaryBtn { background: #4a4a5e; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel(f"🔧 配置音源: {self.source_name}")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # API地址
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("API地址:"))
        self.url_edit = QLineEdit(self.config.get('api_url', ''))
        self.url_edit.setPlaceholderText("https://api.example.com")
        url_layout.addWidget(self.url_edit)
        layout.addLayout(url_layout)
        
        # API密钥
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("API密钥:"))
        self.key_edit = QLineEdit(self.config.get('api_key', ''))
        self.key_edit.setPlaceholderText("可选")
        key_layout.addWidget(self.key_edit)
        layout.addLayout(key_layout)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
    def get_config(self) -> dict:
        return {
            'api_url': self.url_edit.text().strip(),
            'api_key': self.key_edit.text().strip()
        }


class RecommenderDebugDialog(QDialog):
    """推荐系统调试对话框"""
    
    def __init__(self, recommender, settings, parent=None):
        super().__init__(parent)
        self.recommender = recommender
        self.settings = settings
        self.setWindowTitle("🧠 推荐系统调试")
        self.setMinimumSize(800, 700)
        self.setup_ui()
        self.refresh_data()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a24; }
            QLabel { color: #e0e0e0; }
            QGroupBox { 
                color: #a0a0a0; border: 1px solid #3a3a4a; 
                border-radius: 8px; margin-top: 12px; padding-top: 8px;
            }
            QPushButton { 
                background: #7c5ce0; color: white; 
                border: none; border-radius: 8px; 
                padding: 10px 20px; font-weight: bold; 
            }
            QPushButton:hover { background: #9c7cf0; }
            QPushButton#secondaryBtn { background: #4a4a5e; }
            QPushButton#dangerBtn { background: #e05050; }
            QPushButton#dangerBtn:hover { background: #f06060; }
            QCheckBox { color: #e0e0e0; }
            QTextEdit { 
                background: #0a0a12; color: #00ff00; 
                border: 1px solid #3a3a4a; border-radius: 8px;
                font-family: Consolas, monospace; font-size: 11px;
            }
            QTableWidget { 
                background: #1a1a24; color: #e0e0e0; 
                border: 1px solid #3a3a4a; border-radius: 8px;
                gridline-color: #2a2a3a;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background: #7c5ce0; }
            QHeaderView::section { 
                background: #2a2a3a; color: #a0a0a0; 
                padding: 8px; border: none; 
            }
            QTabWidget::pane { border: 1px solid #3a3a4a; border-radius: 8px; }
            QTabBar::tab { 
                background: #2a2a3a; color: #a0a0a0; 
                padding: 10px 20px; border-radius: 8px 8px 0 0; 
            }
            QTabBar::tab:selected { background: #3a3a4a; color: #ffffff; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 顶部控制区
        control_group = QGroupBox("学习控制")
        control_layout = QHBoxLayout(control_group)
        
        self.learning_enabled = QCheckBox("启用推荐学习")
        self.learning_enabled.setChecked(self.settings.value("recommender_learning_enabled", True, type=bool))
        self.learning_enabled.stateChanged.connect(self._on_learning_toggle)
        control_layout.addWidget(self.learning_enabled)
        
        control_layout.addSpacing(20)
        
        self.exploration_label = QLabel("探索率: 15%")
        control_layout.addWidget(self.exploration_label)
        
        control_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新数据")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self.refresh_data)
        control_layout.addWidget(refresh_btn)
        
        save_btn = QPushButton("💾 保存数据")
        save_btn.clicked.connect(self._save_data)
        control_layout.addWidget(save_btn)
        
        reset_btn = QPushButton("🗑️ 重置学习数据")
        reset_btn.setObjectName("dangerBtn")
        reset_btn.clicked.connect(self._reset_data)
        control_layout.addWidget(reset_btn)
        
        layout.addWidget(control_group)
        
        # 标签页
        tabs = QTabWidget()
        
        # 统计页
        stats_tab = self._create_stats_tab()
        tabs.addTab(stats_tab, "📊 统计信息")
        
        # 歌曲偏好页
        songs_tab = self._create_songs_tab()
        tabs.addTab(songs_tab, "🎵 歌曲偏好")
        
        # 快速训练模式页
        training_tab = self._create_training_tab()
        tabs.addTab(training_tab, "⚡ 快速训练")
        
        # 日志页
        log_tab = self._create_log_tab()
        tabs.addTab(log_tab, "📝 日志")
        
        layout.addWidget(tabs)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
    def _create_stats_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 统计信息显示
        self.stats_text = QLabel()
        self.stats_text.setWordWrap(True)
        self.stats_text.setStyleSheet("color: #e0e0e0; font-size: 13px; line-height: 1.6;")
        layout.addWidget(self.stats_text)
        
        layout.addStretch()
        return widget
        
    def _create_songs_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 歌曲偏好表格
        self.songs_table = QTableWidget()
        self.songs_table.setColumnCount(7)
        self.songs_table.setHorizontalHeaderLabels([
            "歌曲名称", "艺术家", "学习状态", "偏好分数", "置信度", "播放次数", "完成次数"
        ])
        self.songs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.songs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(2, 7):
            self.songs_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.songs_table)
        
        return widget
    
    def _create_training_tab(self) -> QWidget:
        """创建快速训练模式标签页 - 优化版"""
        from PyQt6.QtWidgets import QSpinBox, QTextEdit, QListWidget, QListWidgetItem, QSplitter
        from PyQt6.QtCore import Qt
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        intro_label = QLabel(
            "⚡ <b>快速训练模式</b> - 标记歌曲偏好，快速训练推荐系统<br>"
            "💡 操作后自动跳到下一首，支持连续训练"
        )
        intro_label.setWordWrap(True)
        intro_label.setStyleSheet("color: #a0a0a0; margin-bottom: 10px;")
        layout.addWidget(intro_label)
        
        # 主区域使用分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：歌曲列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        # 歌曲列表标题和刷新按钮
        list_header = QHBoxLayout()
        list_header.addWidget(QLabel("📋 待训练歌曲:"))
        list_header.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("QPushButton { background: #4a4a5e; color: white; border: none; border-radius: 4px; padding: 6px 12px; } QPushButton:hover { background: #5a5a6e; }")
        refresh_btn.clicked.connect(self._refresh_training_songs)
        list_header.addWidget(refresh_btn)
        left_layout.addLayout(list_header)
        
        # 歌曲列表
        self.training_song_list = QListWidget()
        self.training_song_list.setStyleSheet("""
            QListWidget { 
                background: #2a2a3a; color: #e0e0e0; 
                border: 1px solid #3a3a4a; border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item { padding: 8px; border-radius: 4px; margin: 2px 0; }
            QListWidget::item:selected { background: #7c5ce0; }
            QListWidget::item:hover:!selected { background: #3a3a4a; }
        """)
        self.training_song_list.currentRowChanged.connect(self._on_training_song_selected)
        left_layout.addWidget(self.training_song_list)
        
        # 统计信息
        self.training_stats_label = QLabel("已训练: 0 | 喜欢: 0 | 不喜欢: 0")
        self.training_stats_label.setStyleSheet("color: #808080; font-size: 11px;")
        left_layout.addWidget(self.training_stats_label)
        
        splitter.addWidget(left_widget)
        
        # 右侧：操作区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        # 当前歌曲信息
        current_group = QGroupBox("当前歌曲")
        current_layout = QVBoxLayout(current_group)
        
        self.current_song_label = QLabel("请选择一首歌曲开始训练")
        self.current_song_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        self.current_song_label.setWordWrap(True)
        current_layout.addWidget(self.current_song_label)
        
        self.current_song_info = QLabel("")
        self.current_song_info.setStyleSheet("color: #808080; font-size: 11px;")
        current_layout.addWidget(self.current_song_info)
        
        right_layout.addWidget(current_group)
        
        # 操作按钮 - 大按钮，易于点击
        actions_group = QGroupBox("标记偏好")
        actions_layout = QVBoxLayout(actions_group)
        
        # 第一行：喜欢/不喜欢
        btn_row1 = QHBoxLayout()
        
        like_btn = QPushButton("❤️ 喜欢 (听完)")
        like_btn.setToolTip("标记为完整播放，表示喜欢这首歌")
        like_btn.setStyleSheet("QPushButton { background: #50e050; color: white; border: none; border-radius: 12px; padding: 20px; font-weight: bold; font-size: 14px; } QPushButton:hover { background: #60f060; }")
        like_btn.clicked.connect(lambda: self._quick_train_action('complete'))
        btn_row1.addWidget(like_btn)
        
        dislike_btn = QPushButton("👎 不喜欢 (秒切)")
        dislike_btn.setToolTip("标记为快速跳过，表示不喜欢这首歌")
        dislike_btn.setStyleSheet("QPushButton { background: #e05050; color: white; border: none; border-radius: 12px; padding: 20px; font-weight: bold; font-size: 14px; } QPushButton:hover { background: #f06060; }")
        dislike_btn.clicked.connect(lambda: self._quick_train_action('skip'))
        btn_row1.addWidget(dislike_btn)
        
        actions_layout.addLayout(btn_row1)
        
        # 第二行：中性/跳过
        btn_row2 = QHBoxLayout()
        
        neutral_btn = QPushButton("😐 一般 (听一半)")
        neutral_btn.setToolTip("标记为听一半，表示感觉一般")
        neutral_btn.setStyleSheet("QPushButton { background: #e0a050; color: white; border: none; border-radius: 8px; padding: 12px; font-weight: bold; } QPushButton:hover { background: #f0b060; }")
        neutral_btn.clicked.connect(lambda: self._quick_train_action('half'))
        btn_row2.addWidget(neutral_btn)
        
        skip_song_btn = QPushButton("⏭ 跳过 (不训练)")
        skip_song_btn.setToolTip("跳过这首歌，不进行训练")
        skip_song_btn.setStyleSheet("QPushButton { background: #4a4a5e; color: white; border: none; border-radius: 8px; padding: 12px; font-weight: bold; } QPushButton:hover { background: #5a5a6e; }")
        skip_song_btn.clicked.connect(self._skip_to_next_song)
        btn_row2.addWidget(skip_song_btn)
        
        actions_layout.addLayout(btn_row2)
        right_layout.addWidget(actions_group)
        
        # 训练选项
        auto_group = QGroupBox("训练选项")
        auto_layout = QVBoxLayout(auto_group)
        
        self.auto_next_check = QCheckBox("训练后自动跳到下一首")
        self.auto_next_check.setChecked(True)
        self.auto_next_check.setStyleSheet("color: #e0e0e0;")
        auto_layout.addWidget(self.auto_next_check)
        
        self.auto_save_check = QCheckBox("每10次训练自动保存")
        self.auto_save_check.setChecked(True)
        self.auto_save_check.setStyleSheet("color: #e0e0e0;")
        auto_layout.addWidget(self.auto_save_check)
        
        # 批量训练
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("批量标记次数:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 50)
        self.batch_size_spin.setValue(5)
        self.batch_size_spin.setStyleSheet("background: #2a2a3a; color: #e0e0e0; border: 1px solid #3a3a4a; padding: 5px;")
        batch_layout.addWidget(self.batch_size_spin)
        batch_layout.addStretch()
        auto_layout.addLayout(batch_layout)
        
        batch_btn_layout = QHBoxLayout()
        batch_like_btn = QPushButton("批量喜欢 ❤️")
        batch_like_btn.setStyleSheet("QPushButton { background: #408b40; color: white; border: none; border-radius: 6px; padding: 8px 16px; } QPushButton:hover { background: #509b50; }")
        batch_like_btn.clicked.connect(lambda: self._batch_train('complete'))
        batch_btn_layout.addWidget(batch_like_btn)
        
        batch_dislike_btn = QPushButton("批量不喜欢 👎")
        batch_dislike_btn.setStyleSheet("QPushButton { background: #8b4040; color: white; border: none; border-radius: 6px; padding: 8px 16px; } QPushButton:hover { background: #9b5050; }")
        batch_dislike_btn.clicked.connect(lambda: self._batch_train('skip'))
        batch_btn_layout.addWidget(batch_dislike_btn)
        auto_layout.addLayout(batch_btn_layout)
        
        right_layout.addWidget(auto_group)
        
        # 训练日志
        log_group = QGroupBox("训练日志")
        log_layout = QVBoxLayout(log_group)
        self.training_log = QTextEdit()
        self.training_log.setReadOnly(True)
        self.training_log.setMaximumHeight(100)
        self.training_log.setStyleSheet("QTextEdit { background: #0a0a12; color: #00ff00; border: 1px solid #3a3a4a; font-family: Consolas; font-size: 11px; }")
        log_layout.addWidget(self.training_log)
        right_layout.addWidget(log_group)
        
        right_layout.addStretch()
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 400])
        layout.addWidget(splitter)
        
        # 初始化训练统计
        self._training_count = 0
        self._like_count = 0
        self._dislike_count = 0
        
        return widget
    
    def _refresh_training_songs(self):
        """刷新训练用歌曲列表"""
        self.training_song_list.clear()
        if self.recommender:
            try:
                stats = self.recommender.get_statistics()
                all_songs = stats.get('all_songs', [])
                
                for song in all_songs:
                    path = song.get('path', '')
                    title = song.get('title', '') or os.path.basename(path)
                    artist = song.get('artist', '')
                    score = song.get('score', 0.5)
                    play_count = song.get('play_count', 0)
                    
                    display = f"{title}"
                    if artist:
                        display += f" - {artist}"
                    
                    if play_count > 0:
                        if score > 0.7:
                            display = f"❤️ {display}"
                        elif score < 0.3:
                            display = f"👎 {display}"
                        else:
                            display = f"🎵 {display}"
                    else:
                        display = f"🆕 {display}"
                    
                    from PyQt6.QtWidgets import QListWidgetItem
                    item = QListWidgetItem(display)
                    item.setData(256, path)
                    item.setData(257, song)
                    self.training_song_list.addItem(item)
                
                self._add_training_log("INFO", f"已加载 {len(all_songs)} 首歌曲")
                
                if self.training_song_list.count() > 0:
                    self.training_song_list.setCurrentRow(0)
                    
            except Exception as e:
                self._add_training_log("ERROR", f"加载歌曲失败: {e}")
    
    def _on_training_song_selected(self, row):
        """当选择训练歌曲时"""
        if row < 0:
            return
        
        item = self.training_song_list.item(row)
        if item:
            song_info = item.data(257)
            if song_info:
                title = song_info.get('title', '') or os.path.basename(song_info.get('path', ''))
                artist = song_info.get('artist', '')
                score = song_info.get('score', 0.5)
                play_count = song_info.get('play_count', 0)
                complete_count = song_info.get('complete_count', 0)
                skip_count = song_info.get('skip_count', 0)
                
                self.current_song_label.setText(title)
                
                info_parts = []
                if artist:
                    info_parts.append(f"艺术家: {artist}")
                info_parts.append(f"偏好: {score:.0%}")
                info_parts.append(f"播放{play_count} 完成{complete_count} 跳过{skip_count}")
                
                self.current_song_info.setText(" | ".join(info_parts))
    
    def _quick_train_action(self, action: str):
        """快速训练动作"""
        if not self.recommender:
            self._add_training_log("ERROR", "推荐系统未初始化")
            return
        
        current_item = self.training_song_list.currentItem()
        if not current_item:
            self._add_training_log("WARNING", "请先选择歌曲")
            return
        
        path = current_item.data(256)
        song_info = current_item.data(257)
        title = (song_info.get('title', '') or os.path.basename(path))[:30]
        
        try:
            song_data = {
                'path': path,
                'title': title,
                'artist': song_info.get('artist', ''),
                'duration': 180
            }
            
            if action == 'skip':
                played_seconds = 5
                reason = 'skip'
                action_emoji = "👎"
                self._dislike_count += 1
            elif action == 'half':
                played_seconds = 90
                reason = 'half'
                action_emoji = "😐"
            else:
                played_seconds = 180
                reason = 'complete'
                action_emoji = "❤️"
                self._like_count += 1
            
            self.recommender.on_song_start(song_data)
            self.recommender.on_song_end(song_data, played_seconds, reason)
            
            self._training_count += 1
            
            action_names = {'skip': '不喜欢', 'half': '一般', 'complete': '喜欢'}
            self._add_training_log("INFO", f"{action_emoji} {action_names[action]}: {title}")
            
            self._update_training_stats()
            
            if self.auto_save_check.isChecked() and self._training_count % 10 == 0:
                self.recommender.save()
                self._add_training_log("INFO", "💾 自动保存")
            
            self.refresh_data()
            
            if self.auto_next_check.isChecked():
                self._go_to_next_song()
            
        except Exception as e:
            self._add_training_log("ERROR", f"训练失败: {e}")
    
    def _skip_to_next_song(self):
        """跳过当前歌曲"""
        self._go_to_next_song()
        self._add_training_log("INFO", "⏭ 已跳过")
    
    def _go_to_next_song(self):
        """跳到下一首歌"""
        current_row = self.training_song_list.currentRow()
        if current_row < self.training_song_list.count() - 1:
            self.training_song_list.setCurrentRow(current_row + 1)
        else:
            self._add_training_log("INFO", "✅ 已到列表末尾")
    
    def _batch_train(self, action: str):
        """批量训练"""
        if not self.recommender:
            return
        
        batch_size = self.batch_size_spin.value()
        start_row = self.training_song_list.currentRow()
        
        if start_row < 0:
            self._add_training_log("WARNING", "请先选择起始歌曲")
            return
        
        trained = 0
        for i in range(batch_size):
            row = start_row + i
            if row >= self.training_song_list.count():
                break
            
            self.training_song_list.setCurrentRow(row)
            self._quick_train_action(action)
            trained += 1
        
        action_names = {'skip': '不喜欢', 'complete': '喜欢'}
        self._add_training_log("INFO", f"批量{action_names.get(action, action)} x{trained} 完成")
    
    def _update_training_stats(self):
        """更新训练统计"""
        self.training_stats_label.setText(
            f"已训练: {self._training_count} | 喜欢: {self._like_count} | 不喜欢: {self._dislike_count}"
        )
    
    def _add_training_log(self, level: str, message: str):
        """添加训练日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "#00ff00", "WARNING": "#ffff00", "ERROR": "#ff6b6b"}
        color = colors.get(level, "#ffffff")
        log_line = f'<span style="color: #808080;">[{timestamp}]</span> <span style="color: {color};">[{level}]</span> {message}'
        current = self.training_log.toHtml()
        self.training_log.setHtml(current + log_line + "<br>")
        scrollbar = self.training_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def _create_log_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QTextEdit
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 日志级别选择和操作按钮
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("日志级别:"))
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["全部", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setStyleSheet("background: #2a2a3a; color: #e0e0e0; border: 1px solid #3a3a4a; border-radius: 4px; padding: 5px;")
        self.log_level_combo.currentTextChanged.connect(self._filter_logs)
        level_layout.addWidget(self.log_level_combo)
        
        level_layout.addStretch()
        
        # 加载推荐系统日志按钮
        load_log_btn = QPushButton("📥 加载系统日志")
        load_log_btn.setObjectName("secondaryBtn")
        load_log_btn.clicked.connect(self._load_recommender_logs)
        level_layout.addWidget(load_log_btn)
        
        clear_log_btn = QPushButton("🗑️ 清空日志")
        clear_log_btn.setObjectName("secondaryBtn")
        clear_log_btn.clicked.connect(self._clear_log)
        level_layout.addWidget(clear_log_btn)
        
        layout.addLayout(level_layout)
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # 初始化时加载日志
        self._load_recommender_logs()
        
        return widget
    
    def _load_recommender_logs(self):
        """从推荐系统加载日志历史"""
        if not self.recommender:
            self._add_log("WARNING", "推荐系统未初始化")
            return
        
        try:
            # 检查推荐系统是否有日志历史方法
            if hasattr(self.recommender, 'get_log_history'):
                logs = self.recommender.get_log_history()
                if logs:
                    self.log_text.clear()
                    for log in logs:
                        self._add_log(log.get('level', 'INFO'), log.get('message', ''))
                    self._add_log("INFO", f"已加载 {len(logs)} 条历史日志")
                else:
                    self._add_log("INFO", "暂无历史日志")
            else:
                self._add_log("INFO", "推荐系统不支持日志历史")
        except Exception as e:
            self._add_log("ERROR", f"加载日志失败: {str(e)}")
    
    def _filter_logs(self, level_text: str):
        """根据级别过滤日志（暂未实现完整过滤）"""
        pass  # 可以后续实现
        
    def refresh_data(self):
        """刷新所有数据显示"""
        if not self.recommender:
            self.stats_text.setText("⚠️ 推荐系统未初始化")
            return
            
        try:
            stats = self.recommender.get_statistics()
            
            # 更新探索率显示
            exploration = stats.get('exploration_rate', 0.15)
            self.exploration_label.setText(f"探索率: {exploration:.0%}")
            
            # 更新统计信息
            session = stats.get('session', {})
            learned = stats.get('learned_songs', 0)
            unlearned = stats.get('unlearned_songs', 0)
            total_songs = stats.get('total_songs', 0)
            learn_percent = (learned / total_songs * 100) if total_songs > 0 else 0
            
            stats_html = f"""
            <h3 style="color: #7c5ce0;">📊 学习统计</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; color: #a0a0a0;">歌曲库总数:</td><td style="padding: 8px; color: #ffffff; font-weight: bold;">{total_songs}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">已学习歌曲:</td><td style="padding: 8px; color: #50e050;">{learned} ({learn_percent:.1f}%)</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">待学习歌曲:</td><td style="padding: 8px; color: #ffa500;">{unlearned}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">总播放次数:</td><td style="padding: 8px; color: #ffffff;">{stats.get('total_plays', 0)}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">转换记录数:</td><td style="padding: 8px; color: #ffffff;">{stats.get('transition_count', 0)}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">历史事件数:</td><td style="padding: 8px; color: #ffffff;">{stats.get('history_events', 0)}</td></tr>
            </table>
            
            <h3 style="color: #7c5ce0; margin-top: 20px;">🎯 当前会话状态</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; color: #a0a0a0;">本次播放歌曲:</td><td style="padding: 8px; color: #ffffff;">{session.get('songs_played', 0)} 首</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">连续完成:</td><td style="padding: 8px; color: #50e050;">{session.get('consecutive_good', 0)} 首</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">连续跳过:</td><td style="padding: 8px; color: #ff6b6b;">{session.get('consecutive_bad', 0)} 首</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">挑剔模式:</td><td style="padding: 8px; color: {'#ff6b6b' if session.get('is_picky_mode') else '#50e050'};">{'是 🔍 (快速学习)' if session.get('is_picky_mode') else '否'}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">稳定模式:</td><td style="padding: 8px; color: {'#50e050' if session.get('is_relaxed_mode') else '#a0a0a0'};">{'是 😌 (低学习率)' if session.get('is_relaxed_mode') else '否'}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">基础学习率:</td><td style="padding: 8px; color: #808080;">{session.get('base_learning_rate', 0.15):.3f}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">当前学习率:</td><td style="padding: 8px; color: #ffffff; font-weight: bold;">{session.get('current_learning_rate', 0.15):.3f}</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">探索率:</td><td style="padding: 8px; color: #ffffff;">{stats.get('exploration_rate', 0.15):.0%}</td></tr>
            </table>
            
            <h3 style="color: #7c5ce0; margin-top: 20px;">🎯 当前会话喜好</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; color: #a0a0a0;">听完的歌 (喜欢):</td><td style="padding: 8px; color: #50e050;">{len(session.get('current_likes', []))} 首</td></tr>
                <tr><td style="padding: 8px; color: #a0a0a0;">秒切的歌 (不想听):</td><td style="padding: 8px; color: #ff6b6b;">{len(session.get('current_dislikes', []))} 首</td></tr>
            </table>
            """
            
            # 显示当前喜欢的歌曲
            current_likes = session.get('current_likes', [])
            if current_likes:
                stats_html += "<p style='color: #50e050; margin-top: 10px;'>❤️ 当前喜欢: " + ", ".join(current_likes[:5])
                if len(current_likes) > 5:
                    stats_html += f" (+{len(current_likes)-5}首)"
                stats_html += "</p>"
            
            # 显示当前不想听的歌曲
            current_dislikes = session.get('current_dislikes', [])
            if current_dislikes:
                stats_html += "<p style='color: #ff6b6b;'>👎 当前不想听: " + ", ".join(current_dislikes[:3])
                if len(current_dislikes) > 3:
                    stats_html += f" (+{len(current_dislikes)-3}首)"
                stats_html += "</p>"
            
            stats_html += """
            <h3 style="color: #7c5ce0; margin-top: 20px;">⭐ 历史最喜欢的歌曲 (Top 5)</h3>
            """
            
            top_songs = stats.get('top_songs', [])
            if top_songs:
                stats_html += "<table style='width: 100%; border-collapse: collapse;'>"
                for i, song in enumerate(top_songs[:5], 1):
                    path = song.get('path', '未知')
                    # 只显示文件名
                    filename = os.path.basename(path) if path else '未知'
                    score = song.get('score', 0)
                    confidence = song.get('confidence', 0)
                    stats_html += f"""
                    <tr>
                        <td style="padding: 8px; color: #a0a0a0;">{i}.</td>
                        <td style="padding: 8px; color: #ffffff;">{filename[:40]}...</td>
                        <td style="padding: 8px; color: #50e050;">{score:.0%}</td>
                        <td style="padding: 8px; color: #808080;">置信度: {confidence:.0%}</td>
                    </tr>
                    """
                stats_html += "</table>"
            else:
                stats_html += "<p style='color: #808080;'>暂无数据，请先播放一些歌曲</p>"
            
            self.stats_text.setText(stats_html)
            
            # 更新歌曲表格
            self._update_songs_table(stats)
            
            # 添加日志
            self._add_log("INFO", "数据已刷新")
            
        except Exception as e:
            self.stats_text.setText(f"❌ 获取统计数据失败: {str(e)}")
            self._add_log("ERROR", f"获取统计数据失败: {str(e)}")
            
    def _update_songs_table(self, stats: dict):
        """更新歌曲偏好表格"""
        all_songs = stats.get('all_songs', [])
        self.songs_table.setRowCount(len(all_songs))
        
        for row, song in enumerate(all_songs):
            title = song.get('title', '')
            if not title:
                path = song.get('path', '')
                title = os.path.basename(path) if path else '未知'
            artist = song.get('artist', '')
            is_learned = song.get('is_learned', False)
            
            # 歌曲名称
            self.songs_table.setItem(row, 0, QTableWidgetItem(title))
            # 艺术家
            self.songs_table.setItem(row, 1, QTableWidgetItem(artist))
            # 学习状态
            learn_status = "✅ 已学习" if is_learned else "🆕 待学习"
            status_item = QTableWidgetItem(learn_status)
            self.songs_table.setItem(row, 2, status_item)
            # 偏好分数
            self.songs_table.setItem(row, 3, QTableWidgetItem(f"{song.get('score', 0):.2f}"))
            # 置信度
            self.songs_table.setItem(row, 4, QTableWidgetItem(f"{song.get('confidence', 0):.2f}"))
            # 播放次数
            self.songs_table.setItem(row, 5, QTableWidgetItem(str(song.get('play_count', 0))))
            # 完成次数
            self.songs_table.setItem(row, 6, QTableWidgetItem(str(song.get('complete_count', 0))))
            
    def _on_learning_toggle(self, state):
        """切换学习开关"""
        enabled = state == 2  # Qt.CheckState.Checked
        self.settings.setValue("recommender_learning_enabled", enabled)
        status = "启用" if enabled else "禁用"
        self._add_log("INFO", f"推荐学习已{status}")
        
    def _save_data(self):
        """保存推荐数据"""
        if self.recommender:
            try:
                self.recommender.save()
                self._add_log("INFO", "推荐数据已保存")
                QMessageBox.information(self, "保存成功", "推荐学习数据已保存")
            except Exception as e:
                self._add_log("ERROR", f"保存失败: {str(e)}")
                QMessageBox.warning(self, "保存失败", str(e))
                
    def _reset_data(self):
        """重置学习数据"""
        reply = QMessageBox.question(
            self, "确认重置", 
            "确定要重置所有学习数据吗？\n\n这将清除所有歌曲偏好和播放历史，无法恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.recommender:
                try:
                    self.recommender.reset()
                    self._add_log("WARNING", "学习数据已重置")
                    self.refresh_data()
                    QMessageBox.information(self, "重置成功", "学习数据已重置")
                except Exception as e:
                    self._add_log("ERROR", f"重置失败: {str(e)}")
                    QMessageBox.warning(self, "重置失败", str(e))
                    
    def _add_log(self, level: str, message: str):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        colors = {
            "DEBUG": "#808080",
            "INFO": "#00ff00",
            "WARNING": "#ffff00", 
            "ERROR": "#ff6b6b"
        }
        color = colors.get(level, "#ffffff")
        
        log_line = f'<span style="color: #606060;">[{timestamp}]</span> <span style="color: {color};">[{level}]</span> {message}'
        
        current = self.log_text.toHtml()
        self.log_text.setHtml(current + log_line + "<br>")
        
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def _clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self._add_log("INFO", "日志已清空")
        
    def add_external_log(self, level: str, message: str):
        """从外部添加日志（供主窗口调用）"""
        self._add_log(level, message)
