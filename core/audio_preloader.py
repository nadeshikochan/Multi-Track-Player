"""
音频预加载和缓存系统

优化切歌加载速度的核心模块：
1. 后台预加载 - 自动预加载下一首/前一首歌曲
2. LRU 缓存池 - 缓存最近播放的歌曲，避免重复加载
3. 异步加载 - 使用线程池加载，不阻塞 UI
4. 智能预测 - 根据播放模式预测下一首歌曲
"""

import os
import time
import threading
from typing import Optional, Dict, List, Callable, Any, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QThread

# 尝试导入 pygame
try:
    import pygame
    import pygame.mixer
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# 尝试导入 pydub
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


@dataclass
class CachedAudio:
    """缓存的音频数据"""
    file_path: str
    sound: Optional['pygame.mixer.Sound'] = None
    audio_segment: Optional['AudioSegment'] = None
    duration_ms: int = 0
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    size_bytes: int = 0
    
    def touch(self):
        """更新最后使用时间"""
        self.last_used = time.time()


class AudioCache:
    """
    音频缓存池 (LRU 策略)
    
    - 最大缓存数量可配置
    - 自动清理最久未使用的音频
    - 线程安全
    """
    
    def __init__(self, max_size: int = 10, max_memory_mb: int = 500):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: OrderedDict[str, CachedAudio] = OrderedDict()
        self._lock = threading.RLock()
        self._total_memory = 0
        
    def get(self, file_path: str) -> Optional[CachedAudio]:
        """获取缓存的音频"""
        with self._lock:
            if file_path in self._cache:
                cached = self._cache[file_path]
                cached.touch()
                # 移到最后 (最近使用)
                self._cache.move_to_end(file_path)
                return cached
            return None
    
    def put(self, file_path: str, cached_audio: CachedAudio):
        """添加音频到缓存"""
        with self._lock:
            # 如果已存在，先移除
            if file_path in self._cache:
                old = self._cache.pop(file_path)
                self._total_memory -= old.size_bytes
            
            # 检查是否需要清理
            self._ensure_capacity(cached_audio.size_bytes)
            
            # 添加新的
            self._cache[file_path] = cached_audio
            self._total_memory += cached_audio.size_bytes
            
    def _ensure_capacity(self, new_size: int):
        """确保有足够的容量"""
        # 按数量清理
        while len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            oldest = self._cache.pop(oldest_key)
            self._total_memory -= oldest.size_bytes
            print(f"[AudioCache] 清理缓存: {Path(oldest_key).name}")
            
        # 按内存清理
        while self._total_memory + new_size > self.max_memory_bytes and self._cache:
            oldest_key = next(iter(self._cache))
            oldest = self._cache.pop(oldest_key)
            self._total_memory -= oldest.size_bytes
            print(f"[AudioCache] 内存清理: {Path(oldest_key).name}")
            
    def remove(self, file_path: str):
        """移除缓存"""
        with self._lock:
            if file_path in self._cache:
                removed = self._cache.pop(file_path)
                self._total_memory -= removed.size_bytes
                
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._total_memory = 0
            
    def contains(self, file_path: str) -> bool:
        """检查是否存在缓存"""
        with self._lock:
            return file_path in self._cache
            
    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._lock:
            return {
                'count': len(self._cache),
                'max_count': self.max_size,
                'memory_mb': self._total_memory / (1024 * 1024),
                'max_memory_mb': self.max_memory_bytes / (1024 * 1024),
                'files': list(self._cache.keys())
            }


class PreloadTask:
    """预加载任务"""
    
    def __init__(self, file_path: str, priority: int = 0):
        self.file_path = file_path
        self.priority = priority  # 优先级越高越先加载
        self.future: Optional[Future] = None
        self.created_at = time.time()
        

