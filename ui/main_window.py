"""
主窗口
"""

import os
import sys
import random
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSplitter, QLineEdit, QMessageBox, QDialog, QProgressBar,
    QMenu, QStackedWidget, QAbstractItemView, QTableView, QFrame, QToolButton
)
from PyQt6.QtCore import Qt, QTimer, QSettings, QModelIndex, QPoint, QUrl
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QMouseEvent
from PyQt6.QtMultimedia import QMediaPlayer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import SongInfo, SongScanner, VirtualSongListModel, SongCache, SUPPORTED_FORMATS
from core.msst import MSSTSeparatorThread
from core.recommendation_api import RecommendationAPIServer, DefaultRecommendationProvider
from core.lxmusic_api import OnlineMusicClient, OnlineSong
from core.custom_source import CustomSourceManager, SourceAPIProxy

from ui.track_control import TrackControl, TrackControlPanel
from ui.lyrics_page import LyricsPage
from ui.dialogs import SettingsDialog, MSSTDialog, OnlineSearchDialog, CustomSourceDialog


class ClickableSlider(QSlider):
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.orientation() == Qt.Orientation.Horizontal:
                value = self.minimum() + (self.maximum() - self.minimum()) * event.pos().x() / self.width()
            else:
                value = self.minimum() + (self.maximum() - self.minimum()) * (1 - event.pos().y() / self.height())
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
        super().mousePressEvent(event)


