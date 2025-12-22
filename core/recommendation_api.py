"""
歌曲推荐系统接口

本模块提供与外部歌曲推荐系统对接的接口。

使用方法:
---------
1. 继承 RecommendationProvider 类实现你自己的推荐逻辑
2. 或者通过 HTTP API 方式与本播放器通信

HTTP API:
---------
播放器会启动一个本地HTTP服务器(默认端口: 23331)

POST /api/recommend/next
  请求: {"current_song": {...}, "history": [...], "context": {...}}
  响应: {"song": {...}, "reason": "推荐理由"}

POST /api/recommend/playlist
  请求: {"seed_songs": [...], "count": 10}
  响应: {"songs": [...]}

GET /api/player/status
  响应: {"playing": true, "current_song": {...}, "progress": 0.5}

POST /api/player/play
  请求: {"song": {...}}
  响应: {"success": true}

示例代码:
--------
```python
from recommendation_api import RecommendationProvider, SongRecommendation

class MyRecommender(RecommendationProvider):
    def get_next_song(self, current_song, history, context):
        # 你的推荐逻辑
        return SongRecommendation(
            song_info={...},
            reason="基于你的听歌历史推荐"
        )
        
# 在播放器中注册
player.set_recommendation_provider(MyRecommender())
```
"""

import json
import threading
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Callable
from abc import ABC, abstractmethod
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse


@dataclass
class SongRecommendation:
    """推荐结果"""
    song_info: Dict[str, Any]  # 歌曲信息
    reason: str = ""  # 推荐理由
    confidence: float = 1.0  # 置信度 0-1
    source: str = "recommendation"  # 来源标识
    

@dataclass
class PlayContext:
    """播放上下文"""
    time_of_day: str = ""  # morning, afternoon, evening, night
    mood: str = ""  # happy, sad, energetic, calm, etc.
    activity: str = ""  # workout, study, relax, commute, etc.
    repeat_mode: str = ""  # sequential, shuffle, repeat_one
    

class RecommendationProvider(ABC):
    """推荐提供者抽象基类
    
    实现这个类来提供自定义的歌曲推荐逻辑
    """
    
    @abstractmethod
    def get_next_song(self, 
                      current_song: Optional[Dict], 
                      history: List[Dict],
                      context: PlayContext) -> Optional[SongRecommendation]:
        """获取下一首推荐歌曲
        
        Args:
            current_song: 当前播放的歌曲信息，如果没有则为None
            history: 最近播放历史（最多50首）
            context: 播放上下文
            
        Returns:
            推荐结果，如果没有推荐则返回None
        """
        pass
        
    @abstractmethod
    def get_playlist(self,
                     seed_songs: List[Dict],
                     count: int = 10,
                     context: Optional[PlayContext] = None) -> List[SongRecommendation]:
        """生成推荐播放列表
        
        Args:
            seed_songs: 种子歌曲列表
            count: 需要生成的歌曲数量
            context: 播放上下文
            
        Returns:
            推荐歌曲列表
        """
        pass
        
    def on_song_played(self, song: Dict, duration: float, completed: bool):
        """歌曲播放回调
        
        当一首歌曲播放结束时调用，用于收集反馈
        
        Args:
            song: 播放的歌曲信息
            duration: 实际播放时长（秒）
            completed: 是否完整播放
        """
        pass
        
    def on_song_skipped(self, song: Dict, position: float):
        """歌曲跳过回调
        
        Args:
            song: 被跳过的歌曲
            position: 跳过时的播放位置（秒）
        """
        pass
        
    def on_song_liked(self, song: Dict, liked: bool):
        """歌曲收藏/取消收藏回调
        
        Args:
            song: 歌曲信息
            liked: True表示收藏，False表示取消收藏
        """
        pass


class DefaultRecommendationProvider(RecommendationProvider):
    """默认推荐提供者 - 随机推荐"""
    
    def __init__(self):
        self.song_pool: List[Dict] = []
        
    def set_song_pool(self, songs: List[Dict]):
        """设置歌曲池"""
        self.song_pool = songs
        
    def get_next_song(self, current_song, history, context) -> Optional[SongRecommendation]:
        import random
        if not self.song_pool:
            return None
            
        # 排除最近播放的歌曲
        recent_paths = {h.get('path') for h in history[-10:]} if history else set()
        if current_song:
            recent_paths.add(current_song.get('path'))
            
        available = [s for s in self.song_pool if s.get('path') not in recent_paths]
        
        if not available:
            available = self.song_pool
            
        selected = random.choice(available)
        return SongRecommendation(song_info=selected, reason="随机推荐")
        
    def get_playlist(self, seed_songs, count=10, context=None) -> List[SongRecommendation]:
        import random
        if not self.song_pool:
            return []
            
        seed_paths = {s.get('path') for s in seed_songs}
        available = [s for s in self.song_pool if s.get('path') not in seed_paths]
        
        selected = random.sample(available, min(count, len(available)))
        return [SongRecommendation(song_info=s, reason="随机推荐") for s in selected]


