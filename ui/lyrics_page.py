"""
精美歌词显示页面
"""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QPainter, QBrush, QColor, QPainterPath

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.models import LyricLine, LyricsParser


class CoverWidget(QFrame):
    """专辑封面显示组件"""
    
    def __init__(self, size: int = 280, parent=None):
        super().__init__(parent)
        self.cover_size = size
        self.setup_ui()
        
    def setup_ui(self):
        self.setFixedSize(self.cover_size, self.cover_size)
        self.setStyleSheet(f"""
            QFrame {{ 
                background: #2a2a3a; 
                border-radius: {self.cover_size // 8}px; 
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(self.cover_size, self.cover_size)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(f"""
            QLabel {{ 
                background: #2a2a3a; 
                border-radius: {self.cover_size // 8}px; 
                font-size: 72px; 
            }}
        """)
        self.cover_label.setText("🎵")
        layout.addWidget(self.cover_label)
        
    def set_cover(self, cover_data: bytes):
        """设置封面图片"""
        if cover_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(cover_data):
                # 创建圆角图片
                rounded = self._create_rounded_pixmap(pixmap)
                self.cover_label.setPixmap(rounded)
                return
        self.cover_label.setText("🎵")
        self.cover_label.setPixmap(QPixmap())
        
    def _create_rounded_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """创建圆角图片"""
        size = self.cover_size
        scaled = pixmap.scaled(size, size, 
                              Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                              Qt.TransformationMode.SmoothTransformation)
        
        # 居中裁剪
        x = (scaled.width() - size) // 2
        y = (scaled.height() - size) // 2
        cropped = scaled.copy(x, y, size, size)
        
        # 创建圆角
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        radius = size // 8
        path.addRoundedRect(0, 0, size, size, radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        
        return rounded


class LyricLineWidget(QLabel):
    """单行歌词组件"""
    
    def __init__(self, text: str, translation: str = "", parent=None):
        super().__init__(parent)
        self.main_text = text
        self.translation = translation
        self.is_current = False
        self._setup()
        
    def _setup(self):
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumHeight(40)  # 确保最小高度
        self._update_display()
        
    def _update_display(self):
        if self.is_current:
            font_size = 24
            color = "#ffffff"
            weight = "bold"
            min_height = 60
        else:
            font_size = 16
            color = "#808080"
            weight = "normal"
            min_height = 40
            
        text = self.main_text
        if self.translation:
            text += f"\n<span style='font-size: {font_size - 4}px; color: #a0a0a0;'>{self.translation}</span>"
            min_height += 24
            
        self.setMinimumHeight(min_height)
        self.setStyleSheet(f"""
            QLabel {{ 
                color: {color}; 
                font-size: {font_size}px; 
                font-weight: {weight};
                padding: 12px 20px;
                margin: 4px 0px;
                background: transparent;
                line-height: 1.4;
            }}
        """)
        self.setText(text if not self.translation else "")
        if self.translation:
            self.setText(f"{self.main_text}\n{self.translation}")
        
    def set_current(self, is_current: bool):
        if self.is_current != is_current:
            self.is_current = is_current
            self._update_display()


class LyricsDisplayWidget(QFrame):
    """歌词显示组件 - 逐句滚动"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lyrics_lines: List[LyricLine] = []
        self.line_widgets: List[LyricLineWidget] = []
        self.current_line_index = -1
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea { 
                background: transparent; 
                border: none; 
            }
        """)
        
        # 歌词容器
        self.lyrics_container = QWidget()
        self.lyrics_container.setStyleSheet("background: transparent;")
        self.lyrics_layout = QVBoxLayout(self.lyrics_container)
        self.lyrics_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_layout.setSpacing(8)
        self.lyrics_layout.setContentsMargins(20, 150, 20, 150)  # 增加上下边距确保滚动时歌词不被截断
        
        self.scroll_area.setWidget(self.lyrics_container)
        layout.addWidget(self.scroll_area)
        
        # 无歌词提示
        self.no_lyrics_label = QLabel("暂无歌词")
        self.no_lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_lyrics_label.setStyleSheet("color: #606060; font-size: 18px;")
        self.no_lyrics_label.setVisible(True)
        self.lyrics_layout.addWidget(self.no_lyrics_label)
        
    def set_lyrics(self, lyrics_text: str):
        """设置歌词"""
        # 清除旧歌词
        self._clear_lyrics()
        
        if not lyrics_text:
            self.no_lyrics_label.setVisible(True)
            return
            
        self.lyrics_lines = LyricsParser.parse(lyrics_text)
        
        if not self.lyrics_lines:
            self.no_lyrics_label.setVisible(True)
            return
            
        self.no_lyrics_label.setVisible(False)
        
        # 创建歌词行
        for line in self.lyrics_lines:
            widget = LyricLineWidget(line.text, line.translation)
            self.line_widgets.append(widget)
            self.lyrics_layout.addWidget(widget)
            
        self.current_line_index = -1
        
    def _clear_lyrics(self):
        """清除歌词"""
        for widget in self.line_widgets:
            widget.deleteLater()
        self.line_widgets.clear()
        self.lyrics_lines.clear()
        self.current_line_index = -1
        
    def update_position(self, position_ms: int):
        """更新播放位置，滚动到当前歌词"""
        if not self.lyrics_lines:
            return
            
        position_sec = position_ms / 1000.0
        
        # 找到当前歌词行
        new_index = -1
        for i, line in enumerate(self.lyrics_lines):
            if line.time <= position_sec:
                new_index = i
            else:
                break
                
        if new_index != self.current_line_index and new_index >= 0:
            # 更新高亮
            if 0 <= self.current_line_index < len(self.line_widgets):
                self.line_widgets[self.current_line_index].set_current(False)
                
            self.current_line_index = new_index
            
            if 0 <= new_index < len(self.line_widgets):
                self.line_widgets[new_index].set_current(True)
                # 滚动到当前行
                self._scroll_to_line(new_index)
                
    def _scroll_to_line(self, index: int):
        """滚动到指定行"""
        if 0 <= index < len(self.line_widgets):
            widget = self.line_widgets[index]
            # 计算目标位置（居中显示）
            viewport_height = self.scroll_area.viewport().height()
            widget_pos = widget.pos().y()
            widget_height = widget.height()
            target_y = widget_pos - (viewport_height - widget_height) // 2
            
            # 平滑滚动
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.setValue(max(0, target_y))


class LyricsPage(QWidget):
    """精美歌词页面 - 完整页面布局"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QWidget { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #1a1a24, stop:0.5 #12121a, stop:1 #0a0a10); 
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        # 顶部：封面和歌曲信息
        top_layout = QHBoxLayout()
        top_layout.setSpacing(40)
        
        # 封面
        self.cover_widget = CoverWidget(280)
        top_layout.addWidget(self.cover_widget)
        
        # 歌曲信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(12)
        info_layout.addStretch()
        
        self.title_label = QLabel("--")
        self.title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #ffffff;")
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)
        
        self.artist_label = QLabel("--")
        self.artist_label.setFont(QFont("Segoe UI", 18))
        self.artist_label.setStyleSheet("color: #a0a0a0;")
        info_layout.addWidget(self.artist_label)
        
        self.album_label = QLabel("")
        self.album_label.setFont(QFont("Segoe UI", 14))
        self.album_label.setStyleSheet("color: #707070;")
        info_layout.addWidget(self.album_label)
        
        info_layout.addStretch()
        top_layout.addLayout(info_layout, 1)
        
        layout.addLayout(top_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: #3a3a4a;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        
        # 歌词显示
        self.lyrics_widget = LyricsDisplayWidget()
        layout.addWidget(self.lyrics_widget, 1)
        
    def set_song(self, title: str, artist: str, album: str = ""):
        """设置歌曲信息"""
        self.title_label.setText(title)
        self.artist_label.setText(artist)
        self.album_label.setText(album)
        
    def set_cover(self, cover_data: bytes):
        """设置封面"""
        self.cover_widget.set_cover(cover_data)
        
    def set_lyrics(self, lyrics_text: str):
        """设置歌词"""
        self.lyrics_widget.set_lyrics(lyrics_text)
        
    def update_position(self, position_ms: int):
        """更新播放位置"""
        self.lyrics_widget.update_position(position_ms)


class SimpleLyricsWidget(QFrame):
    """简单歌词显示组件（用于侧边栏）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lyrics_lines: List[LyricLine] = []
        self.current_line = -1
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("QFrame { background: #1a1a24; border-radius: 12px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel("🎤 歌词")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)
        
        from PyQt6.QtWidgets import QTextEdit
        self.lyrics_text = QTextEdit()
        self.lyrics_text.setReadOnly(True)
        self.lyrics_text.setStyleSheet("""
            QTextEdit { 
                background: transparent; 
                color: #a0a0a0; 
                border: none; 
                font-size: 14px; 
            }
        """)
        layout.addWidget(self.lyrics_text)
        
    def set_lyrics(self, lyrics: str):
        """设置歌词"""
        self.lyrics_text.clear()
        if not lyrics:
            self.lyrics_text.setPlainText("暂无歌词")
            self.lyrics_lines = []
            return
            
        self.lyrics_lines = LyricsParser.parse(lyrics)
        if self.lyrics_lines:
            display_text = "\n".join([line.text for line in self.lyrics_lines])
        else:
            display_text = lyrics
        self.lyrics_text.setPlainText(display_text)
        
    def update_position(self, position_ms: int):
        """更新位置（简单版本不做滚动）"""
        pass