class AudioPreloader(QObject):
    """
    音频预加载器
    
    特性：
    - 后台线程池异步加载
    - 智能预加载 (根据播放模式预测)
    - 加载状态回调
    - 可取消的预加载任务
    """
    
    # 信号
    preload_started = pyqtSignal(str)  # 开始预加载
    preload_finished = pyqtSignal(str, bool)  # 预加载完成 (路径, 是否成功)
    preload_progress = pyqtSignal(str, int)  # 预加载进度 (路径, 百分比)
    cache_updated = pyqtSignal(dict)  # 缓存更新
    
    def __init__(self, cache: Optional[AudioCache] = None, max_workers: int = 2):
        super().__init__()
        self.cache = cache or AudioCache()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AudioPreload")
        self._pending_tasks: Dict[str, PreloadTask] = {}
        self._lock = threading.RLock()
        self._shutdown = False
        
        # 初始化 pygame mixer
        self._init_mixer()
        
    def _init_mixer(self):
        """初始化 pygame mixer"""
        if not PYGAME_AVAILABLE:
            return
            
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            print("[AudioPreloader] pygame mixer 初始化成功")
        except Exception as e:
            print(f"[AudioPreloader] pygame mixer 初始化失败: {e}")
    
    def preload(self, file_path: str, priority: int = 0) -> bool:
        """
        预加载音频文件
        
        Args:
            file_path: 音频文件路径
            priority: 优先级 (越高越先加载)
            
        Returns:
            是否成功提交任务
        """
        if self._shutdown:
            return False
            
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return False
            
        # 检查是否已缓存
        if self.cache.contains(file_path):
            print(f"[AudioPreloader] 已缓存: {Path(file_path).name}")
            return True
            
        with self._lock:
            # 检查是否已在加载
            if file_path in self._pending_tasks:
                return True
                
            # 创建任务
            task = PreloadTask(file_path, priority)
            task.future = self._executor.submit(self._load_audio, file_path)
            self._pending_tasks[file_path] = task
            
        self.preload_started.emit(file_path)
        print(f"[AudioPreloader] 开始预加载: {Path(file_path).name}")
        return True
        
    def preload_batch(self, file_paths: List[str], priorities: Optional[List[int]] = None):
        """批量预加载"""
        if priorities is None:
            priorities = list(range(len(file_paths), 0, -1))
            
        for path, priority in zip(file_paths, priorities):
            self.preload(path, priority)
            
    def _load_audio(self, file_path: str) -> Optional[CachedAudio]:
        """加载音频 (在后台线程执行)"""
        try:
            start_time = time.time()
            
            if not PYGAME_AVAILABLE:
                return None
                
            # 加载 pygame Sound
            sound = pygame.mixer.Sound(file_path)
            duration_ms = int(sound.get_length() * 1000)
            
            # 获取文件大小
            size_bytes = os.path.getsize(file_path)
            
            # 加载 pydub AudioSegment (用于 seek)
            audio_segment = None
            if PYDUB_AVAILABLE:
                try:
                    audio_segment = AudioSegment.from_file(file_path)
                except Exception as e:
                    print(f"[AudioPreloader] pydub 加载失败: {e}")
                    
            # 创建缓存对象
            cached = CachedAudio(
                file_path=file_path,
                sound=sound,
                audio_segment=audio_segment,
                duration_ms=duration_ms,
                size_bytes=size_bytes
            )
            
            # 存入缓存
            self.cache.put(file_path, cached)
            
            load_time = time.time() - start_time
            print(f"[AudioPreloader] 预加载完成: {Path(file_path).name} ({load_time:.2f}s, {size_bytes/1024/1024:.1f}MB)")
            
            # 移除待处理任务
            with self._lock:
                if file_path in self._pending_tasks:
                    del self._pending_tasks[file_path]
                    
            # 发送完成信号
            self.preload_finished.emit(file_path, True)
            self.cache_updated.emit(self.cache.get_stats())
            
            return cached
            
        except Exception as e:
            print(f"[AudioPreloader] 加载失败 {file_path}: {e}")
            
            with self._lock:
                if file_path in self._pending_tasks:
                    del self._pending_tasks[file_path]
                    
            self.preload_finished.emit(file_path, False)
            return None
            
    def cancel(self, file_path: str):
        """取消预加载任务"""
        with self._lock:
            if file_path in self._pending_tasks:
                task = self._pending_tasks[file_path]
                if task.future and not task.future.done():
                    task.future.cancel()
                del self._pending_tasks[file_path]
                
    def cancel_all(self):
        """取消所有预加载任务"""
        with self._lock:
            for path in list(self._pending_tasks.keys()):
                self.cancel(path)
                
    def is_loading(self, file_path: str) -> bool:
        """检查是否正在加载"""
        with self._lock:
            return file_path in self._pending_tasks
            
    def is_cached(self, file_path: str) -> bool:
        """检查是否已缓存"""
        return self.cache.contains(file_path)
        
    def get_cached(self, file_path: str) -> Optional[CachedAudio]:
        """获取缓存的音频"""
        return self.cache.get(file_path)
        
    def wait_for_load(self, file_path: str, timeout: float = 10.0) -> Optional[CachedAudio]:
        """等待加载完成"""
        start = time.time()
        
        while time.time() - start < timeout:
            # 检查缓存
            cached = self.cache.get(file_path)
            if cached:
                return cached
                
            # 检查是否在加载
            with self._lock:
                if file_path not in self._pending_tasks:
                    # 未在加载，开始加载
                    self.preload(file_path, priority=100)
                    
            time.sleep(0.05)
            
        return None
        
    def shutdown(self):
        """关闭预加载器"""
        self._shutdown = True
        self.cancel_all()
        self._executor.shutdown(wait=False)
        self.cache.clear()


