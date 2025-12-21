#!/usr/bin/env python3
"""
Multi-Track Audio Player v3.0
高性能多音轨音乐播放器

功能特性:
- 双页面UI: 音轨控制页 + 精美歌词页
- 支持MSST音轨分离
- 嵌入式歌词和封面显示
- 歌曲推荐系统接口
- 落雪音乐在线播放接口
- 可折叠歌曲列表
- 滑动条调速
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPalette
from ui.main_window import MultiTrackPlayer


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 暗色主题
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(18, 18, 26))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.Base, QColor(26, 26, 36))
    palette.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.Button, QColor(42, 42, 58))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(124, 92, 224))
    app.setPalette(palette)
    
    window = MultiTrackPlayer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
