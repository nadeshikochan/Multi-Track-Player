"""
音轨控制组件 - 完整修复版 v5

修复问题：
1. 多音轨同步播放 - 使用 pygame.mixer 多通道混音
2. 进度条拖动同步 - 统一seek操作，确保所有音轨完美同步
3. 音量持久化 - 保存音量设置到 QSettings
4. 播放位置追踪 - 使用定时器追踪播放位置
5. 播放结束检测 - 自动检测播放结束以支持自动播放下一首
"""

import os
import time
import threading
from typing import Optional, List, Dict, Callable
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
    QSlider, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QUrl, QSettings, QObject, QRunnable, QThreadPool
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

# 尝试导入 pygame
try:
    import pygame
    import pygame.mixer
    PYGAME_AVAILABLE = True
    print("[音频引擎] pygame 可用，将使用混音器模式")
except ImportError:
    PYGAME_AVAILABLE = False
    print("[音频引擎] pygame 未安装，使用 QMediaPlayer 模式")

# 尝试导入预加载模块
try:
    from core.audio_preloader import get_audio_cache, CachedAudio, PYDUB_AVAILABLE
    PRELOADER_AVAILABLE = True
except ImportError:
    PRELOADER_AVAILABLE = False
    PYDUB_AVAILABLE = False

# pydub
if not PRELOADER_AVAILABLE:
    try:
        from pydub import AudioSegment
        PYDUB_AVAILABLE = True
    except ImportError:
        PYDUB_AVAILABLE = False
else:
    try:
        from pydub import AudioSegment
    except ImportError:
        pass


# ============================================================
# 音量设置管理器
# ============================================================