class RecommendationAPIHandler(BaseHTTPRequestHandler):
    """HTTP API处理器"""
    
    provider: Optional[RecommendationProvider] = None
    player_callback: Optional[Callable] = None
    
    def log_message(self, format, *args):
        pass  # 静默日志
        
    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        
    def _read_json(self) -> Optional[dict]:
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            return json.loads(body.decode('utf-8'))
        except Exception:
            return None
            
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/api/player/status':
            if self.player_callback:
                status = self.player_callback('get_status')
                self._send_json(status or {})
            else:
                self._send_json({'error': 'Player not connected'}, 503)
                
        elif path == '/api/health':
            self._send_json({'status': 'ok', 'version': '3.0'})
            
        else:
            self._send_json({'error': 'Not found'}, 404)
            
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        
        if path == '/api/recommend/next':
            if not self.provider:
                self._send_json({'error': 'No recommendation provider'}, 503)
                return
                
            current = data.get('current_song') if data else None
            history = data.get('history', []) if data else []
            ctx_data = data.get('context', {}) if data else {}
            context = PlayContext(**ctx_data) if ctx_data else PlayContext()
            
            result = self.provider.get_next_song(current, history, context)
            if result:
                self._send_json(asdict(result))
            else:
                self._send_json({'error': 'No recommendation available'}, 404)
                
        elif path == '/api/recommend/playlist':
            if not self.provider:
                self._send_json({'error': 'No recommendation provider'}, 503)
                return
                
            seeds = data.get('seed_songs', []) if data else []
            count = data.get('count', 10) if data else 10
            ctx_data = data.get('context', {}) if data else {}
            context = PlayContext(**ctx_data) if ctx_data else None
            
            results = self.provider.get_playlist(seeds, count, context)
            self._send_json({'songs': [asdict(r) for r in results]})
            
        elif path == '/api/player/play':
            if not self.player_callback:
                self._send_json({'error': 'Player not connected'}, 503)
                return
                
            song = data.get('song') if data else None
            if song:
                result = self.player_callback('play_song', song)
                self._send_json({'success': result})
            else:
                self._send_json({'error': 'No song provided'}, 400)
                
        elif path == '/api/player/next':
            if self.player_callback:
                self.player_callback('play_next')
                self._send_json({'success': True})
            else:
                self._send_json({'error': 'Player not connected'}, 503)
                
        elif path == '/api/feedback/played':
            if self.provider and data:
                self.provider.on_song_played(
                    data.get('song', {}),
                    data.get('duration', 0),
                    data.get('completed', False)
                )
            self._send_json({'success': True})
            
        elif path == '/api/feedback/skipped':
            if self.provider and data:
                self.provider.on_song_skipped(
                    data.get('song', {}),
                    data.get('position', 0)
                )
            self._send_json({'success': True})
            
        else:
            self._send_json({'error': 'Not found'}, 404)


class RecommendationAPIServer:
    """推荐API服务器"""
    
    def __init__(self, port: int = 23331):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.provider: Optional[RecommendationProvider] = None
        self.player_callback: Optional[Callable] = None
        
    def set_provider(self, provider: RecommendationProvider):
        """设置推荐提供者"""
        self.provider = provider
        RecommendationAPIHandler.provider = provider
        
    def set_player_callback(self, callback: Callable):
        """设置播放器回调"""
        self.player_callback = callback
        RecommendationAPIHandler.player_callback = callback
        
    def start(self):
        """启动服务器"""
        if self.server:
            return
            
        try:
            self.server = HTTPServer(('127.0.0.1', self.port), RecommendationAPIHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            print(f"[播放器内置API] 推荐接口已启动 (端口: {self.port})")
        except Exception as e:
            print(f"推荐API服务器启动失败: {e}")
            
    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            self.server = None
            self.thread = None
