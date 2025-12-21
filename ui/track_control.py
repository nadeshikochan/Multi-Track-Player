"""
音轨控制组件 - 完整修复版 v4

修复问题：
1. 多音轨同步播放 - 使用 pygame.mixer 多通道混音
2. 进度条拖动 - 支持 pygame 模式下的 seek
3. 音量持久化 - 保存音量设置到 QSettings
4. 播放位置追踪 - 使用定时器追踪播放位置

使用方法：
1. pip install pygame
2. 将此文件替换 ui/track_control.py
"""

import os
import time
from typing import Optional, List, Dict
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
    QSlider, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QUrl, QSettings
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
    print("[提示] 运行 'pip install pygame' 可获得更好的多音轨体验")


# 音量设置管理器
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
        """获取保存的音量值，默认80"""
        return int(self.settings.value(f"volume/{track_name}", 80))
    
    def set_volume(self, track_name: str, volume: int):
        """保存音量值"""
        self.settings.setValue(f"volume/{track_name}", volume)
    
    def get_muted(self, track_name: str) -> bool:
        """获取静音状态"""
        return self.settings.value(f"muted/{track_name}", False, type=bool)
    
    def set_muted(self, track_name: str, muted: bool):
        """保存静音状态"""
        self.settings.setValue(f"muted/{track_name}", muted)


def get_volume_settings() -> VolumeSettings:
    return VolumeSettings()


class ClickableVolumeSlider(QSlider):
    """可点击的音量滑块，点击直接跳转到对应位置"""
    
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
# Pygame 混音引擎 - 支持 Seek (使用 pydub)
# ============================================================

# 尝试导入 pydub
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
    print("[音频引擎] pydub 可用，支持精确 seek")
except ImportError:
    PYDUB_AVAILABLE = False
    print("[音频引擎] pydub 未安装，seek 功能受限")
    print("[提示] 运行 'pip install pydub' 可获得精确的进度跳转功能")


