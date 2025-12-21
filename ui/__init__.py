"""
UI模块
"""

from .main_window import MultiTrackPlayer
from .track_control import TrackControl, TrackControlPanel
from .lyrics_page import LyricsPage, SimpleLyricsWidget, CoverWidget
from .dialogs import SettingsDialog, MSSTDialog, OnlineSearchDialog

__all__ = [
    'MultiTrackPlayer',
    'TrackControl',
    'TrackControlPanel',
    'LyricsPage',
    'SimpleLyricsWidget',
    'CoverWidget',
    'SettingsDialog',
    'MSSTDialog',
    'OnlineSearchDialog'
]
