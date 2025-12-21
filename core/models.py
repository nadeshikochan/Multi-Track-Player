"""
核心数据模型
"""

import os
import glob
import random
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QThread, pyqtSignal, QAbstractTableModel, QModelIndex, Qt

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("警告: mutagen未安装，请运行: pip install mutagen")

SUPPORTED_FORMATS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma', '.opus'}
COVER_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
LYRICS_FORMATS = {'.lrc', '.txt'}


@dataclass
class SongInfo:
    """歌曲信息数据类"""
    path: str
    filename: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    cover_data: bytes = None
    cover_path: str = ""
    lyrics: str = ""
    lyrics_path: str = ""
    has_stems: bool = False
    stems_path: str = ""
    # 在线歌曲相关
    is_online: bool = False
    online_url: str = ""
    source: str = ""  # 音源: kw, kg, tx, wy, mg
    song_id: str = ""
    
    def __post_init__(self):
        if not self.title:
            self.title = Path(self.filename).stem


@dataclass  
class LyricLine:
    """歌词行数据"""
    time: float  # 秒
    text: str
    translation: str = ""  # 翻译
    
    
class LyricsParser:
    """LRC歌词解析器"""
    
    @staticmethod
    def parse(lrc_text: str) -> List[LyricLine]:
        """解析LRC格式歌词"""
        lines = []
        if not lrc_text:
            return lines
            
        # 分离日文/中文歌词
        all_lines = lrc_text.strip().split('\n')
        
        # 解析时间戳格式 [mm:ss.xx] 或 [mm:ss:xx]
        pattern = r'\[(\d+):(\d+)(?:[.:]+(\d+))?\](.+)?'
        
        parsed_dict = {}  # 按时间存储
        
        for line in all_lines:
            line = line.strip()
            if not line:
                continue
                
            matches = re.findall(pattern, line)
            for match in matches:
                minutes = int(match[0])
                seconds = int(match[1])
                ms = int(match[2]) if match[2] else 0
                # 处理毫秒格式
                if ms > 99:
                    ms = ms // 10
                text = match[3].strip() if match[3] else ""
                
                time_sec = minutes * 60 + seconds + ms / 100.0
                
                if time_sec not in parsed_dict:
                    parsed_dict[time_sec] = LyricLine(time=time_sec, text=text)
                elif text and not parsed_dict[time_sec].translation:
                    # 同时间戳的第二行作为翻译
                    parsed_dict[time_sec].translation = text
                    
        lines = sorted(parsed_dict.values(), key=lambda x: x.time)
        return lines


