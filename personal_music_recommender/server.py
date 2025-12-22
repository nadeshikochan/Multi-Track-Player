"""
扩展的推荐API服务器

在原有recommendation_api.py的基础上扩展更多端点：
- 正负反馈
- 学习统计
- 会话管理
- 模型导入导出
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from typing import Optional, Callable, Dict, Any
from dataclasses import asdict

# 导入适配器
from adapter import PersonalRecommendationAdapter
from personal_recommender import SongFeatures


class ExtendedAPIHandler(BaseHTTPRequestHandler):
    """扩展的HTTP API处理器"""
    
    adapter: Optional[PersonalRecommendationAdapter] = None
    player_callback: Optional[Callable] = None
    
    def log_message(self, format, *args):
        # 可以选择开启或关闭日志
        # print(f"[API] {format % args}")
        pass
    
    def _send_json(self, data: dict, status: int = 200):
        """发送JSON响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def _read_json(self) -> Optional[dict]:
        """读取JSON请求体"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                return {}
            body = self.rfile.read(content_length)
            return json.loads(body.decode('utf-8'))
        except Exception:
            return None
    
    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """处理GET请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/api/health':
            self._send_json({
                'status': 'ok',
                'version': '3.0-personal',
                'features': ['personal_learning', 'feedback', 'statistics']
            })
        
        elif path == '/api/player/status':
            if self.player_callback:
                status = self.player_callback('get_status')
                self._send_json(status or {})
            else:
                self._send_json({'error': 'Player not connected'}, 503)
        
        elif path == '/api/stats':
            # 获取学习统计
            if self.adapter:
                stats = self.adapter.get_statistics()
                self._send_json(stats)
            else:
                self._send_json({'error': 'Adapter not initialized'}, 503)
        
        elif path == '/api/session':
            # 获取当前会话状态
            if self.adapter:
                stats = self.adapter.get_statistics()
                self._send_json(stats.get('session', {}))
            else:
                self._send_json({'error': 'Adapter not initialized'}, 503)
        
        elif path == '/api/songs':
            # 获取所有歌曲的学习数据
            if self.adapter:
                songs_data = {}
                for path, song in self.adapter.recommender.songs.items():
                    songs_data[path] = {
                        'title': song.title,
                        'artist': song.artist,
                        'preference_score': round(song.preference_score, 3),
                        'preference_confidence': round(song.preference_confidence, 3),
                        'play_count': song.play_count,
                        'complete_count': song.complete_count,
                        'skip_count': song.skip_count
                    }
                self._send_json({'songs': songs_data, 'count': len(songs_data)})
            else:
                self._send_json({'error': 'Adapter not initialized'}, 503)
        
        elif path.startswith('/api/song/'):
            # 获取单首歌曲的详细数据
            song_path = urllib.parse.unquote(path[10:])  # 去掉 /api/song/ 前缀
            if self.adapter and song_path in self.adapter.recommender.songs:
                song = self.adapter.recommender.songs[song_path]
                self._send_json(asdict(song))
            else:
                self._send_json({'error': 'Song not found'}, 404)
        
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        """处理POST请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        
        # === 推荐相关 ===
        
        if path == '/api/recommend/next':
            if not self.adapter:
                self._send_json({'error': 'Adapter not initialized'}, 503)
                return
            
            from adapter import PlayContext
            
            current = data.get('current_song') if data else None
            history = data.get('history', []) if data else []
            ctx_data = data.get('context', {}) if data else {}
            context = PlayContext(**ctx_data) if ctx_data else PlayContext()
            
            result = self.adapter.get_next_song(current, history, context)
            if result:
                self._send_json({
                    'song_info': result.song_info,
                    'reason': result.reason,
                    'confidence': result.confidence,
                    'source': result.source
                })
            else:
                self._send_json({'error': 'No recommendation available'}, 404)
        
        elif path == '/api/recommend/playlist':
            if not self.adapter:
                self._send_json({'error': 'Adapter not initialized'}, 503)
                return
            
            from adapter import PlayContext
            
            seeds = data.get('seed_songs', []) if data else []
            count = data.get('count', 10) if data else 10
            ctx_data = data.get('context', {}) if data else {}
            context = PlayContext(**ctx_data) if ctx_data else None
            
            results = self.adapter.get_playlist(seeds, count, context)
            self._send_json({
                'songs': [{
                    'song_info': r.song_info,
                    'reason': r.reason,
                    'confidence': r.confidence,
                    'source': r.source
                } for r in results]
            })
        
        # === 播放器控制 ===
        
        elif path == '/api/player/play':
            if not self.player_callback:
                self._send_json({'error': 'Player not connected'}, 503)
                return
            
            song = data.get('song') if data else None
            if song:
                # 通知适配器歌曲开始播放
                if self.adapter:
                    self.adapter.on_song_start(song)
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
        
        # === 反馈相关 ===
        
        elif path == '/api/feedback/played':
            # 歌曲播放完成
            if self.adapter and data:
                self.adapter.on_song_played(
                    data.get('song', {}),
                    data.get('duration', 0),
                    data.get('completed', False)
                )
            self._send_json({'success': True})
        
        elif path == '/api/feedback/skipped':
            # 歌曲被跳过
            if self.adapter and data:
                self.adapter.on_song_skipped(
                    data.get('song', {}),
                    data.get('position', 0)
                )
            self._send_json({'success': True})
        
        elif path == '/api/feedback/liked':
            # 收藏/取消收藏
            if self.adapter and data:
                self.adapter.on_song_liked(
                    data.get('song', {}),
                    data.get('liked', True)
                )
            self._send_json({'success': True})
        
        elif path == '/api/feedback/positive':
            # 正向反馈按钮
            if self.adapter:
                self.adapter.on_positive_feedback()
                self._send_json({'success': True, 'message': '已强化当前推荐策略'})
            else:
                self._send_json({'error': 'Adapter not initialized'}, 503)
        
        elif path == '/api/feedback/negative':
            # 负向反馈按钮
            if self.adapter:
                self.adapter.on_negative_feedback()
                self._send_json({'success': True, 'message': '将增加推荐多样性'})
            else:
                self._send_json({'error': 'Adapter not initialized'}, 503)
        
        # === 会话管理 ===
        
        elif path == '/api/session/reset':
            # 重置会话
            if self.adapter:
                self.adapter.reset_session()
                self._send_json({'success': True, 'message': '会话已重置'})
            else:
                self._send_json({'error': 'Adapter not initialized'}, 503)
        
        # === 歌曲池管理 ===
        
        elif path == '/api/songs/register':
            # 注册歌曲池
            if self.adapter and data:
                songs = data.get('songs', [])
                self.adapter.set_song_pool(songs)
                self._send_json({
                    'success': True,
                    'message': f'已注册 {len(songs)} 首歌曲'
                })
            else:
                self._send_json({'error': 'Invalid request'}, 400)
        
        # === 数据管理 ===
        
        elif path == '/api/data/save':
            # 保存数据
            if self.adapter:
                self.adapter.save()
                self._send_json({'success': True, 'message': '数据已保存'})
            else:
                self._send_json({'error': 'Adapter not initialized'}, 503)
        
        elif path == '/api/data/export':
            # 导出模型
            if self.adapter and data:
                filepath = data.get('filepath', './model_export.json')
                self.adapter.export_model(filepath)
                self._send_json({
                    'success': True,
                    'message': f'模型已导出到 {filepath}'
                })
            else:
                self._send_json({'error': 'Invalid request'}, 400)
        
        elif path == '/api/data/import':
            # 导入模型
            if self.adapter and data:
                filepath = data.get('filepath')
                if filepath:
                    try:
                        self.adapter.import_model(filepath)
                        self._send_json({
                            'success': True,
                            'message': f'模型已从 {filepath} 导入'
                        })
                    except Exception as e:
                        self._send_json({'error': str(e)}, 400)
                else:
                    self._send_json({'error': 'No filepath provided'}, 400)
            else:
                self._send_json({'error': 'Invalid request'}, 400)
        
        else:
            self._send_json({'error': 'Not found'}, 404)


class PersonalRecommendationServer:
    """个人推荐API服务器"""
    
    def __init__(self, port: int = 23331, data_dir: str = "./recommender_data"):
        self.port = port
        self.data_dir = data_dir
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        
        # 初始化适配器
        self.adapter = PersonalRecommendationAdapter(data_dir)
        ExtendedAPIHandler.adapter = self.adapter
        
        self.player_callback: Optional[Callable] = None
    
    def set_player_callback(self, callback: Callable):
        """设置播放器回调"""
        self.player_callback = callback
        ExtendedAPIHandler.player_callback = callback
    
    def set_song_pool(self, songs: list):
        """设置歌曲池"""
        self.adapter.set_song_pool(songs)
    
    def start(self):
        """启动服务器"""
        if self.server:
            return
        
        try:
            self.server = HTTPServer(('127.0.0.1', self.port), ExtendedAPIHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            print(f"个人推荐API服务器已启动: http://127.0.0.1:{self.port}")
            print(f"数据目录: {self.data_dir}")
            self._print_endpoints()
        except Exception as e:
            print(f"服务器启动失败: {e}")
    
    def _print_endpoints(self):
        """打印可用端点"""
        print("\n可用API端点:")
        print("  GET  /api/health              - 健康检查")
        print("  GET  /api/stats               - 获取学习统计")
        print("  GET  /api/session             - 获取会话状态")
        print("  GET  /api/songs               - 获取所有歌曲学习数据")
        print("  GET  /api/song/<path>         - 获取单首歌曲详情")
        print("  POST /api/recommend/next      - 获取下一首推荐")
        print("  POST /api/recommend/playlist  - 生成推荐列表")
        print("  POST /api/feedback/played     - 歌曲播放完成反馈")
        print("  POST /api/feedback/skipped    - 歌曲跳过反馈")
        print("  POST /api/feedback/liked      - 收藏反馈")
        print("  POST /api/feedback/positive   - 正向反馈(推荐很棒)")
        print("  POST /api/feedback/negative   - 负向反馈(推荐不好)")
        print("  POST /api/session/reset       - 重置会话")
        print("  POST /api/songs/register      - 注册歌曲池")
        print("  POST /api/data/save           - 保存学习数据")
        print("  POST /api/data/export         - 导出模型")
        print("  POST /api/data/import         - 导入模型")
        print()
    
    def stop(self):
        """停止服务器"""
        if self.server:
            # 保存数据
            self.adapter.save()
            self.server.shutdown()
            self.server = None
            self.thread = None
            print("服务器已停止，数据已保存")
    
    def get_adapter(self) -> PersonalRecommendationAdapter:
        """获取适配器实例"""
        return self.adapter


def main():
    """主函数 - 独立运行服务器"""
    import argparse
    
    parser = argparse.ArgumentParser(description='个人音乐推荐API服务器')
    parser.add_argument('--port', type=int, default=23331, help='服务器端口')
    parser.add_argument('--data-dir', type=str, default='./recommender_data', help='数据目录')
    args = parser.parse_args()
    
    server = PersonalRecommendationServer(port=args.port, data_dir=args.data_dir)
    server.start()
    
    print("\n服务器正在运行，按 Ctrl+C 停止...")
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
        server.stop()
        print("再见！")


if __name__ == "__main__":
    main()
