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