class VolumeSettings:
    """管理音轨音量的持久化存储"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.settings = QSettings("MultiTrackPlayer", "TrackVolumes")
        self._initialized = True
    
    def get_volume(self, track_name: str) -> int:
        return int(self.settings.value(f"volume/{track_name}", 80))
    
    def set_volume(self, track_name: str, volume: int):
        self.settings.setValue(f"volume/{track_name}", volume)
    
    def get_muted(self, track_name: str) -> bool:
        return self.settings.value(f"muted/{track_name}", False, type=bool)
    
    def set_muted(self, track_name: str, muted: bool):
        self.settings.setValue(f"muted/{track_name}", muted)


def get_volume_settings() -> VolumeSettings:
    return VolumeSettings()


class ClickableVolumeSlider(QSlider):
    """可点击的音量滑块"""
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.orientation() == Qt.Orientation.Horizontal:
                value = self.minimum() + (self.maximum() - self.minimum()) * event.pos().x() / self.width()
            else:
                value = self.minimum() + (self.maximum() - self.minimum()) * (1 - event.pos().y() / self.height())
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
        super().mousePressEvent(event)


# ============================================================
# Pygame 混音引擎 - 改进版
# ============================================================

class PygameMixerEngine:
    """Pygame 混音引擎 - 单例模式，支持多音轨同步"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._lock = threading.Lock()
        
        self.sounds: Dict[int, 'pygame.mixer.Sound'] = {}
        self.channels: Dict[int, 'pygame.mixer.Channel'] = {}
        self.volumes: Dict[int, float] = {}
        self.file_paths: Dict[int, str] = {}
        self.duration_ms: int = 0
        self.is_playing: bool = False
        self._mixer_ready = False
        
        self.audio_segments: Dict[int, 'AudioSegment'] = {}
        self._current_sounds: Dict[int, 'pygame.mixer.Sound'] = {}
        
        self._play_start_time: float = 0
        self._play_offset_ms: int = 0
        self._paused_position_ms: int = 0
        self._is_paused: bool = False
        
        self._initialized = True
        
    def init_mixer(self) -> bool:
        if self._mixer_ready:
            return True
        
        if not PYGAME_AVAILABLE:
            return False
        
        try:
            if not pygame.get_init():
                pygame.init()
            
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
            
            pygame.mixer.set_num_channels(32)
            self._mixer_ready = True
            return True
        except Exception as e:
            print(f"[PygameMixer] 初始化失败: {e}")
            return False
    
    def load_track(self, track_id: int, file_path: str) -> bool:
        if not self.init_mixer():
            return False
        
        print(f"[PygameMixer] 开始加载: {os.path.basename(file_path)}")
        
        with self._lock:
            try:
                # 优先从缓存获取
                if PRELOADER_AVAILABLE:
                    cache = get_audio_cache()
                    cached = cache.get(file_path)
                    
                    if cached and cached.sound:
                        print(f"[PygameMixer] 从缓存加载成功")
                        self.sounds[track_id] = cached.sound
                        self.file_paths[track_id] = file_path
                        self.volumes[track_id] = 0.8
                        
                        if cached.audio_segment:
                            self.audio_segments[track_id] = cached.audio_segment
                        
                        if cached.duration_ms > self.duration_ms:
                            self.duration_ms = cached.duration_ms
                        
                        self.channels[track_id] = pygame.mixer.Channel(track_id)
                        return True
                
                # 检查文件格式 - pygame对某些格式支持不好
                file_ext = os.path.splitext(file_path)[1].lower()
                
                # 对于FLAC和某些格式，pygame加载可能很慢或失败
                # 尝试用pydub先转换
                if file_ext in ['.flac', '.m4a', '.aac', '.wma', '.opus'] and PYDUB_AVAILABLE:
                    print(f"[PygameMixer] 使用pydub加载 {file_ext} 格式...")
                    try:
                        audio_seg = AudioSegment.from_file(file_path)
                        self.audio_segments[track_id] = audio_seg
                        
                        # 转换为pygame可以直接使用的格式
                        import io
                        buffer = io.BytesIO()
                        audio_seg.export(buffer, format='wav')
                        buffer.seek(0)
                        sound = pygame.mixer.Sound(buffer)
                        
                        self.sounds[track_id] = sound
                        self.file_paths[track_id] = file_path
                        self.volumes[track_id] = 0.8
                        
                        duration = len(audio_seg)  # pydub的长度是毫秒
                        if duration > self.duration_ms:
                            self.duration_ms = duration
                        
                        self.channels[track_id] = pygame.mixer.Channel(track_id)
                        print(f"[PygameMixer] pydub加载成功，时长: {duration/1000:.1f}秒")
                        
                        # 存入缓存
                        if PRELOADER_AVAILABLE:
                            size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                            cached_audio = CachedAudio(
                                file_path=file_path,
                                sound=sound,
                                audio_segment=audio_seg,
                                duration_ms=duration,
                                size_bytes=size_bytes
                            )
                            cache.put(file_path, cached_audio)
                        
                        return True
                    except Exception as e:
                        print(f"[PygameMixer] pydub加载失败: {e}")
                        # 继续尝试直接用pygame加载
                
                # 直接用pygame加载（主要用于wav, mp3, ogg）
                print(f"[PygameMixer] 使用pygame直接加载...")
                sound = pygame.mixer.Sound(file_path)
                self.sounds[track_id] = sound
                self.file_paths[track_id] = file_path
                self.volumes[track_id] = 0.8
                
                if PYDUB_AVAILABLE and track_id not in self.audio_segments:
                    try:
                        audio_seg = AudioSegment.from_file(file_path)
                        self.audio_segments[track_id] = audio_seg
                    except:
                        pass
                
                duration = int(sound.get_length() * 1000)
                if duration > self.duration_ms:
                    self.duration_ms = duration
                
                self.channels[track_id] = pygame.mixer.Channel(track_id)
                print(f"[PygameMixer] pygame加载成功，时长: {duration/1000:.1f}秒")
                
                # 存入缓存
                if PRELOADER_AVAILABLE:
                    size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    cached_audio = CachedAudio(
                        file_path=file_path,
                        sound=sound,
                        audio_segment=self.audio_segments.get(track_id),
                        duration_ms=duration,
                        size_bytes=size_bytes
                    )
                    cache.put(file_path, cached_audio)
                
                return True
                
            except Exception as e:
                print(f"[PygameMixer] 加载失败 {os.path.basename(file_path)}: {e}")
                return False
    
    def _create_sound_from_position(self, track_id: int, position_ms: int) -> Optional['pygame.mixer.Sound']:
        if not PYDUB_AVAILABLE or track_id not in self.audio_segments:
            return self.sounds.get(track_id)
        
        try:
            audio_seg = self.audio_segments[track_id]
            trimmed = audio_seg[position_ms:]
            
            if len(trimmed) == 0:
                return None
            
            import io
            buffer = io.BytesIO()
            trimmed.export(buffer, format='wav')
            buffer.seek(0)
            
            return pygame.mixer.Sound(buffer)
        except Exception as e:
            print(f"[PygameMixer] 裁剪音频失败: {e}")
            return self.sounds.get(track_id)
    
    def _create_all_sounds_from_position(self, position_ms: int) -> Dict[int, 'pygame.mixer.Sound']:
        result = {}
        for track_id in self.sounds.keys():
            if position_ms > 0 and PYDUB_AVAILABLE and track_id in self.audio_segments:
                trimmed = self._create_sound_from_position(track_id, position_ms)
                result[track_id] = trimmed if trimmed else self.sounds[track_id]
            else:
                result[track_id] = self.sounds[track_id]
        return result
    
    def play_all(self, start_position_ms: int = 0):
        if not self.sounds:
            return
        
        with self._lock:
            # 先停止所有通道
            for channel in self.channels.values():
                if channel:
                    channel.stop()
            
            self._play_offset_ms = start_position_ms
            self._is_paused = False
            
            # 预先为所有音轨创建Sound对象
            if start_position_ms > 0 and PYDUB_AVAILABLE:
                self._current_sounds = self._create_all_sounds_from_position(start_position_ms)
            else:
                self._current_sounds = dict(self.sounds)
            
            self._play_start_time = time.time()
            
            # 同时启动所有通道
            for track_id, sound in self._current_sounds.items():
                channel = self.channels.get(track_id)
                if channel and sound:
                    channel.set_volume(self.volumes.get(track_id, 0.8))
                    channel.play(sound)
            
            self.is_playing = True
    
    def pause_all(self):
        with self._lock:
            if self.is_playing and not self._is_paused:
                self._paused_position_ms = self.get_position()
                self._is_paused = True
                
            for channel in self.channels.values():
                if channel:
                    channel.pause()
            self.is_playing = False
    
    def unpause_all(self):
        with self._lock:
            if self._is_paused:
                self._play_start_time = time.time()
                self._play_offset_ms = self._paused_position_ms
                self._is_paused = False
                
            for channel in self.channels.values():
                if channel:
                    channel.unpause()
            self.is_playing = True
    
    def stop_all(self):
        with self._lock:
            for channel in self.channels.values():
                if channel:
                    channel.stop()
            self.is_playing = False
            self._play_offset_ms = 0
            self._paused_position_ms = 0
            self._is_paused = False
            self._current_sounds.clear()
    
    def set_position(self, position_ms: int):
        if not self.sounds:
            return
        
        with self._lock:
            was_playing = self.is_playing
            was_paused = self._is_paused
            
            for channel in self.channels.values():
                if channel:
                    channel.stop()
            
            self._play_offset_ms = position_ms
            
            if was_playing or was_paused:
                self._is_paused = False
                
                if PYDUB_AVAILABLE and position_ms > 0:
                    self._current_sounds = self._create_all_sounds_from_position(position_ms)
                else:
                    self._current_sounds = dict(self.sounds)
                
                self._play_start_time = time.time()
                
                for track_id, sound in self._current_sounds.items():
                    channel = self.channels.get(track_id)
                    if channel and sound:
                        channel.set_volume(self.volumes.get(track_id, 0.8))
                        channel.play(sound)
                
                self.is_playing = True
            else:
                self._paused_position_ms = position_ms
                self._is_paused = True
                self.is_playing = False
    
    def get_position(self) -> int:
        if not self.sounds:
            return 0
        
        if self._is_paused:
            return self._paused_position_ms
        
        if not self.is_playing:
            return 0
        
        elapsed = time.time() - self._play_start_time
        current_pos = self._play_offset_ms + int(elapsed * 1000)
        
        if current_pos > self.duration_ms:
            current_pos = self.duration_ms
        
        return current_pos
    
    def check_playback_ended(self) -> bool:
        if not self.is_playing or self._is_paused:
            return False
        
        any_playing = False
        for channel in self.channels.values():
            if channel and channel.get_busy():
                any_playing = True
                break
        
        if not any_playing and self.is_playing:
            current_pos = self.get_position()
            if current_pos >= self.duration_ms - 100:
                return True
        
        return False
    
    def set_volume(self, track_id: int, volume: float):
        with self._lock:
            self.volumes[track_id] = max(0.0, min(1.0, volume))
            if track_id in self.channels:
                self.channels[track_id].set_volume(self.volumes[track_id])
    
    def unload_track(self, track_id: int):
        with self._lock:
            if track_id in self.channels:
                self.channels[track_id].stop()
                del self.channels[track_id]
            if track_id in self.sounds:
                del self.sounds[track_id]
            if track_id in self.volumes:
                del self.volumes[track_id]
            if track_id in self.file_paths:
                del self.file_paths[track_id]
            if track_id in self.audio_segments:
                del self.audio_segments[track_id]
            if track_id in self._current_sounds:
                del self._current_sounds[track_id]
    
    def clear_all(self):
        with self._lock:
            self.stop_all()
            self.sounds.clear()
            self.channels.clear()
            self.volumes.clear()
            self.file_paths.clear()
            self.audio_segments.clear()
            self._current_sounds.clear()
            self.duration_ms = 0
            self._play_offset_ms = 0
            self._paused_position_ms = 0
    
    def get_duration(self) -> int:
        return self.duration_ms
    
    def is_busy(self) -> bool:
        for channel in self.channels.values():
            if channel and channel.get_busy():
                return True
        return False