class CollapsibleSongList(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.song_model = VirtualSongListModel()
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("background: #1a1a24; border-radius: 16px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header = QHBoxLayout()
        self.collapse_btn = QToolButton()
        self.collapse_btn.setText("▼")
        self.collapse_btn.setStyleSheet("QToolButton { background: transparent; color: #a0a0a0; border: none; font-size: 12px; } QToolButton:hover { color: #ffffff; }")
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        header.addWidget(self.collapse_btn)
        
        title = QLabel("🎶 歌曲列表")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        header.addWidget(title)
        
        self.song_count_label = QLabel("0 首")
        self.song_count_label.setStyleSheet("color: #808080;")
        header.addWidget(self.song_count_label)
        header.addStretch()
        
        # 定位当前歌曲按钮
        self.locate_btn = QPushButton("📍")
        self.locate_btn.setFixedSize(32, 32)
        self.locate_btn.setToolTip("定位当前播放的歌曲")
        self.locate_btn.setStyleSheet("QPushButton { background: #3a3a4a; border: none; border-radius: 16px; } QPushButton:hover { background: #7c5ce0; }")
        header.addWidget(self.locate_btn)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setToolTip("刷新歌曲列表")
        self.refresh_btn.setStyleSheet("QPushButton { background: #3a3a4a; border: none; border-radius: 16px; } QPushButton:hover { background: #4a4a5a; }")
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        
        self.scan_progress = QProgressBar()
        self.scan_progress.setStyleSheet("QProgressBar { background: #2a2a3a; border: none; border-radius: 4px; height: 4px; } QProgressBar::chunk { background: #7c5ce0; }")
        self.scan_progress.setVisible(False)
        layout.addWidget(self.scan_progress)
        
        self.song_table = QTableView()
        self.song_table.setModel(self.song_model)
        self.song_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.song_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.song_table.setShowGrid(False)
        self.song_table.verticalHeader().setVisible(False)
        self.song_table.horizontalHeader().setStretchLastSection(True)
        self.song_table.setColumnWidth(0, 180)
        self.song_table.setColumnWidth(1, 100)
        self.song_table.setColumnWidth(2, 50)
        self.song_table.setColumnWidth(3, 40)
        self.song_table.verticalHeader().setDefaultSectionSize(45)
        self.song_table.setStyleSheet("""
            QTableView { background: #1a1a24; border: none; border-radius: 12px; gridline-color: transparent; selection-background-color: #7c5ce0; }
            QTableView::item { padding: 8px; }
            QTableView::item:hover { background: #2a2a3a; }
            QHeaderView::section { background: #2a2a3a; color: #a0a0a0; padding: 8px; border: none; font-weight: bold; }
        """)
        layout.addWidget(self.song_table)
        
    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        self.song_table.setVisible(not self.is_collapsed)
        self.collapse_btn.setText("▶" if self.is_collapsed else "▼")
        
    def update_count(self, count: int):
        self.song_count_label.setText(f"{count} 首")
    
    def scroll_to_song(self, song_index: int):
        """滚动到指定歌曲并选中"""
        if song_index < 0 or song_index >= self.song_model.rowCount():
            return
        
        # 如果列表是折叠的，先展开
        if self.is_collapsed:
            self.toggle_collapse()
        
        # 获取模型索引
        model_index = self.song_model.index(song_index, 0)
        
        # 选中该行
        self.song_table.selectRow(song_index)
        
        # 滚动到该行，居中显示
        self.song_table.scrollTo(model_index, QAbstractItemView.ScrollHint.PositionAtCenter)


class MultiTrackPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MultiTrackPlayer", "Settings")
        self.config = self._load_config()
        self.songs: List[SongInfo] = []
        self.current_song: Optional[SongInfo] = None
        self.current_song_index = -1
        self.track_controls: List[TrackControl] = []
        self.is_playing = False
        self.play_mode = "sequential"
        self.playback_rate = 1.0
        self.shuffle_order: List[int] = []
        self.shuffle_index = 0
        self.mode = "single"
        self.current_page = "tracks"
        self.scanner: Optional[SongScanner] = None
        self.separator_thread: Optional[MSSTSeparatorThread] = None
        self.lx_client = OnlineMusicClient()
        self.recommendation_server = RecommendationAPIServer(self.config.get('recommendation_port', 23331))
        self.recommendation_provider = DefaultRecommendationProvider()
        # 添加歌曲缓存
        self.song_cache = SongCache()
        # 添加自定义音源管理器
        self.source_manager = CustomSourceManager()
        self.source_manager.scan_sources_dir()
        # 进度条拖动状态
        self.seek_pending = False
        self.seek_value = 0
        self.setup_ui()
        self.setup_shortcuts()
        self.setup_timer()
        self.setup_recommendation_api()
        # 改用缓存加载或扫描
        QTimer.singleShot(100, self.load_songs_with_cache)
        
    def _load_config(self) -> dict:
        return {
            'music_path': self.settings.value("music_path", ""),
            'stems_path': self.settings.value("stems_path", ""),
            'msst_path': self.settings.value("msst_path", ""),
            'model_type': self.settings.value("model_type", "bs_roformer"),
            'config_path': self.settings.value("config_path", ""),
            'model_path': self.settings.value("model_path", ""),
            'output_format': self.settings.value("output_format", "wav"),
            'recommendation_port': int(self.settings.value("recommendation_port", 23331)),
            'recommendation_enabled': self.settings.value("recommendation_enabled", True, type=bool),
            'lxmusic_api_url': self.settings.value("lxmusic_api_url", "http://127.0.0.1:9763")
        }
        
    def _save_config(self):
        for key, value in self.config.items():
            self.settings.setValue(key, value)
            
    def setup_recommendation_api(self):
        if self.config.get('recommendation_enabled', True):
            self.recommendation_server.set_provider(self.recommendation_provider)
            self.recommendation_server.set_player_callback(self._handle_api_callback)
            self.recommendation_server.start()
            
    def _handle_api_callback(self, action: str, data=None):
        if action == 'get_status':
            return {
                'playing': self.is_playing,
                'current_song': {'title': self.current_song.title, 'artist': self.current_song.artist, 'path': self.current_song.path} if self.current_song else None,
                'progress': self.track_controls[0].get_position() / 1000.0 if self.track_controls else 0,
                'duration': self.track_controls[0].get_duration() / 1000.0 if self.track_controls else 0
            }
        elif action == 'play_song' and data:
            path = data.get('path', '')
            if path and os.path.exists(path):
                for song in self.songs:
                    if song.path == path:
                        self.play_song(song)
                        return True
            return False
        elif action == 'play_next':
            self.play_next()
            
    def setup_ui(self):
        self.setWindowTitle("🎵 Multi-Track Player v3.0")
        self.setMinimumSize(1400, 850)
        self.setStyleSheet("QMainWindow { background: #12121a; } QScrollArea { border: none; background: transparent; } QScrollBar:vertical { background: #1a1a24; width: 10px; border-radius: 5px; } QScrollBar::handle:vertical { background: #4a4a5e; border-radius: 5px; min-height: 30px; }")
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)
        
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setStyleSheet("QSplitter::handle { background: #3a3a4a; width: 2px; }")
        
        self.song_list = CollapsibleSongList()
        self.song_list.song_table.doubleClicked.connect(self.on_song_double_clicked)
        self.song_list.song_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.song_list.song_table.customContextMenuRequested.connect(self.show_song_context_menu)
        self.song_list.refresh_btn.clicked.connect(self.start_scan)
        self.song_list.locate_btn.clicked.connect(self.locate_current_song)
        content_splitter.addWidget(self.song_list)
        
        self.page_stack = QStackedWidget()
        self.track_panel = TrackControlPanel()
        self.track_panel.separate_btn.clicked.connect(self.separate_current_song)
        self.page_stack.addWidget(self.track_panel)
        self.lyrics_page = LyricsPage()
        self.page_stack.addWidget(self.lyrics_page)
        content_splitter.addWidget(self.page_stack)
        
        # 右侧面板已移除，只保留歌曲列表和主页面
        content_splitter.setSizes([350, 850])
        main_layout.addWidget(content_splitter, 1)
        
        player_bar = self._create_player_bar()
        main_layout.addWidget(player_bar)
        
    def _create_top_bar(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("🎵 Multi-Track Player")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)
        layout.addStretch()
        
        self.page_tracks_btn = QPushButton("🎚️ 音轨控制")
        self.page_tracks_btn.setCheckable(True)
        self.page_tracks_btn.setChecked(True)
        self.page_tracks_btn.setStyleSheet("QPushButton { background: #7c5ce0; color: white; border: none; border-radius: 8px; padding: 10px 20px; } QPushButton:checked { background: #5a3eb8; } QPushButton:hover { background: #9c7cf0; }")
        self.page_tracks_btn.clicked.connect(lambda: self.switch_page("tracks"))
        layout.addWidget(self.page_tracks_btn)
        
        self.page_lyrics_btn = QPushButton("🎤 歌词页面")
        self.page_lyrics_btn.setCheckable(True)
        self.page_lyrics_btn.setStyleSheet("QPushButton { background: #3a3a4a; color: white; border: none; border-radius: 8px; padding: 10px 20px; } QPushButton:checked { background: #5a3eb8; } QPushButton:hover { background: #4a4a5a; }")
        self.page_lyrics_btn.clicked.connect(lambda: self.switch_page("lyrics"))
        layout.addWidget(self.page_lyrics_btn)
        
        layout.addSpacing(20)
        
        self.mode_label = QLabel("模式: 单曲")
        self.mode_label.setStyleSheet("color: #a0a0a0; margin-right: 16px;")
        layout.addWidget(self.mode_label)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索歌曲... (Ctrl+F)")
        self.search_edit.setFixedWidth(250)
        self.search_edit.setStyleSheet("QLineEdit { background: #2a2a3a; border: 2px solid #3a3a4a; border-radius: 20px; padding: 10px 20px; color: #e0e0e0; } QLineEdit:focus { border-color: #7c5ce0; }")
        self.search_edit.textChanged.connect(self.on_search_changed)
        layout.addWidget(self.search_edit)
        
        online_btn = QPushButton("🌐 在线搜索")
        online_btn.setStyleSheet("QPushButton { background: #2d8a4e; color: white; border: none; border-radius: 8px; padding: 10px 20px; } QPushButton:hover { background: #3da05e; }")
        online_btn.clicked.connect(self.open_online_search)
        layout.addWidget(online_btn)
        
        source_btn = QPushButton("📦 音源管理")
        source_btn.setStyleSheet("QPushButton { background: #8b5cf6; color: white; border: none; border-radius: 8px; padding: 10px 20px; } QPushButton:hover { background: #a78bfa; }")
        source_btn.clicked.connect(self.open_source_manager)
        layout.addWidget(source_btn)
        
        msst_btn = QPushButton("✂️ MSST设置")
        msst_btn.setStyleSheet("QPushButton { background: #e85d04; color: white; border: none; border-radius: 8px; padding: 10px 20px; } QPushButton:hover { background: #f77f00; }")
        msst_btn.clicked.connect(self.open_msst_settings)
        layout.addWidget(msst_btn)
        
        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setStyleSheet("QPushButton { background: #2a2a3a; color: #e0e0e0; border: none; border-radius: 8px; padding: 10px 20px; } QPushButton:hover { background: #3a3a4a; }")
        settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(settings_btn)
        
        return widget
        

        
    def _create_player_bar(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("QWidget { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a2a3a, stop:1 #1a1a24); border-radius: 16px; }")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)
        
        progress_layout = QHBoxLayout()
        self.time_current = QLabel("0:00")
        self.time_current.setStyleSheet("color: #a0a0a0; font-size: 12px; min-width: 50px;")
        progress_layout.addWidget(self.time_current)
        
        self.progress_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setStyleSheet("QSlider::groove:horizontal { background: #3a3a4a; height: 8px; border-radius: 4px; } QSlider::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff6b9d, stop:1 #c44569); width: 20px; height: 20px; margin: -6px 0; border-radius: 10px; } QSlider::sub-page:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff6b9d, stop:1 #c44569); border-radius: 4px; }")
        self.progress_slider.sliderMoved.connect(self.seek_position)
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        progress_layout.addWidget(self.progress_slider)
        
        self.time_total = QLabel("0:00")
        self.time_total.setStyleSheet("color: #a0a0a0; font-size: 12px; min-width: 50px;")
        self.time_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        progress_layout.addWidget(self.time_total)
        layout.addLayout(progress_layout)
        
        controls_layout = QHBoxLayout()
        
        self.mode_btn = QPushButton("🔁")
        self.mode_btn.setFixedSize(40, 40)
        self.mode_btn.setToolTip("顺序播放")
        self.mode_btn.setStyleSheet("QPushButton { background: #3a3a4a; color: #e0e0e0; border: none; border-radius: 20px; } QPushButton:hover { background: #4a4a5a; }")
        self.mode_btn.clicked.connect(self.toggle_play_mode)
        controls_layout.addWidget(self.mode_btn)
        controls_layout.addStretch()
        
        btn_style = "QPushButton { background: #3a3a4a; color: #e0e0e0; border: none; border-radius: 24px; font-weight: bold; } QPushButton:hover { background: #4a4a5a; }"
        
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(48, 48)
        self.prev_btn.setStyleSheet(btn_style)
        self.prev_btn.clicked.connect(self.play_previous)
        controls_layout.addWidget(self.prev_btn)
        
        self.back_btn = QPushButton("-5s")
        self.back_btn.setFixedSize(48, 48)
        self.back_btn.setStyleSheet(btn_style)
        self.back_btn.clicked.connect(self.seek_backward)
        controls_layout.addWidget(self.back_btn)
        
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(64, 64)
        self.play_btn.setStyleSheet("QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7c5ce0, stop:1 #5a3eb8); color: white; border: none; border-radius: 32px; font-size: 24px; } QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9c7cf0, stop:1 #7a5ed8); }")
        self.play_btn.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_btn)
        
        self.forward_btn = QPushButton("+5s")
        self.forward_btn.setFixedSize(48, 48)
        self.forward_btn.setStyleSheet(btn_style)
        self.forward_btn.clicked.connect(self.seek_forward)
        controls_layout.addWidget(self.forward_btn)
        
        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(48, 48)
        self.next_btn.setStyleSheet(btn_style)
        self.next_btn.clicked.connect(self.play_next)
        controls_layout.addWidget(self.next_btn)
        
        controls_layout.addStretch()
        
        speed_layout = QHBoxLayout()
        speed_layout.setSpacing(8)
        speed_label = QLabel("速度:")
        speed_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        speed_layout.addWidget(speed_label)
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(25, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.setStyleSheet("QSlider::groove:horizontal { background: #3a3a4a; height: 6px; border-radius: 3px; } QSlider::handle:horizontal { background: #7c5ce0; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; } QSlider::sub-page:horizontal { background: #5a3eb8; border-radius: 3px; }")
        self.speed_slider.valueChanged.connect(self.on_speed_slider_changed)
        speed_layout.addWidget(self.speed_slider)
        
        self.speed_label = QLabel("1.00x")
        self.speed_label.setStyleSheet("color: #a0a0a0; font-size: 12px; min-width: 40px;")
        speed_layout.addWidget(self.speed_label)
        
        reset_btn = QPushButton("1x")
        reset_btn.setFixedSize(40, 28)
        reset_btn.setStyleSheet("QPushButton { background: #4a4a5a; color: #e0e0e0; border: none; border-radius: 6px; } QPushButton:hover { background: #5a5a6a; }")
        reset_btn.clicked.connect(lambda: self.speed_slider.setValue(100))
        speed_layout.addWidget(reset_btn)
        
        controls_layout.addLayout(speed_layout)
        layout.addLayout(controls_layout)
        
        return widget
        
    def switch_page(self, page: str):
        self.current_page = page
        if page == "tracks":
            self.page_stack.setCurrentIndex(0)
            self.page_tracks_btn.setChecked(True)
            self.page_lyrics_btn.setChecked(False)
        else:
            self.page_stack.setCurrentIndex(1)
            self.page_tracks_btn.setChecked(False)
            self.page_lyrics_btn.setChecked(True)
            
    def setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.seek_backward)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self.seek_forward)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, self.play_previous)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, self.play_next)
        QShortcut(QKeySequence("Ctrl+F"), self, self.focus_search)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.clear_search)
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self.switch_page("lyrics"))
        QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.switch_page("tracks"))
        
    def setup_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_progress)
        self.slider_being_dragged = False
        
    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()
        
    def clear_search(self):
        self.search_edit.clear()
        self.search_edit.clearFocus()
        
    def on_search_changed(self, text: str):
        self.song_list.song_model.set_filter(text)
        self.song_list.update_count(self.song_list.song_model.rowCount())
        
    def load_songs_with_cache(self):
        """尝试从缓存加载歌曲，如果缓存无效则扫描"""
        music_path = self.config.get('music_path', '')
        stems_path = self.config.get('stems_path', '')
        
        if not music_path:
            return
            
        # 尝试从缓存加载
        cached_songs = self.song_cache.load_cache(music_path, stems_path)
        
        if cached_songs:
            # 使用缓存的歌曲列表
            self.songs = cached_songs
            self.song_list.song_model.set_songs(self.songs)
            self.song_list.update_count(len(self.songs))
            self.shuffle_order = list(range(len(self.songs)))
            random.shuffle(self.shuffle_order)
            self.shuffle_index = 0
            self.recommendation_provider.set_song_pool([
                {'path': s.path, 'title': s.title, 'artist': s.artist} 
                for s in self.songs
            ])
            # 后台更新stems状态
            self.song_cache.update_stems_status(self.songs, stems_path)
            self.song_list.song_model.set_songs(self.songs)
        else:
            # 缓存无效，重新扫描
            self.start_scan()
        
    def start_scan(self):
        if self.scanner and self.scanner.isRunning():
            self.scanner.stop()
            self.scanner.wait()
        self.song_list.song_model.set_songs([])
        self.songs.clear()
        self.song_list.scan_progress.setVisible(True)
        self.song_list.scan_progress.setValue(0)
        self.scanner = SongScanner(self.config.get('music_path', ''), self.config.get('stems_path', ''))
        self.scanner.progress.connect(self.on_scan_progress)
        self.scanner.song_found.connect(self.on_song_found)
        self.scanner.finished_scan.connect(self.on_scan_finished)
        self.scanner.start()
        
    def on_scan_progress(self, current: int, total: int):
        if total > 0:
            self.song_list.scan_progress.setMaximum(total)
            self.song_list.scan_progress.setValue(current)
            
    def on_song_found(self, song: SongInfo):
        self.song_list.song_model.add_song(song)
        self.songs.append(song)
        self.song_list.update_count(len(self.songs))
        
    def on_scan_finished(self, songs: List[SongInfo]):
        self.song_list.scan_progress.setVisible(False)
        self.songs = songs
        self.shuffle_order = list(range(len(self.songs)))
        random.shuffle(self.shuffle_order)
        self.shuffle_index = 0
        self.song_list.update_count(len(self.songs))
        self.recommendation_provider.set_song_pool([{'path': s.path, 'title': s.title, 'artist': s.artist} for s in self.songs])
        # 保存缓存
        self.song_cache.save_cache(
            self.songs, 
            self.config.get('music_path', ''), 
            self.config.get('stems_path', '')
        )
        
    def show_song_context_menu(self, pos: QPoint):
        index = self.song_list.song_table.indexAt(pos)
        if not index.isValid():
            return
        song = self.song_list.song_model.get_song(index.row())
        if not song:
            return
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: #2a2a3a; color: #e0e0e0; border: 1px solid #3a3a4a; border-radius: 8px; padding: 8px; } QMenu::item { padding: 8px 24px; } QMenu::item:selected { background: #7c5ce0; }")
        play_action = menu.addAction("▶️ 播放")
        play_action.triggered.connect(lambda: self.play_song_at_index(index.row()))
        menu.addSeparator()
        if song.has_stems:
            stems_action = menu.addAction("🎚️ 播放分离音轨")
            stems_action.triggered.connect(lambda: self.play_stems(song))
        else:
            separate_action = menu.addAction("✂️ 分离音轨")
            separate_action.triggered.connect(lambda: self.separate_song(song))
        menu.addSeparator()
        open_folder_action = menu.addAction("📂 在资源管理器中打开")
        open_folder_action.triggered.connect(lambda: self.open_in_explorer(song.path))
        menu.exec(self.song_list.song_table.mapToGlobal(pos))
        
    def open_in_explorer(self, path: str):
        import subprocess
        if sys.platform == 'win32':
            subprocess.run(['explorer', '/select,', os.path.normpath(path)])
        elif sys.platform == 'darwin':
            subprocess.run(['open', '-R', path])
        else:
            subprocess.run(['xdg-open', os.path.dirname(path)])
            
    def on_song_double_clicked(self, index: QModelIndex):
        self.play_song_at_index(index.row())
        
    def play_song_at_index(self, index: int):
        song = self.song_list.song_model.get_song(index)
        if song:
            self.play_song(song)
            
    def play_song(self, song: SongInfo):
        self.stop_all_tracks()
        self.cleanup_tracks()
        self.current_song = song
        self.current_song_index = self.songs.index(song) if song in self.songs else -1
        self.mode = "single"
        self.mode_label.setText("模式: 单曲")
        self.track_panel.set_current_song(song.title)
        self.lyrics_page.set_song(song.title, song.artist, song.album)
        self.lyrics_page.set_cover(song.cover_data)
        self.lyrics_page.set_lyrics(song.lyrics)
        if song.has_stems:
            self.track_panel.separate_btn.setText("🎚️ 播放分离音轨")
        else:
            self.track_panel.separate_btn.setText("✂️ 一键分离音轨")
        self.track_panel.separate_btn.setEnabled(True)
        self.track_panel.separate_status.setText("")
        tc = self.track_panel.add_track(song.path)
        tc.set_playback_rate(self.playback_rate)
        self.track_controls.append(tc)
        tc.setup_player()
        # pygame 模式下 tc.player 为 None，需要检查
        if tc.player is not None:
            tc.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.play_all_tracks()
        self.is_playing = True
        self.play_btn.setText("⏸")
        self.update_timer.start(100)
        
    def play_stems(self, song: SongInfo):
        if not song.has_stems or not song.stems_path:
            QMessageBox.warning(self, "提示", "该歌曲没有分离音轨")
            return
        self.stop_all_tracks()
        self.cleanup_tracks()
        self.current_song = song
        self.mode = "stems"
        self.mode_label.setText("模式: 多音轨")
        self.track_panel.set_current_song(f"{song.title} (分离音轨)")
        self.lyrics_page.set_song(song.title, song.artist, song.album)
        self.lyrics_page.set_cover(song.cover_data)
        self.lyrics_page.set_lyrics(song.lyrics)
        self.track_panel.separate_btn.setText("🔙 返回单曲模式")
        self.track_panel.separate_btn.setEnabled(True)
        self.track_panel.separate_status.setText("")
        audio_files = sorted([os.path.join(song.stems_path, f) for f in os.listdir(song.stems_path) if f.lower().endswith(tuple(SUPPORTED_FORMATS))])
        for audio_path in audio_files:
            tc = self.track_panel.add_track(audio_path)
            tc.set_playback_rate(self.playback_rate)
            self.track_controls.append(tc)
        # 修复：为所有音轨初始化播放器，而不仅仅是第一个
        for i, tc in enumerate(self.track_controls):
            tc.setup_player()
            # 只对第一个音轨连接媒体状态变化信号（用于检测播放结束）
            # 注意：pygame 模式下 tc.player 为 None，需要检查
            if i == 0 and tc.player is not None:
                tc.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.play_all_tracks()
        self.is_playing = True
        self.play_btn.setText("⏸")
        self.update_timer.start(100)
        
    def separate_current_song(self):
        if not self.current_song:
            return
        if self.mode == "stems":
            self.play_song(self.current_song)
        elif self.current_song.has_stems:
            self.play_stems(self.current_song)
        else:
            self.separate_song(self.current_song)
            
    def separate_song(self, song: SongInfo):
        msst_path = self.config.get('msst_path', '')
        stems_path = self.config.get('stems_path', '')
        config_path = self.config.get('config_path', '')
        model_path = self.config.get('model_path', '')
        model_type = self.config.get('model_type', 'bs_roformer')
        output_format = self.config.get('output_format', 'wav')
        python_path = self.config.get('msst_python_path', '')
        # 压缩设置
        compress_output = self.config.get('compress_stems', True)
        compress_bitrate = self.config.get('compress_bitrate', '64k')
        compress_format = self.config.get('compress_format', 'm4a')
        
        if not msst_path or not os.path.exists(msst_path):
            QMessageBox.warning(self, "MSST未配置", "请先在MSST设置中配置MSST WebUI的路径")
            self.open_msst_settings()
            return
        if not python_path or not os.path.exists(python_path):
            QMessageBox.warning(self, "Python路径未配置", "请先在MSST设置中配置Python解释器路径\n\n这应该是MSST虚拟环境中的python.exe")
            self.open_msst_settings()
            return
        if not stems_path:
            QMessageBox.warning(self, "输出路径未配置", "请先在MSST设置中配置分离音轨的保存路径")
            self.open_msst_settings()
            return
        if not config_path or not os.path.exists(config_path):
            QMessageBox.warning(self, "配置文件未设置", "请先在MSST设置中选择模型配置文件(*.yaml)")
            self.open_msst_settings()
            return
        if not model_path or not os.path.exists(model_path):
            QMessageBox.warning(self, "模型文件未设置", "请先在MSST设置中选择模型权重文件(*.ckpt)")
            self.open_msst_settings()
            return
        song_name = Path(song.filename).stem
        output_dir = os.path.join(stems_path, song_name)
        os.makedirs(output_dir, exist_ok=True)
        self.track_panel.separate_btn.setEnabled(False)
        self.track_panel.separate_btn.setText("⏳ 正在分离...")
        self.track_panel.separate_status.setText("正在初始化...")
        self.separator_thread = MSSTSeparatorThread(
            msst_path, song.path, output_dir, model_type, 
            config_path, model_path, output_format, python_path,
            compress_output, compress_bitrate, compress_format
        )
        self.separator_thread.progress.connect(self._on_separate_progress)
        self.separator_thread.finished.connect(lambda s, m, p: self._on_separate_finished(song, s, m, p))
        self.separator_thread.start()
        
    def _on_separate_progress(self, message: str):
        self.track_panel.separate_status.setText(message)
        
    def _on_separate_finished(self, song: SongInfo, success: bool, message: str, output_path: str):
        self.track_panel.separate_btn.setEnabled(True)
        if success:
            song.has_stems = True
            song.stems_path = output_path
            self.song_list.song_model.update_song(song)
            self.track_panel.separate_btn.setText("🎚️ 播放分离音轨")
            self.track_panel.separate_status.setText(f"✅ {message}")
            # 更新缓存
            self.song_cache.save_cache(
                self.songs,
                self.config.get('music_path', ''),
                self.config.get('stems_path', '')
            )
            reply = QMessageBox.question(self, "分离完成", f"音轨分离完成!\n保存位置: {output_path}\n\n是否现在播放分离后的音轨?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.play_stems(song)
        else:
            self.track_panel.separate_btn.setText("✂️ 一键分离音轨")
            self.track_panel.separate_status.setText(f"❌ {message}")
            QMessageBox.warning(self, "分离失败", message)
            
    def cleanup_tracks(self):
        # 停止同步监控
        self.track_panel.get_sync_manager().stop_sync_monitoring()
        for tc in self.track_controls:
            tc.cleanup()
            tc.deleteLater()
        self.track_controls.clear()
        self.track_panel.clear_tracks()
        
    def play_all_tracks(self):
        """同步播放所有音轨 - 修复版"""
        if not self.track_controls:
            return
            
        # 使用同步管理器播放
        sync_manager = self.track_panel.get_sync_manager()
        
        if len(self.track_controls) > 1:
            # 多音轨模式：使用同步播放
            sync_manager.play_all_synced()
            # 启动同步监控，确保长时间播放时保持同步
            sync_manager.start_sync_monitoring()
        else:
            # 单音轨模式：直接播放
            self.track_controls[0].play()
            
    def pause_all_tracks(self):
        """同步暂停所有音轨"""
        sync_manager = self.track_panel.get_sync_manager()
        sync_manager.pause_all()
        sync_manager.stop_sync_monitoring()
            
    def stop_all_tracks(self):
        """停止所有音轨"""
        sync_manager = self.track_panel.get_sync_manager()
        sync_manager.stop_all()
        sync_manager.stop_sync_monitoring()
            
    def toggle_play(self):
        if not self.track_controls:
            if self.song_list.song_model.rowCount() > 0:
                self.play_song_at_index(0)
            return
        if self.is_playing:
            self.pause_all_tracks()
            self.play_btn.setText("▶")
            self.update_timer.stop()
        else:
            self.play_all_tracks()
            self.play_btn.setText("⏸")
            self.update_timer.start(100)
        self.is_playing = not self.is_playing
        
    def stop_playback(self):
        self.stop_all_tracks()
        self.is_playing = False
        self.play_btn.setText("▶")
        self.update_timer.stop()
        self.progress_slider.setValue(0)
        self.time_current.setText("0:00")
        
    def play_next(self):
        if not self.songs:
            return
        if self.play_mode == "shuffle":
            self.shuffle_index += 1
            if self.shuffle_index >= len(self.shuffle_order):
                random.shuffle(self.shuffle_order)
                self.shuffle_index = 0
            next_song = self.songs[self.shuffle_order[self.shuffle_index]]
        else:
            next_index = (self.current_song_index + 1) % len(self.songs)
            next_song = self.songs[next_index]
        self.play_song(next_song)
        
    def play_previous(self):
        if not self.songs:
            return
        if self.play_mode == "shuffle":
            self.shuffle_index -= 1
            if self.shuffle_index < 0:
                self.shuffle_index = len(self.shuffle_order) - 1
            prev_song = self.songs[self.shuffle_order[self.shuffle_index]]
        else:
            prev_index = (self.current_song_index - 1) % len(self.songs)
            prev_song = self.songs[prev_index]
        self.play_song(prev_song)
        
    def seek_forward(self):
        if self.track_controls:
            current_pos = self.track_controls[0].get_position()
            duration = self.track_controls[0].get_duration()
            new_pos = min(current_pos + 5000, duration)
            self.set_all_positions(new_pos)
            # 如果在播放中，恢复播放
            if self.is_playing:
                sync_manager = self.track_panel.get_sync_manager()
                sync_manager.resume_all()
            
    def seek_backward(self):
        if self.track_controls:
            current_pos = self.track_controls[0].get_position()
            new_pos = max(0, current_pos - 5000)
            self.set_all_positions(new_pos)
            # 如果在播放中，恢复播放
            if self.is_playing:
                sync_manager = self.track_panel.get_sync_manager()
                sync_manager.resume_all()
            
    def seek_position(self, value):
        """拖动时只记录目标位置，不实时设置（避免卡顿）"""
        if self.slider_being_dragged:
            # 拖动时只更新时间显示，不实际seek
            if self.track_controls:
                duration = self.track_controls[0].get_duration()
                if duration > 0:
                    preview_pos = int((value / 1000.0) * duration)
                    self.time_current.setText(self.format_time(preview_pos))
                    self.seek_pending = True
                    self.seek_value = value
        else:
            # 点击时直接跳转
            if self.track_controls:
                duration = self.track_controls[0].get_duration()
                if duration > 0:
                    target_position = int((value / 1000.0) * duration)
                    self.set_all_positions(target_position)
                    # 如果在播放中，恢复播放
                    if self.is_playing:
                        sync_manager = self.track_panel.get_sync_manager()
                        sync_manager.resume_all()
                        sync_manager.start_sync_monitoring()
                
    def on_slider_pressed(self):
        self.slider_being_dragged = True
        # 暂时暂停播放以避免卡顿
        if self.is_playing:
            sync_manager = self.track_panel.get_sync_manager()
            sync_manager.pause_all()
            sync_manager.stop_sync_monitoring()
        
    def on_slider_released(self):
        self.slider_being_dragged = False
        # 执行最终的seek
        if self.seek_pending:
            value = self.seek_value
            self.seek_pending = False
            if self.track_controls:
                duration = self.track_controls[0].get_duration()
                if duration > 0:
                    target_position = int((value / 1000.0) * duration)
                    # set_all_positions 现在会自动处理暂停/恢复
                    self.set_all_positions(target_position)
        # 如果之前在播放，恢复播放
        if self.is_playing:
            sync_manager = self.track_panel.get_sync_manager()
            sync_manager.resume_all()
            sync_manager.start_sync_monitoring()
                
    def set_all_positions(self, position: int):
        """同步设置所有音轨位置 - 修复版"""
        sync_manager = self.track_panel.get_sync_manager()
        
        # 暂停同步监控
        sync_manager.stop_sync_monitoring()
        
        # 同步设置位置（这会自动处理 pygame 和 QMediaPlayer）
        sync_manager.set_all_positions_synced(position)
            
    def update_progress(self):
        if not self.track_controls or self.slider_being_dragged:
            return
        tc = self.track_controls[0]
        position = tc.get_position()
        duration = tc.get_duration()
        if duration > 0:
            self.progress_slider.setValue(int((position / duration) * 1000))
        self.time_current.setText(self.format_time(position))
        self.time_total.setText(self.format_time(duration))
        self.lyrics_page.update_position(position)
        
    def format_time(self, ms: int) -> str:
        seconds = ms // 1000
        return f"{seconds // 60}:{seconds % 60:02d}"
        
    def toggle_play_mode(self):
        modes = ["sequential", "shuffle", "repeat_one"]
        icons = ["🔁", "🔀", "🔂"]
        tips = ["顺序播放", "随机播放", "单曲循环"]
        current_idx = modes.index(self.play_mode)
        next_idx = (current_idx + 1) % len(modes)
        self.play_mode = modes[next_idx]
        self.mode_btn.setText(icons[next_idx])
        self.mode_btn.setToolTip(tips[next_idx])
        if self.play_mode == "shuffle":
            random.shuffle(self.shuffle_order)
            self.shuffle_index = 0
            
    def on_speed_slider_changed(self, value: int):
        self.playback_rate = value / 100.0
        self.speed_label.setText(f"{self.playback_rate:.2f}x")
        # 使用同步管理器设置所有音轨的播放速率
        sync_manager = self.track_panel.get_sync_manager()
        sync_manager.set_playback_rate_all(self.playback_rate)
            
    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.on_song_ended()
            
    def on_song_ended(self):
        if self.play_mode == "repeat_one" and self.current_song:
            self.play_song(self.current_song)
        elif self.play_mode == "shuffle":
            self.play_next()
        elif self.current_song_index < len(self.songs) - 1:
            self.play_next()
        else:
            self.stop_playback()
            
    def open_online_search(self):
        dialog = OnlineSearchDialog(self.lx_client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            online_song = dialog.get_selected_song()
            quality = dialog.get_selected_quality()
            if online_song:
                self._play_online_song(online_song, quality)
                
    def _play_online_song(self, online_song, quality: str = '320k'):
        # 按优先级尝试获取播放链接
        qualities_to_try = [quality, '320k', '128k', 'flac']
        # 去重并保持顺序
        seen = set()
        qualities_to_try = [q for q in qualities_to_try if not (q in seen or seen.add(q))]
        
        url = None
        for q in qualities_to_try:
            url = self.lx_client.get_music_url(online_song, q)
            if url:
                break
                
        if not url:
            QMessageBox.warning(self, "播放失败", "无法获取歌曲播放链接\n\n可能原因:\n1. 该歌曲暂无可用音源\n2. API服务不可用\n3. 网络连接问题")
            return
            
        song = SongInfo(
            path=url, 
            filename=f"{online_song.name}.mp3", 
            title=online_song.name, 
            artist=online_song.artist, 
            album=online_song.album, 
            duration=online_song.duration, 
            is_online=True, 
            online_url=url, 
            source=online_song.source, 
            song_id=online_song.song_id
        )
        
        # 获取封面
        cover = self.lx_client.get_pic(online_song)
        if cover:
            song.cover_data = cover
            
        # 获取歌词
        lyrics = self.lx_client.get_lyric(online_song)
        if lyrics:
            song.lyrics = lyrics
            
        self.play_song(song)
                
    def open_source_manager(self):
        """打开自定义音源管理对话框"""
        dialog = CustomSourceDialog(self.source_manager, self)
        dialog.exec()
        # 如果有活动音源，更新API客户端配置
        active_source = self.source_manager.get_active_source()
        if active_source:
            config = self.source_manager.get_api_config(active_source.name)
            if config.get('api_url'):
                self.lx_client.set_api_url(config['api_url'])
            if config.get('api_key'):
                self.lx_client.set_api_key(config['api_key'])
                
    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            old_music_path = self.config.get('music_path', '')
            old_stems_path = self.config.get('stems_path', '')
            self.config = dialog.get_config()
            self._save_config()
            # 只有当音乐路径改变时才提示用户手动刷新
            if old_music_path != self.config.get('music_path', '') or old_stems_path != self.config.get('stems_path', ''):
                QMessageBox.information(self, "路径已更改", "音乐文件夹已更改，请点击刷新按钮重新扫描歌曲列表")
            
    def open_msst_settings(self):
        dialog = MSSTDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config.update(dialog.get_config())
            self._save_config()
    
    def locate_current_song(self):
        """定位当前播放的歌曲在列表中的位置"""
        if not self.current_song:
            QMessageBox.information(self, "提示", "当前没有播放的歌曲")
            return
        
        # 清除搜索过滤（如果有的话）
        if self.search_edit.text():
            self.search_edit.clear()
        
        # 查找当前歌曲在列表中的索引
        song_index = -1
        for i, song in enumerate(self.songs):
            if song.path == self.current_song.path:
                song_index = i
                break
        
        if song_index >= 0:
            # 滚动到该歌曲
            self.song_list.scroll_to_song(song_index)
        else:
            QMessageBox.information(self, "提示", "当前歌曲不在列表中")
            
    def closeEvent(self, event):
        self.stop_all_tracks()
        self.cleanup_tracks()
        if self.scanner and self.scanner.isRunning():
            self.scanner.stop()
            self.scanner.wait()
        self.recommendation_server.stop()
        event.accept()