class SongScanner(QThread):
    """歌曲扫描线程"""
    progress = pyqtSignal(int, int)
    song_found = pyqtSignal(object)
    finished_scan = pyqtSignal(list)
    
    def __init__(self, music_path: str, stems_path: str = ""):
        super().__init__()
        self.music_path = music_path
        self.stems_path = stems_path
        self._stop_flag = False
        
    def stop(self):
        self._stop_flag = True
        
    def run(self):
        songs = []
        if not self.music_path or not os.path.exists(self.music_path):
            self.finished_scan.emit(songs)
            return
            
        all_files = []
        for root, dirs, files in os.walk(self.music_path):
            for f in files:
                if f.lower().endswith(tuple(SUPPORTED_FORMATS)):
                    all_files.append(os.path.join(root, f))
                    
        total = len(all_files)
        stems_dict = self._get_stems_dict()
        
        for i, filepath in enumerate(all_files):
            if self._stop_flag:
                break
            song = self._scan_single_file(filepath, stems_dict)
            if song:
                songs.append(song)
                self.song_found.emit(song)
            if i % 50 == 0:
                self.progress.emit(i + 1, total)
                
        self.progress.emit(total, total)
        self.finished_scan.emit(songs)
        
    def _get_stems_dict(self) -> Dict[str, str]:
        """获取所有stems文件夹，返回 {规范化名称: 实际路径} 的字典"""
        stems_dict = {}
        if self.stems_path and os.path.exists(self.stems_path):
            for item in os.listdir(self.stems_path):
                item_path = os.path.join(self.stems_path, item)
                if os.path.isdir(item_path):
                    # 检查文件夹中是否有音频文件
                    has_audio = any(
                        f.lower().endswith(tuple(SUPPORTED_FORMATS))
                        for f in os.listdir(item_path)
                        if os.path.isfile(os.path.join(item_path, f))
                    )
                    if has_audio:
                        # 使用规范化的名称作为key，便于匹配
                        normalized_name = self._normalize_song_name(item)
                        stems_dict[normalized_name] = item_path
                        # 同时保存原始名称
                        stems_dict[item] = item_path
        return stems_dict
    
    @staticmethod
    def _normalize_song_name(name: str) -> str:
        """规范化歌曲名称用于匹配"""
        # 移除常见的后缀和括号内容
        import re
        # 移除括号内容如 (Official Video), [HD] 等
        name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', name)
        # 移除常见后缀
        for suffix in [' - ', '_', '.']:
            if suffix in name:
                parts = name.split(suffix)
                name = parts[0]
        # 转小写并移除多余空格
        name = name.lower().strip()
        name = re.sub(r'\s+', ' ', name)
        return name
        
    def _scan_single_file(self, filepath: str, stems_dict: Dict[str, str]) -> Optional[SongInfo]:
        try:
            filename = os.path.basename(filepath)
            song = SongInfo(path=filepath, filename=filename)
            folder = os.path.dirname(filepath)
            stem_name = Path(filename).stem
            
            # 尝试多种匹配方式
            stems_path = None
            
            # 1. 精确匹配文件名（不含扩展名）
            if stem_name in stems_dict:
                stems_path = stems_dict[stem_name]
            else:
                # 2. 规范化名称匹配
                normalized = self._normalize_song_name(stem_name)
                if normalized in stems_dict:
                    stems_path = stems_dict[normalized]
                    
            if stems_path:
                song.has_stems = True
                song.stems_path = stems_path
                
            if HAS_MUTAGEN:
                try:
                    audio = MutagenFile(filepath)
                    if audio:
                        if hasattr(audio.info, 'length'):
                            song.duration = audio.info.length
                        if hasattr(audio, 'tags') and audio.tags:
                            tags = audio.tags
                            if hasattr(tags, 'get'):
                                song.title = self._get_tag(tags, ['TIT2', 'title', '\xa9nam', 'TITLE']) or song.title
                                song.artist = self._get_tag(tags, ['TPE1', 'artist', '\xa9ART', 'ARTIST']) or "未知艺术家"
                                song.album = self._get_tag(tags, ['TALB', 'album', '\xa9alb', 'ALBUM']) or ""
                                song.cover_data = self._get_cover(tags)
                                song.lyrics = self._get_lyrics_embedded(tags)
                except Exception:
                    pass
                    
            # 外部封面文件
            if not song.cover_data:
                song.cover_path = self._find_cover_file(folder, stem_name)
                if song.cover_path:
                    try:
                        with open(song.cover_path, 'rb') as f:
                            song.cover_data = f.read()
                    except Exception:
                        pass
                        
            # 外部歌词文件
            if not song.lyrics:
                song.lyrics_path = self._find_lyrics_file(folder, stem_name)
                if song.lyrics_path:
                    try:
                        with open(song.lyrics_path, 'r', encoding='utf-8', errors='ignore') as f:
                            song.lyrics = f.read()
                    except Exception:
                        pass
                    
            return song
        except Exception:
            return None
            
    def _find_cover_file(self, folder: str, song_name: str) -> str:
        for ext in COVER_FORMATS:
            cover_path = os.path.join(folder, song_name + ext)
            if os.path.exists(cover_path):
                return cover_path
        common_names = ['cover', 'folder', 'album', 'front', 'art', 'artwork', '封面']
        for name in common_names:
            for ext in COVER_FORMATS:
                cover_path = os.path.join(folder, name + ext)
                if os.path.exists(cover_path):
                    return cover_path
        for ext in COVER_FORMATS:
            pattern = os.path.join(folder, f"*{ext}")
            matches = glob.glob(pattern)
            if matches:
                return matches[0]
        return ""
        
    def _find_lyrics_file(self, folder: str, song_name: str) -> str:
        for ext in LYRICS_FORMATS:
            lyrics_path = os.path.join(folder, song_name + ext)
            if os.path.exists(lyrics_path):
                return lyrics_path
        return ""
            
    def _get_tag(self, tags, keys: List[str]) -> str:
        for key in keys:
            try:
                if key in tags:
                    val = tags[key]
                    if hasattr(val, 'text'):
                        return str(val.text[0]) if val.text else ""
                    elif isinstance(val, list):
                        return str(val[0]) if val else ""
                    else:
                        return str(val)
            except Exception:
                continue
        return ""
        
    def _get_cover(self, tags) -> Optional[bytes]:
        try:
            for key in tags.keys():
                if key.startswith('APIC'):
                    return tags[key].data
            if hasattr(tags, 'pictures') and tags.pictures:
                return tags.pictures[0].data
            if 'covr' in tags:
                return bytes(tags['covr'][0])
        except Exception:
            pass
        return None
        
    def _get_lyrics_embedded(self, tags) -> str:
        try:
            # ID3 USLT
            for key in tags.keys():
                if key.startswith('USLT'):
                    lyric = tags[key]
                    if hasattr(lyric, 'text'):
                        return lyric.text
                    return str(lyric)
            # FLAC LYRICS
            if 'LYRICS' in tags:
                val = tags['LYRICS']
                if isinstance(val, list):
                    return str(val[0])
                return str(val)
        except Exception:
            pass
        return ""