_mixer_engine: Optional[PygameMixerEngine] = None

def get_mixer_engine() -> PygameMixerEngine:
    global _mixer_engine
    if _mixer_engine is None:
        _mixer_engine = PygameMixerEngine()
    return _mixer_engine


# ============================================================
# 音轨控制组件
# ============================================================

class TrackControl(QFrame):
    """单个音轨控制组件"""
    volumeChanged = pyqtSignal(str, int)
    loadFinished = pyqtSignal(bool)
    
    _track_counter = 0
    
    def __init__(self, track_path: str, parent=None, force_qmedia: bool = False):
        super().__init__(parent)
        self.track_path = track_path
        self.track_name = Path(track_path).stem
        self.is_muted = False
        self.saved_volume = 80
        self._is_ready = False
        self._pending_play = False
        
        self.track_id = TrackControl._track_counter
        TrackControl._track_counter += 1
        
        # 如果force_qmedia为True，强制使用QMediaPlayer（单音轨模式，异步加载不阻塞UI）
        # 否则使用pygame（多音轨模式，需要同步）
        self._use_pygame = PYGAME_AVAILABLE and not force_qmedia
        self._force_qmedia = force_qmedia
        
        self.player: Optional[QMediaPlayer] = None
        self.audio_output: Optional[QAudioOutput] = None
        
        self._load_volume_settings()
        self.setup_ui()
        
    def _load_volume_settings(self):
        vs = get_volume_settings()
        self.saved_volume = vs.get_volume(self.track_name)
        self.is_muted = vs.get_muted(self.track_name)
        
    def _save_volume_settings(self):
        vs = get_volume_settings()
        if not self.is_muted:
            vs.set_volume(self.track_name, self.volume_slider.value())
        else:
            vs.set_volume(self.track_name, self.saved_volume)
        vs.set_muted(self.track_name, self.is_muted)
        
    def setup_ui(self):
        self.setObjectName("trackControl")
        self.setStyleSheet("""
            #trackControl {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2d2d3a, stop:1 #1e1e28);
                border-radius: 12px; padding: 12px; margin: 4px 0;
            }
            #trackControl:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3d3d4a, stop:1 #2e2e38); 
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)
        
        name_label = QLabel(self.track_name)
        name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        name_label.setStyleSheet("color: #e0e0e0; min-width: 150px; max-width: 200px;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        self.mute_btn = QPushButton("🔊" if not self.is_muted else "🔇")
        self.mute_btn.setFixedSize(36, 36)
        self.mute_btn.setStyleSheet("""
            QPushButton { background: #4a4a5e; border: none; border-radius: 18px; font-size: 16px; }
            QPushButton:hover { background: #5a5a6e; }
        """)
        self.mute_btn.clicked.connect(self.toggle_mute)
        layout.addWidget(self.mute_btn)
        
        self.volume_slider = ClickableVolumeSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        initial_volume = 0 if self.is_muted else self.saved_volume
        self.volume_slider.setValue(initial_volume)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #3a3a4a; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7c5ce0, stop:1 #5a3eb8); 
                width: 20px; height: 20px; margin: -6px 0; border-radius: 10px; 
            }
            QSlider::sub-page:horizontal { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c5ce0, stop:1 #a78bfa); 
                border-radius: 4px; 
            }
        """)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        layout.addWidget(self.volume_slider, 1)
        
        self.volume_label = QLabel(f"{initial_volume}%")
        self.volume_label.setFixedWidth(45)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.volume_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(self.volume_label)
        
    def setup_player(self):
        print(f"[TrackControl] setup_player开始: {self.track_name}, 使用pygame: {self._use_pygame}")
        if self._use_pygame:
            engine = get_mixer_engine()
            if engine.load_track(self.track_id, self.track_path):
                self._is_ready = True
                volume = 0 if self.is_muted else self.saved_volume / 100.0
                engine.set_volume(self.track_id, volume)
                print(f"[TrackControl] pygame加载成功: {self.track_name}")
            else:
                print(f"[TrackControl] pygame加载失败，回退到QMediaPlayer: {self.track_name}")
                self._use_pygame = False
                self._setup_qmediaplayer()
        else:
            self._setup_qmediaplayer()
        print(f"[TrackControl] setup_player完成: {self.track_name}, ready={self._is_ready}")
    
    def _setup_qmediaplayer(self):
        if self.player:
            return
        
        try:
            self.player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            volume = 0 if self.is_muted else self.saved_volume / 100.0
            self.audio_output.setVolume(volume)
            self.player.setAudioOutput(self.audio_output)
            self.player.mediaStatusChanged.connect(self._on_media_status_changed)
            self.player.errorOccurred.connect(self._on_player_error)
            
            # 检查文件是否存在（本地文件）
            if not self.track_path.startswith('http') and not os.path.exists(self.track_path):
                print(f"[TrackControl] 文件不存在: {self.track_path}")
                self.loadFinished.emit(False)
                return
            
            if self.track_path.startswith('http'):
                self.player.setSource(QUrl(self.track_path))
            else:
                self.player.setSource(QUrl.fromLocalFile(self.track_path))
            print(f"[TrackControl] QMediaPlayer设置源: {self.track_name}")
        except Exception as e:
            print(f"[TrackControl] QMediaPlayer初始化失败: {e}")
            self.loadFinished.emit(False)
    
    def _on_player_error(self, error, message):
        """处理QMediaPlayer错误"""
        print(f"[TrackControl] 播放器错误 ({self.track_name}): {error} - {message}")
        
    def _on_media_status_changed(self, status):
        status_names = {
            QMediaPlayer.MediaStatus.NoMedia: "NoMedia",
            QMediaPlayer.MediaStatus.LoadingMedia: "LoadingMedia",
            QMediaPlayer.MediaStatus.LoadedMedia: "LoadedMedia",
            QMediaPlayer.MediaStatus.StalledMedia: "StalledMedia",
            QMediaPlayer.MediaStatus.BufferingMedia: "BufferingMedia",
            QMediaPlayer.MediaStatus.BufferedMedia: "BufferedMedia",
            QMediaPlayer.MediaStatus.EndOfMedia: "EndOfMedia",
            QMediaPlayer.MediaStatus.InvalidMedia: "InvalidMedia",
        }
        print(f"[TrackControl] 媒体状态变化 ({self.track_name}): {status_names.get(status, status)}")
        
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._is_ready = True
            if self._pending_play:
                print(f"[TrackControl] 媒体已加载，开始播放: {self.track_name}")
                self.player.play()
                self._pending_play = False
            self.loadFinished.emit(True)
        elif status == QMediaPlayer.MediaStatus.BufferedMedia:
            # 在线音乐缓冲完成，也可以播放
            if self._pending_play and not self._is_ready:
                self._is_ready = True
                print(f"[TrackControl] 缓冲完成，开始播放: {self.track_name}")
                self.player.play()
                self._pending_play = False
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._is_ready = False
            self._pending_play = False
            print(f"[TrackControl] 无效媒体: {self.track_name}")
            self.loadFinished.emit(False)
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            self._is_ready = False
        
    def on_volume_changed(self, value):
        volume = value / 100.0
        if self._use_pygame:
            get_mixer_engine().set_volume(self.track_id, volume)
        elif self.audio_output:
            self.audio_output.setVolume(volume)
        self.volume_label.setText(f"{value}%")
        
        if not self.is_muted:
            self._save_volume_settings()
        
    def toggle_mute(self):
        if self.is_muted:
            self.volume_slider.setValue(self.saved_volume)
            self.mute_btn.setText("🔊")
            self.is_muted = False
        else:
            self.saved_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
            self.mute_btn.setText("🔇")
            self.is_muted = True
        self._save_volume_settings()
            
    def play(self):
        self.setup_player()
        if self._use_pygame:
            engine = get_mixer_engine()
            if engine.is_playing or engine.sounds:
                engine.play_all()
                print(f"[TrackControl] pygame播放: {self.track_name}")
            else:
                print(f"[TrackControl] pygame未加载音频，尝试加载: {self.track_name}")
                if engine.load_track(self.track_id, self.track_path):
                    engine.play_all()
                else:
                    print(f"[TrackControl] pygame加载失败，回退到QMediaPlayer: {self.track_name}")
                    self._use_pygame = False
                    self._setup_qmediaplayer()
                    self._pending_play = True
        elif self.player:
            if self._is_ready:
                self.player.play()
                print(f"[TrackControl] QMediaPlayer播放: {self.track_name}")
            else:
                self._pending_play = True
                print(f"[TrackControl] QMediaPlayer未就绪，等待加载: {self.track_name}")
            
    def pause(self):
        if self._use_pygame:
            get_mixer_engine().pause_all()
        elif self.player:
            self.player.pause()
            
    def stop(self):
        if self._use_pygame:
            get_mixer_engine().stop_all()
        elif self.player:
            self.player.stop()
            
    def set_position(self, position: int):
        if self._use_pygame:
            get_mixer_engine().set_position(position)
        elif self.player:
            self.player.setPosition(position)
            
    def set_playback_rate(self, rate: float):
        if not self._use_pygame and self.player:
            self.player.setPlaybackRate(rate)
            
    def get_duration(self) -> int:
        if self._use_pygame:
            return get_mixer_engine().get_duration()
        return self.player.duration() if self.player else 0
    
    def get_position(self) -> int:
        if self._use_pygame:
            return get_mixer_engine().get_position()
        return self.player.position() if self.player else 0
    
    def is_ready(self) -> bool:
        return self._is_ready
    
    def set_volume(self, volume: int):
        """设置音量 (0-100)"""
        self.volume_slider.setValue(volume)
        
    def cleanup(self):
        if self._use_pygame:
            get_mixer_engine().unload_track(self.track_id)
        else:
            if self.player:
                self.player.stop()
                self.player.setSource(QUrl())
                self.player.deleteLater()
                self.player = None
            if self.audio_output:
                self.audio_output.deleteLater()
                self.audio_output = None


# ============================================================
# 同步管理器
# ============================================================

class SyncedTrackManager:
    """多音轨同步管理器"""
    
    def __init__(self):
        self.tracks: List[TrackControl] = []
        self._use_pygame = PYGAME_AVAILABLE
        
        self._sync_timer = QTimer()
        self._sync_timer.setInterval(500)
        self._sync_timer.timeout.connect(self._check_sync)
        
        self._end_check_timer = QTimer()
        self._end_check_timer.setInterval(200)
        self._end_check_timer.timeout.connect(self._check_playback_ended)
        
        self._on_end_callback: Optional[Callable] = None
        
    def set_end_callback(self, callback: Callable):
        self._on_end_callback = callback
        
    def add_track(self, track: TrackControl):
        self.tracks.append(track)
        
    def clear(self):
        self._sync_timer.stop()
        self._end_check_timer.stop()
        TrackControl._track_counter = 0
        
        # 检查实际的音轨使用的引擎
        if self.tracks and self.tracks[0]._use_pygame:
            get_mixer_engine().clear_all()
        
        self.tracks.clear()
        
    def setup_all(self):
        for track in self.tracks:
            track.setup_player()
            
    def play_all_synced(self, start_position_ms: int = 0):
        if not self.tracks:
            return
        
        for track in self.tracks:
            track.setup_player()
        
        # 检查实际的音轨使用的引擎
        if self.tracks[0]._use_pygame:
            get_mixer_engine().play_all(start_position_ms)
        else:
            for track in self.tracks:
                if track.player and track.is_ready():
                    if start_position_ms > 0:
                        track.player.setPosition(start_position_ms)
                    track.player.play()
        
        self._end_check_timer.start()
                
    def pause_all(self):
        if not self.tracks:
            return
        # 检查实际的音轨使用的引擎
        if self.tracks[0]._use_pygame:
            get_mixer_engine().pause_all()
        else:
            for track in self.tracks:
                track.pause()
                
    def resume_all(self):
        if not self.tracks:
            return
        # 检查实际的音轨使用的引擎
        if self.tracks[0]._use_pygame:
            get_mixer_engine().unpause_all()
        else:
            for track in self.tracks:
                if track.player:
                    track.player.play()
        
        self._end_check_timer.start()
                
    def stop_all(self):
        self._end_check_timer.stop()
        if not self.tracks:
            return
        # 检查实际的音轨使用的引擎，而不是全局的PYGAME_AVAILABLE
        if self.tracks[0]._use_pygame:
            get_mixer_engine().stop_all()
        else:
            for track in self.tracks:
                track.stop()
            
    def set_all_positions_synced(self, position: int):
        # 检查实际的音轨使用的引擎
        if self.tracks and self.tracks[0]._use_pygame:
            get_mixer_engine().set_position(position)
        else:
            if not self.tracks:
                return
            
            for track in self.tracks:
                if track.player:
                    track.player.pause()
            
            time.sleep(0.05)
            
            for track in self.tracks:
                track.set_position(position)
            
    def set_playback_rate_all(self, rate: float):
        # 检查实际的音轨使用的引擎
        if not (self.tracks and self.tracks[0]._use_pygame):
            for track in self.tracks:
                track.set_playback_rate(rate)
                
    def get_position(self) -> int:
        # 检查实际的音轨使用的引擎
        if self.tracks and self.tracks[0]._use_pygame:
            return get_mixer_engine().get_position()
        elif self.tracks:
            return self.tracks[0].get_position()
        return 0
    
    def get_duration(self) -> int:
        # 检查实际的音轨使用的引擎
        if self.tracks and self.tracks[0]._use_pygame:
            return get_mixer_engine().get_duration()
        elif self.tracks:
            return self.tracks[0].get_duration()
        return 0
            
    def _check_sync(self):
        # 检查实际的音轨使用的引擎
        if (self.tracks and self.tracks[0]._use_pygame) or not self.tracks or len(self.tracks) < 2:
            return
            
        ref_position = self.tracks[0].get_position()
        tolerance = 300
        
        for track in self.tracks[1:]:
            pos = track.get_position()
            if abs(pos - ref_position) > tolerance:
                track.set_position(ref_position)
    
    def _check_playback_ended(self):
        ended = False
        
        # 检查实际的音轨使用的引擎
        if self.tracks and self.tracks[0]._use_pygame:
            ended = get_mixer_engine().check_playback_ended()
        else:
            if self.tracks and self.tracks[0].player:
                status = self.tracks[0].player.mediaStatus()
                if status == QMediaPlayer.MediaStatus.EndOfMedia:
                    ended = True
        
        if ended:
            print("[SyncManager] 检测到播放结束")
            self._end_check_timer.stop()
            if self._on_end_callback:
                self._on_end_callback()
                
    def start_sync_monitoring(self):
        # 检查实际的音轨使用的引擎
        if not (self.tracks and self.tracks[0]._use_pygame):
            self._sync_timer.start()
        
    def stop_sync_monitoring(self):
        self._sync_timer.stop()


# ============================================================
# 音轨控制面板
# ============================================================

class TrackControlPanel(QFrame):
    """音轨控制面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.track_controls: list[TrackControl] = []
        self.sync_manager = SyncedTrackManager()
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("background: #1a1a24; border-radius: 16px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header = QHBoxLayout()
        self.track_title = QLabel("🎚️ 音轨控制")
        self.track_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.track_title.setStyleSheet("color: #ffffff;")
        header.addWidget(self.track_title)
        header.addStretch()
        layout.addLayout(header)
        
        if PYGAME_AVAILABLE:
            engine_text = "🎮 音频引擎: pygame mixer"
            engine_color = "#50e050"
        else:
            engine_text = "⚠️ 音频引擎: QMediaPlayer"
            engine_color = "#e0a050"
        
        engine_label = QLabel(engine_text)
        engine_label.setStyleSheet(f"color: {engine_color}; font-size: 10px;")
        layout.addWidget(engine_label)
        
        self.current_song_label = QLabel("请选择歌曲...")
        self.current_song_label.setFont(QFont("Segoe UI", 11))
        self.current_song_label.setStyleSheet("color: #a0a0a0;")
        self.current_song_label.setWordWrap(True)
        layout.addWidget(self.current_song_label)
        
        self.separate_btn = QPushButton("✂️ 一键分离音轨")
        self.separate_btn.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e85d04, stop:1 #f77f00); 
                color: white; border: none; border-radius: 12px; padding: 14px 28px; font-weight: bold; 
            }
            QPushButton:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f77f00, stop:1 #ff9500); 
            }
            QPushButton:disabled { background: #4a4a5e; }
        """)
        self.separate_btn.setEnabled(False)
        layout.addWidget(self.separate_btn)
        
        self.separate_status = QLabel("")
        self.separate_status.setStyleSheet("color: #808080; font-size: 11px;")
        self.separate_status.setWordWrap(True)
        layout.addWidget(self.separate_status)
        
        self.sync_status = QLabel("")
        self.sync_status.setStyleSheet("color: #50e050; font-size: 10px;")
        layout.addWidget(self.sync_status)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tracks_container = QWidget()
        self.tracks_layout = QVBoxLayout(self.tracks_container)
        self.tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tracks_layout.setSpacing(8)
        scroll.setWidget(self.tracks_container)
        layout.addWidget(scroll)
        
    def clear_tracks(self):
        self.sync_manager.stop_sync_monitoring()
        self.sync_manager.clear()
        for tc in self.track_controls:
            tc.cleanup()
            tc.deleteLater()
        self.track_controls.clear()
        self.sync_status.setText("")
        
    def add_track(self, track_path: str, force_qmedia: bool = False) -> TrackControl:
        tc = TrackControl(track_path, force_qmedia=force_qmedia)
        self.track_controls.append(tc)
        self.sync_manager.add_track(tc)
        self.tracks_layout.addWidget(tc)
        
        if len(self.track_controls) > 1:
            engine = "pygame" if PYGAME_AVAILABLE else "QMediaPlayer"
            self.sync_status.setText(f"🔗 {len(self.track_controls)} 个音轨 ({engine})")
        
        return tc
        
    def set_current_song(self, title: str):
        self.current_song_label.setText(f"正在播放: {title}")
        
    def get_sync_manager(self) -> SyncedTrackManager:
        return self.sync_manager