class PygameMixerEngine:
    """
    Pygame 混音引擎 - 单例模式
    
    所有音轨在同一个混音器中处理，支持 seek 操作。
    使用 pydub 裁剪音频来实现精确的 seek。
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.sounds: Dict[int, 'pygame.mixer.Sound'] = {}
        self.channels: Dict[int, 'pygame.mixer.Channel'] = {}
        self.volumes: Dict[int, float] = {}
        self.file_paths: Dict[int, str] = {}
        self.duration_ms: int = 0
        self.is_playing: bool = False
        self._mixer_ready = False
        
        # 原始音频数据 (pydub AudioSegment)
        self.audio_segments: Dict[int, 'AudioSegment'] = {}
        
        # 播放位置追踪
        self._play_start_time: float = 0  # 开始播放的系统时间
        self._play_offset_ms: int = 0  # 播放起始偏移(seek位置)
        self._paused_position_ms: int = 0  # 暂停时的位置
        self._is_paused: bool = False
        
    def init_mixer(self) -> bool:
        """初始化 pygame mixer"""
        if self._mixer_ready:
            return True
        
        if not PYGAME_AVAILABLE:
            return False
        
        try:
            # 初始化 pygame（如果还没有）
            if not pygame.get_init():
                pygame.init()
            
            # 初始化 mixer
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
            
            # 设置通道数
            pygame.mixer.set_num_channels(32)
            
            self._mixer_ready = True
            self._initialized = True
            print(f"[PygameMixer] 初始化成功: {pygame.mixer.get_init()}")
            return True
            
        except Exception as e:
            print(f"[PygameMixer] 初始化失败: {e}")
            return False
    
    def load_track(self, track_id: int, file_path: str) -> bool:
        """加载音轨到指定通道"""
        if not self.init_mixer():
            return False
        
        try:
            print(f"[PygameMixer] 正在加载: {file_path}")
            
            # 加载音频
            sound = pygame.mixer.Sound(file_path)
            self.sounds[track_id] = sound
            self.file_paths[track_id] = file_path
            self.volumes[track_id] = 0.8
            
            # 如果 pydub 可用，也加载 AudioSegment 用于 seek
            if PYDUB_AVAILABLE:
                try:
                    audio_seg = AudioSegment.from_file(file_path)
                    self.audio_segments[track_id] = audio_seg
                    print(f"[PygameMixer] AudioSegment 已加载: {len(audio_seg)}ms")
                except Exception as e:
                    print(f"[PygameMixer] AudioSegment 加载失败: {e}")
            
            # 更新总时长
            duration = int(sound.get_length() * 1000)
            if duration > self.duration_ms:
                self.duration_ms = duration
            
            # 分配通道
            self.channels[track_id] = pygame.mixer.Channel(track_id)
            
            print(f"[PygameMixer] 已加载音轨 {track_id}, 时长: {duration}ms")
            return True
            
        except Exception as e:
            print(f"[PygameMixer] 加载失败 {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_sound_from_position(self, track_id: int, position_ms: int) -> Optional['pygame.mixer.Sound']:
        """从指定位置创建 Sound 对象（使用 pydub 裁剪）"""
        if not PYDUB_AVAILABLE:
            return self.sounds.get(track_id)
        
        if track_id not in self.audio_segments:
            return self.sounds.get(track_id)
        
        try:
            audio_seg = self.audio_segments[track_id]
            # 裁剪音频
            trimmed = audio_seg[position_ms:]
            
            if len(trimmed) == 0:
                return None
            
            # 转换为 pygame Sound
            # 导出为 wav 格式的字节流
            import io
            buffer = io.BytesIO()
            trimmed.export(buffer, format='wav')
            buffer.seek(0)
            
            sound = pygame.mixer.Sound(buffer)
            return sound
            
        except Exception as e:
            print(f"[PygameMixer] 裁剪音频失败: {e}")
            return self.sounds.get(track_id)
    
    def play_all(self, start_position_ms: int = 0):
        """同时播放所有音轨，支持从指定位置开始"""
        if not self.sounds:
            print("[PygameMixer] 没有音轨可播放")
            return
        
        print(f"[PygameMixer] 开始播放 {len(self.sounds)} 个音轨, 起始位置: {start_position_ms}ms")
        
        # 记录播放起始信息
        self._play_offset_ms = start_position_ms
        self._play_start_time = time.time()
        self._is_paused = False
        
        for track_id, sound in self.sounds.items():
            channel = self.channels.get(track_id)
            if channel:
                vol = self.volumes.get(track_id, 0.8)
                channel.set_volume(vol)
                
                if start_position_ms > 0 and PYDUB_AVAILABLE:
                    # 使用裁剪后的音频
                    trimmed_sound = self._create_sound_from_position(track_id, start_position_ms)
                    if trimmed_sound:
                        channel.play(trimmed_sound)
                        print(f"[PygameMixer] 音轨 {track_id} 从 {start_position_ms}ms 开始播放")
                else:
                    # 从头播放
                    channel.play(sound)
                    print(f"[PygameMixer] 音轨 {track_id} 从头开始播放")
        
        self.is_playing = True
    
    def pause_all(self):
        """暂停所有音轨"""
        if self.is_playing and not self._is_paused:
            # 记录暂停时的位置
            self._paused_position_ms = self.get_position()
            self._is_paused = True
            
        for channel in self.channels.values():
            if channel:
                channel.pause()
        self.is_playing = False
    
    def unpause_all(self):
        """恢复所有音轨"""
        if self._is_paused:
            # 恢复时重新计算开始时间
            self._play_start_time = time.time()
            self._play_offset_ms = self._paused_position_ms
            self._is_paused = False
            
        for channel in self.channels.values():
            if channel:
                channel.unpause()
        self.is_playing = True
    
    def stop_all(self):
        """停止所有音轨"""
        for channel in self.channels.values():
            if channel:
                channel.stop()
        self.is_playing = False
        self._play_offset_ms = 0
        self._paused_position_ms = 0
        self._is_paused = False
    
    def set_position(self, position_ms: int):
        """设置播放位置（通过重新播放实现）"""
        if not self.sounds:
            return
        
        print(f"[PygameMixer] set_position: {position_ms}ms, is_playing={self.is_playing}, is_paused={self._is_paused}")
        
        was_playing = self.is_playing
        was_paused = self._is_paused
        
        # 停止所有通道
        for channel in self.channels.values():
            if channel:
                channel.stop()
        
        # 更新位置追踪
        self._play_offset_ms = position_ms
        self._play_start_time = time.time()
        
        if was_playing or was_paused:
            # 从新位置开始播放
            self._is_paused = False
            
            for track_id in self.sounds.keys():
                channel = self.channels.get(track_id)
                if channel:
                    vol = self.volumes.get(track_id, 0.8)
                    channel.set_volume(vol)
                    
                    if PYDUB_AVAILABLE and position_ms > 0:
                        # 使用裁剪后的音频
                        trimmed_sound = self._create_sound_from_position(track_id, position_ms)
                        if trimmed_sound:
                            channel.play(trimmed_sound)
                    else:
                        # 没有 pydub，只能从头播放（但位置追踪是正确的）
                        channel.play(self.sounds[track_id])
            
            self.is_playing = True
            print(f"[PygameMixer] 从 {position_ms}ms 恢复播放")
        else:
            # 只更新位置，不播放
            self._paused_position_ms = position_ms
            self._is_paused = True
            self.is_playing = False
    
    def get_position(self) -> int:
        """获取当前播放位置（毫秒）"""
        if not self.sounds:
            return 0
        
        if self._is_paused:
            return self._paused_position_ms
        
        if not self.is_playing:
            return 0
        
        # 通过时间计算当前位置
        elapsed = time.time() - self._play_start_time
        current_pos = self._play_offset_ms + int(elapsed * 1000)
        
        # 确保不超过总时长
        if current_pos > self.duration_ms:
            current_pos = self.duration_ms
        
        return current_pos
    
    def set_volume(self, track_id: int, volume: float):
        """设置指定音轨的音量"""
        self.volumes[track_id] = max(0.0, min(1.0, volume))
        if track_id in self.channels:
            self.channels[track_id].set_volume(self.volumes[track_id])
    
    def unload_track(self, track_id: int):
        """卸载指定音轨"""
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
    
    def clear_all(self):
        """清除所有音轨"""
        self.stop_all()
        self.sounds.clear()
        self.channels.clear()
        self.volumes.clear()
        self.file_paths.clear()
        self.audio_segments.clear()
        self.duration_ms = 0
        self._play_offset_ms = 0
        self._paused_position_ms = 0
    
    def get_duration(self) -> int:
        return self.duration_ms
    
    def is_busy(self) -> bool:
        """检查是否有音轨在播放"""
        for channel in self.channels.values():
            if channel and channel.get_busy():
                return True
        return False


# 全局引擎实例
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
    
    # 音轨ID计数器
    _track_counter = 0
    
    def __init__(self, track_path: str, parent=None):
        super().__init__(parent)
        self.track_path = track_path
        self.track_name = Path(track_path).stem
        self.is_muted = False
        self.saved_volume = 80
        self._is_ready = False
        self._pending_play = False
        
        # 分配唯一ID
        self.track_id = TrackControl._track_counter
        TrackControl._track_counter += 1
        
        # 判断使用哪个引擎
        self._use_pygame = PYGAME_AVAILABLE
        
        # QMediaPlayer 备用
        self.player: Optional[QMediaPlayer] = None
        self.audio_output: Optional[QAudioOutput] = None
        
        # 加载保存的音量设置
        self._load_volume_settings()
        
        self.setup_ui()
        
    def _load_volume_settings(self):
        """加载保存的音量设置"""
        vs = get_volume_settings()
        self.saved_volume = vs.get_volume(self.track_name)
        self.is_muted = vs.get_muted(self.track_name)
        
    def _save_volume_settings(self):
        """保存音量设置"""
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
        
        # 音轨名称
        name_label = QLabel(self.track_name)
        name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        name_label.setStyleSheet("color: #e0e0e0; min-width: 150px; max-width: 200px;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # 静音按钮
        self.mute_btn = QPushButton("🔊" if not self.is_muted else "🔇")
        self.mute_btn.setFixedSize(36, 36)
        self.mute_btn.setStyleSheet("""
            QPushButton { background: #4a4a5e; border: none; border-radius: 18px; font-size: 16px; }
            QPushButton:hover { background: #5a5a6e; }
        """)
        self.mute_btn.clicked.connect(self.toggle_mute)
        layout.addWidget(self.mute_btn)
        
        # 音量滑块
        self.volume_slider = ClickableVolumeSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        # 设置保存的音量值
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
        
        # 音量百分比
        self.volume_label = QLabel(f"{initial_volume}%")
        self.volume_label.setFixedWidth(45)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.volume_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(self.volume_label)
        
    def setup_player(self):
        """初始化播放器"""
        if self._use_pygame:
            # 使用 pygame 混音器
            engine = get_mixer_engine()
            if engine.load_track(self.track_id, self.track_path):
                self._is_ready = True
                # 应用保存的音量
                volume = 0 if self.is_muted else self.saved_volume / 100.0
                engine.set_volume(self.track_id, volume)
            else:
                print(f"[TrackControl] pygame 加载失败，回退到 QMediaPlayer")
                self._use_pygame = False
                self._setup_qmediaplayer()
        else:
            self._setup_qmediaplayer()
    
    def _setup_qmediaplayer(self):
        """设置 QMediaPlayer"""
        if self.player:
            return
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        # 应用保存的音量
        volume = 0 if self.is_muted else self.saved_volume / 100.0
        self.audio_output.setVolume(volume)
        self.player.setAudioOutput(self.audio_output)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.setSource(QUrl.fromLocalFile(self.track_path))
        
    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._is_ready = True
            if self._pending_play:
                self.player.play()
                self._pending_play = False
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            self._is_ready = False
        
    def on_volume_changed(self, value):
        volume = value / 100.0
        if self._use_pygame:
            get_mixer_engine().set_volume(self.track_id, volume)
        elif self.audio_output:
            self.audio_output.setVolume(volume)
        self.volume_label.setText(f"{value}%")
        
        # 如果不是静音状态，保存音量
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
        # 保存静音状态
        self._save_volume_settings()
            
    def play(self):
        """播放此音轨（单音轨模式）"""
        self.setup_player()
        if self._use_pygame:
            # 单音轨也用 pygame 播放
            engine = get_mixer_engine()
            engine.play_all()
        elif self.player:
            if self._is_ready:
                self.player.play()
            else:
                self._pending_play = True
            
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
        """设置播放位置"""
        if self._use_pygame:
            get_mixer_engine().set_position(position)
        elif self.player:
            self.player.setPosition(position)
            
    def set_playback_rate(self, rate: float):
        """设置播放速率（仅 QMediaPlayer 支持）"""
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
        
    def cleanup(self):
        """清理资源"""
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
    """
    多音轨同步管理器
    
    - pygame 模式：不需要同步，引擎自动处理
    - QMediaPlayer 模式：使用宽松的同步策略
    """
    
    def __init__(self):
        self.tracks: List[TrackControl] = []
        self._use_pygame = PYGAME_AVAILABLE
        
        # QMediaPlayer 回退时的同步定时器
        self._sync_timer = QTimer()
        self._sync_timer.setInterval(500)  # 500ms，比原来宽松很多
        self._sync_timer.timeout.connect(self._check_sync)
        
    def add_track(self, track: TrackControl):
        self.tracks.append(track)
        
    def clear(self):
        self._sync_timer.stop()
        
        # 重置音轨ID计数器
        TrackControl._track_counter = 0
        
        if self._use_pygame:
            get_mixer_engine().clear_all()
        
        self.tracks.clear()
        
    def setup_all(self):
        for track in self.tracks:
            track.setup_player()
            
    def play_all_synced(self, start_position_ms: int = 0):
        """播放所有音轨"""
        if not self.tracks:
            return
        
        # 确保所有音轨都初始化了
        for track in self.tracks:
            track.setup_player()
        
        if self._use_pygame:
            # pygame: 统一播放
            print(f"[SyncManager] 使用 pygame 播放 {len(self.tracks)} 个音轨, 位置: {start_position_ms}ms")
            get_mixer_engine().play_all(start_position_ms)
        else:
            # QMediaPlayer: 同时启动
            print(f"[SyncManager] 使用 QMediaPlayer 播放 {len(self.tracks)} 个音轨")
            for track in self.tracks:
                if track.player and track.is_ready():
                    if start_position_ms > 0:
                        track.player.setPosition(start_position_ms)
                    track.player.play()
                
    def pause_all(self):
        if self._use_pygame:
            get_mixer_engine().pause_all()
        else:
            for track in self.tracks:
                track.pause()
                
    def resume_all(self):
        """恢复播放（从暂停状态）"""
        if self._use_pygame:
            get_mixer_engine().unpause_all()
        else:
            for track in self.tracks:
                if track.player:
                    track.player.play()
                
    def stop_all(self):
        if self._use_pygame:
            get_mixer_engine().stop_all()
        else:
            for track in self.tracks:
                track.stop()
            
    def set_all_positions_synced(self, position: int):
        """设置所有音轨位置"""
        if self._use_pygame:
            get_mixer_engine().set_position(position)
        else:
            for track in self.tracks:
                track.set_position(position)
            
    def set_playback_rate_all(self, rate: float):
        """设置播放速率"""
        if not self._use_pygame:
            for track in self.tracks:
                track.set_playback_rate(rate)
                
    def get_position(self) -> int:
        """获取当前播放位置"""
        if self._use_pygame:
            return get_mixer_engine().get_position()
        elif self.tracks:
            return self.tracks[0].get_position()
        return 0
    
    def get_duration(self) -> int:
        """获取总时长"""
        if self._use_pygame:
            return get_mixer_engine().get_duration()
        elif self.tracks:
            return self.tracks[0].get_duration()
        return 0
            
    def _check_sync(self):
        """检查同步（仅 QMediaPlayer 模式）"""
        if self._use_pygame or not self.tracks or len(self.tracks) < 2:
            return
            
        ref_position = self.tracks[0].get_position()
        tolerance = 300  # 300ms 容差
        
        for track in self.tracks[1:]:
            pos = track.get_position()
            if abs(pos - ref_position) > tolerance:
                track.set_position(ref_position)
                
    def start_sync_monitoring(self):
        if not self._use_pygame:
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
        
        # 标题
        header = QHBoxLayout()
        self.track_title = QLabel("🎚️ 音轨控制")
        self.track_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.track_title.setStyleSheet("color: #ffffff;")
        header.addWidget(self.track_title)
        header.addStretch()
        layout.addLayout(header)
        
        # 引擎状态
        if PYGAME_AVAILABLE:
            engine_text = "🎮 音频引擎: pygame mixer"
            engine_color = "#50e050"
        else:
            engine_text = "⚠️ 音频引擎: QMediaPlayer (建议安装 pygame)"
            engine_color = "#e0a050"
        
        engine_label = QLabel(engine_text)
        engine_label.setStyleSheet(f"color: {engine_color}; font-size: 10px;")
        layout.addWidget(engine_label)
        
        # 当前歌曲
        self.current_song_label = QLabel("请选择歌曲...")
        self.current_song_label.setFont(QFont("Segoe UI", 11))
        self.current_song_label.setStyleSheet("color: #a0a0a0;")
        self.current_song_label.setWordWrap(True)
        layout.addWidget(self.current_song_label)
        
        # 分离按钮
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
        
        # 状态标签
        self.separate_status = QLabel("")
        self.separate_status.setStyleSheet("color: #808080; font-size: 11px;")
        self.separate_status.setWordWrap(True)
        layout.addWidget(self.separate_status)
        
        # 同步状态
        self.sync_status = QLabel("")
        self.sync_status.setStyleSheet("color: #50e050; font-size: 10px;")
        layout.addWidget(self.sync_status)
        
        # 音轨列表滚动区域
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
        """清除所有音轨"""
        self.sync_manager.stop_sync_monitoring()
        self.sync_manager.clear()
        for tc in self.track_controls:
            tc.cleanup()
            tc.deleteLater()
        self.track_controls.clear()
        self.sync_status.setText("")
        
    def add_track(self, track_path: str) -> TrackControl:
        """添加音轨"""
        tc = TrackControl(track_path)
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