class VirtualSongListModel(QAbstractTableModel):
    """虚拟歌曲列表模型 - 支持高性能大列表"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.songs: List[SongInfo] = []
        self.filtered_songs: List[SongInfo] = []
        self.filter_text = ""
        
    def set_songs(self, songs: List[SongInfo]):
        self.beginResetModel()
        self.songs = songs
        self._apply_filter()
        self.endResetModel()
        
    def add_song(self, song: SongInfo):
        if self._matches_filter(song):
            row = len(self.filtered_songs)
            self.beginInsertRows(QModelIndex(), row, row)
            self.filtered_songs.append(song)
            self.endInsertRows()
        self.songs.append(song)
        
    def set_filter(self, text: str):
        self.beginResetModel()
        self.filter_text = text.lower()
        self._apply_filter()
        self.endResetModel()
        
    def _apply_filter(self):
        if not self.filter_text:
            self.filtered_songs = self.songs.copy()
        else:
            self.filtered_songs = [s for s in self.songs if self._matches_filter(s)]
            
    def _matches_filter(self, song: SongInfo) -> bool:
        """模糊搜索匹配
        
        支持:
        1. 连续匹配: 输入的字符按顺序出现在目标中
        2. 多关键词: 空格分隔的多个关键词都需要匹配
        3. 拼音首字母匹配 (可选)
        """
        if not self.filter_text:
            return True
            
        # 分割关键词
        keywords = self.filter_text.split()
        
        # 搜索目标
        targets = [
            song.title.lower(),
            song.artist.lower(),
            song.filename.lower(),
            song.album.lower() if song.album else ""
        ]
        
        # 每个关键词都需要匹配至少一个目标
        for keyword in keywords:
            keyword_matched = False
            for target in targets:
                if self._fuzzy_match(keyword, target):
                    keyword_matched = True
                    break
            if not keyword_matched:
                return False
        return True
    
    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """模糊匹配 - 支持连续子串和跳跃匹配"""
        if not pattern:
            return True
        if not text:
            return False
            
        # 首先尝试简单的包含匹配
        if pattern in text:
            return True
            
        # 跳跃匹配 (pattern中的字符按顺序出现在text中)
        pattern_idx = 0
        for char in text:
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1
        
        return pattern_idx == len(pattern)
                
    def rowCount(self, parent=QModelIndex()):
        return len(self.filtered_songs)
        
    def columnCount(self, parent=QModelIndex()):
        return 4
        
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.filtered_songs):
            return None
        song = self.filtered_songs[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                prefix = "🌐 " if song.is_online else ""
                return prefix + song.title
            elif col == 1:
                return song.artist
            elif col == 2:
                mins = int(song.duration // 60)
                secs = int(song.duration % 60)
                return f"{mins}:{secs:02d}"
            elif col == 3:
                return "🎚️" if song.has_stems else ""
        elif role == Qt.ItemDataRole.UserRole:
            return song
        elif role == Qt.ItemDataRole.ToolTipRole:
            source_info = f"\n来源: {song.source}" if song.is_online else ""
            return f"{song.title}\n{song.artist}\n{song.path}{source_info}"
        return None
        
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            headers = ["标题", "艺术家", "时长", "分离"]
            return headers[section] if section < len(headers) else ""
        return None
        
    def get_song(self, row: int) -> Optional[SongInfo]:
        if 0 <= row < len(self.filtered_songs):
            return self.filtered_songs[row]
        return None
        
    def update_song(self, song: SongInfo):
        for i, s in enumerate(self.filtered_songs):
            if s.path == song.path:
                self.filtered_songs[i] = song
                self.dataChanged.emit(self.index(i, 0), self.index(i, 3))
                break
                
    def get_all_songs(self) -> List[SongInfo]:
        return self.songs.copy()


class SongCache:
    """歌曲缓存管理器 - 避免每次启动重新扫描"""
    
    def __init__(self, cache_dir: str = ""):
        if not cache_dir:
            # 默认缓存目录
            cache_dir = os.path.join(os.path.expanduser("~"), ".multi_track_player")
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "song_cache.json")
        os.makedirs(cache_dir, exist_ok=True)
        
    def save_cache(self, songs: List[SongInfo], music_path: str, stems_path: str):
        """保存歌曲列表到缓存"""
        try:
            cache_data = {
                "version": 2,
                "music_path": music_path,
                "stems_path": stems_path,
                "timestamp": os.path.getmtime(music_path) if os.path.exists(music_path) else 0,
                "songs": []
            }
            
            for song in songs:
                if song.is_online:
                    continue  # 不缓存在线歌曲
                song_data = {
                    "path": song.path,
                    "filename": song.filename,
                    "title": song.title,
                    "artist": song.artist,
                    "album": song.album,
                    "duration": song.duration,
                    "cover_path": song.cover_path,
                    "lyrics_path": song.lyrics_path,
                    "has_stems": song.has_stems,
                    "stems_path": song.stems_path,
                }
                cache_data["songs"].append(song_data)
                
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"保存缓存失败: {e}")
            
    def load_cache(self, music_path: str, stems_path: str) -> Optional[List[SongInfo]]:
        """从缓存加载歌曲列表，如果缓存有效的话"""
        try:
            if not os.path.exists(self.cache_file):
                return None
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # 检查版本
            if cache_data.get("version", 1) < 2:
                return None
                
            # 检查路径是否匹配
            if cache_data.get("music_path") != music_path:
                return None
            if cache_data.get("stems_path") != stems_path:
                return None
                
            # 加载歌曲
            songs = []
            for song_data in cache_data.get("songs", []):
                # 检查文件是否还存在
                if not os.path.exists(song_data["path"]):
                    continue
                    
                song = SongInfo(
                    path=song_data["path"],
                    filename=song_data["filename"],
                    title=song_data.get("title", ""),
                    artist=song_data.get("artist", ""),
                    album=song_data.get("album", ""),
                    duration=song_data.get("duration", 0),
                    cover_path=song_data.get("cover_path", ""),
                    lyrics_path=song_data.get("lyrics_path", ""),
                    has_stems=song_data.get("has_stems", False),
                    stems_path=song_data.get("stems_path", ""),
                )
                
                # 重新检查stems是否存在
                if song.has_stems and not os.path.exists(song.stems_path):
                    song.has_stems = False
                    song.stems_path = ""
                    
                # 加载封面数据
                if song.cover_path and os.path.exists(song.cover_path):
                    try:
                        with open(song.cover_path, 'rb') as cf:
                            song.cover_data = cf.read()
                    except Exception:
                        pass
                        
                # 加载歌词
                if song.lyrics_path and os.path.exists(song.lyrics_path):
                    try:
                        with open(song.lyrics_path, 'r', encoding='utf-8', errors='ignore') as lf:
                            song.lyrics = lf.read()
                    except Exception:
                        pass
                        
                songs.append(song)
                
            return songs if songs else None
            
        except Exception as e:
            print(f"加载缓存失败: {e}")
            return None
            
    def invalidate(self):
        """使缓存失效"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
        except Exception:
            pass
            
    def update_stems_status(self, songs: List[SongInfo], stems_path: str):
        """更新歌曲的stems状态（用于分离完成后）"""
        if not stems_path or not os.path.exists(stems_path):
            return
            
        stems_folders = set()
        for item in os.listdir(stems_path):
            item_path = os.path.join(stems_path, item)
            if os.path.isdir(item_path):
                # 检查是否有音频文件
                has_audio = any(
                    f.lower().endswith(tuple(SUPPORTED_FORMATS))
                    for f in os.listdir(item_path)
                    if os.path.isfile(os.path.join(item_path, f))
                )
                if has_audio:
                    stems_folders.add(item)
                    
        for song in songs:
            stem_name = Path(song.filename).stem
            if stem_name in stems_folders and not song.has_stems:
                song.has_stems = True
                song.stems_path = os.path.join(stems_path, stem_name)


# 需要导入json
import json