class SmartPreloader(QObject):
    """
    智能预加载器
    
    根据播放模式和当前位置，智能预测并预加载歌曲
    """
    
    def __init__(self, preloader: AudioPreloader):
        super().__init__()
        self.preloader = preloader
        self._songs: List[Any] = []  # SongInfo 列表
        self._current_index: int = -1
        self._play_mode: str = "sequential"  # sequential, shuffle, repeat_one
        self._shuffle_order: List[int] = []
        self._shuffle_index: int = 0
        
    def set_playlist(self, songs: List[Any]):
        """设置播放列表"""
        self._songs = songs
        self._preload_nearby()
        
    def set_current_index(self, index: int):
        """设置当前播放索引"""
        self._current_index = index
        self._preload_nearby()
        
    def set_play_mode(self, mode: str):
        """设置播放模式"""
        self._play_mode = mode
        self._preload_nearby()
        
    def set_shuffle_state(self, order: List[int], index: int):
        """设置随机播放状态"""
        self._shuffle_order = order
        self._shuffle_index = index
        
    def _preload_nearby(self):
        """预加载附近的歌曲"""
        if not self._songs or self._current_index < 0:
            return
            
        to_preload = []
        
        if self._play_mode == "sequential":
            # 顺序播放：预加载下一首和前一首
            next_idx = (self._current_index + 1) % len(self._songs)
            prev_idx = (self._current_index - 1) % len(self._songs)
            
            if next_idx != self._current_index:
                to_preload.append((self._songs[next_idx], 2))  # 下一首优先级高
            if prev_idx != self._current_index:
                to_preload.append((self._songs[prev_idx], 1))
                
        elif self._play_mode == "shuffle":
            # 随机播放：预加载随机列表中的下一首
            if self._shuffle_order and self._shuffle_index >= 0:
                next_shuffle_idx = (self._shuffle_index + 1) % len(self._shuffle_order)
                if next_shuffle_idx < len(self._shuffle_order):
                    song_idx = self._shuffle_order[next_shuffle_idx]
                    if song_idx < len(self._songs):
                        to_preload.append((self._songs[song_idx], 2))
                        
        elif self._play_mode == "repeat_one":
            # 单曲循环：当前歌曲已加载，无需预加载
            pass
            
        # 执行预加载
        for song, priority in to_preload:
            if hasattr(song, 'path') and song.path and not song.is_online:
                if hasattr(song, 'has_stems') and song.has_stems and hasattr(song, 'stems_path'):
                    # 预加载分离音轨
                    stems_path = song.stems_path
                    if os.path.exists(stems_path):
                        for f in os.listdir(stems_path):
                            if f.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                                self.preloader.preload(os.path.join(stems_path, f), priority)
                else:
                    # 预加载主音频
                    self.preloader.preload(song.path, priority)
                    
    def on_song_ended(self):
        """歌曲播放结束时触发"""
        # 预加载更多歌曲
        self._preload_nearby()


# 全局预加载器实例
_global_cache: Optional[AudioCache] = None
_global_preloader: Optional[AudioPreloader] = None


def get_audio_cache() -> AudioCache:
    """获取全局音频缓存"""
    global _global_cache
    if _global_cache is None:
        _global_cache = AudioCache(max_size=10, max_memory_mb=500)
    return _global_cache


def get_audio_preloader() -> AudioPreloader:
    """获取全局预加载器"""
    global _global_preloader
    if _global_preloader is None:
        _global_preloader = AudioPreloader(get_audio_cache())
    return _global_preloader
