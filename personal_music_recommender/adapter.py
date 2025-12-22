"""
推荐系统适配器 - 与音乐播放器API对接

这个模块将PersonalMusicRecommender适配到音乐播放器的RecommendationProvider接口
"""

import sys
import os
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

# 添加播放器根目录到路径，以便导入recommendation_api
# 使用时需要根据实际路径调整
PLAYER_ROOT = os.environ.get('MUSIC_PLAYER_ROOT', '..')
if PLAYER_ROOT not in sys.path:
    sys.path.insert(0, PLAYER_ROOT)

try:
    from recommendation_api import (
        RecommendationProvider, 
        SongRecommendation, 
        PlayContext,
        RecommendationAPIServer
    )
except ImportError:
    # 如果无法导入，提供本地定义以便独立测试
    print("警告：无法导入recommendation_api，使用本地定义")
    from dataclasses import dataclass
    from abc import ABC, abstractmethod
    
    @dataclass
    class SongRecommendation:
        song_info: Dict[str, Any]
        reason: str = ""
        confidence: float = 1.0
        source: str = "recommendation"
    
    @dataclass
    class PlayContext:
        time_of_day: str = ""
        mood: str = ""
        activity: str = ""
        repeat_mode: str = ""
    
    class RecommendationProvider(ABC):
        @abstractmethod
        def get_next_song(self, current_song, history, context) -> Optional[SongRecommendation]:
            pass
        
        @abstractmethod
        def get_playlist(self, seed_songs, count, context) -> List[SongRecommendation]:
            pass
        
        def on_song_played(self, song, duration, completed):
            pass
        
        def on_song_skipped(self, song, position):
            pass
        
        def on_song_liked(self, song, liked):
            pass
    
    class RecommendationAPIServer:
        def __init__(self, port=23331):
            self.port = port
        def set_provider(self, provider):
            pass
        def start(self):
            pass
        def stop(self):
            pass

from personal_recommender import PersonalMusicRecommender


class PersonalRecommendationAdapter(RecommendationProvider):
    """
    个人推荐系统适配器
    
    将PersonalMusicRecommender适配到RecommendationProvider接口
    """
    
    def __init__(self, data_dir: str = "./recommender_data"):
        """
        初始化适配器
        
        Args:
            data_dir: 数据存储目录
        """
        self.recommender = PersonalMusicRecommender(data_dir)
        self._current_song_start: Dict[str, float] = {}  # 记录每首歌的开始时间
        self._last_completed_song: Optional[Dict] = None
        
        print(f"个人推荐系统已初始化，数据目录: {data_dir}")
        stats = self.recommender.get_statistics()
        print(f"已加载 {stats['total_songs']} 首歌曲的学习数据")
    
    def set_song_pool(self, songs: List[Dict]):
        """
        设置歌曲池
        
        Args:
            songs: 歌曲信息列表
        """
        self.recommender.register_song_pool(songs)
        print(f"歌曲池已更新，共 {len(songs)} 首歌曲")
    
    def get_next_song(self, 
                      current_song: Optional[Dict],
                      history: List[Dict],
                      context: PlayContext) -> Optional[SongRecommendation]:
        """
        获取下一首推荐歌曲
        
        实现RecommendationProvider接口
        """
        # 注册历史中的歌曲（如果还没注册）
        for song in history:
            self.recommender.register_song(song)
        
        # 排除最近播放的歌曲
        exclude = set(song.get('path') for song in history[-10:] if song.get('path'))
        
        # 考虑上下文调整策略
        self._apply_context(context)
        
        # 获取推荐
        result = self.recommender.get_next_recommendation(current_song, exclude)
        
        if result is None:
            return None
        
        song_info, reason = result
        
        # 根据置信度调整
        if song_info['path'] in self.recommender.songs:
            song_data = self.recommender.songs[song_info['path']]
            confidence = song_data.preference_confidence
        else:
            confidence = 0.5
        
        return SongRecommendation(
            song_info=song_info,
            reason=reason,
            confidence=confidence,
            source="personal_learning"
        )
    
    def get_playlist(self,
                     seed_songs: List[Dict],
                     count: int = 10,
                     context: Optional[PlayContext] = None) -> List[SongRecommendation]:
        """
        生成推荐播放列表
        
        实现RecommendationProvider接口
        """
        if context:
            self._apply_context(context)
        
        results = self.recommender.get_playlist_recommendations(seed_songs, count)
        
        recommendations = []
        for song_info, reason in results:
            if song_info['path'] in self.recommender.songs:
                confidence = self.recommender.songs[song_info['path']].preference_confidence
            else:
                confidence = 0.5
            
            recommendations.append(SongRecommendation(
                song_info=song_info,
                reason=reason,
                confidence=confidence,
                source="personal_learning"
            ))
        
        return recommendations
    
    def _apply_context(self, context: PlayContext):
        """根据上下文调整推荐参数"""
        # 可以根据时间、心情等调整参数
        if context.mood == 'energetic':
            # 精力充沛时增加探索
            self.recommender.exploration_rate = min(0.3, self.recommender.exploration_rate + 0.05)
        elif context.mood == 'calm':
            # 放松时减少探索，推荐熟悉的歌
            self.recommender.exploration_rate = max(0.05, self.recommender.exploration_rate - 0.05)
        
        if context.activity == 'workout':
            # 运动时可能更喜欢节奏感强的歌
            pass  # 可以扩展支持音频特征
    
    def on_song_played(self, song: Dict, duration: float, completed: bool):
        """
        歌曲播放完成回调
        
        Args:
            song: 播放的歌曲信息
            duration: 实际播放时长（秒）
            completed: 是否完整播放
        """
        path = song.get('path')
        if not path:
            return
        
        # 如果记录了开始时间，用实际时间
        if path in self._current_song_start:
            actual_duration = time.time() - self._current_song_start[path]
            del self._current_song_start[path]
        else:
            actual_duration = duration
        
        action = 'complete' if completed else 'next'
        
        self.recommender.on_song_end(song, actual_duration, action)
        
        if completed:
            self._last_completed_song = song
    
    def on_song_skipped(self, song: Dict, position: float):
        """
        歌曲被跳过回调
        
        Args:
            song: 被跳过的歌曲
            position: 跳过时的播放位置（秒）
        """
        path = song.get('path')
        if not path:
            return
        
        # 清理开始时间记录
        if path in self._current_song_start:
            del self._current_song_start[path]
        
        self.recommender.on_song_end(song, position, 'skip')
    
    def on_song_liked(self, song: Dict, liked: bool):
        """
        歌曲收藏/取消收藏回调
        
        Args:
            song: 歌曲信息
            liked: True表示收藏，False表示取消收藏
        """
        path = song.get('path')
        if not path or path not in self.recommender.songs:
            return
        
        song_data = self.recommender.songs[path]
        
        if liked:
            # 收藏：大幅提升偏好分数
            song_data.preference_score = min(1.0, song_data.preference_score + 0.3)
            song_data.preference_confidence = min(1.0, song_data.preference_confidence + 0.3)
        else:
            # 取消收藏：轻微降低
            song_data.preference_score = max(0, song_data.preference_score - 0.1)
    
    def on_song_start(self, song: Dict):
        """
        歌曲开始播放回调
        
        这是额外的回调方法，用于更精确地追踪播放时间
        """
        path = song.get('path')
        if path:
            self._current_song_start[path] = time.time()
            self.recommender.on_song_start(song)
    
    def on_positive_feedback(self):
        """用户点击正向反馈按钮"""
        self.recommender.on_positive_feedback()
    
    def on_negative_feedback(self):
        """用户点击负向反馈按钮"""
        self.recommender.on_negative_feedback()
    
    def get_statistics(self) -> Dict:
        """获取学习统计信息"""
        return self.recommender.get_statistics()
    
    def reset_session(self):
        """重置会话"""
        self.recommender.reset_session()
    
    def save(self):
        """保存学习数据"""
        self.recommender.save_data()
    
    def export_model(self, filepath: str):
        """导出模型"""
        self.recommender.export_model(filepath)
    
    def import_model(self, filepath: str):
        """导入模型"""
        self.recommender.import_model(filepath)


def create_recommendation_server(
    port: int = 23331,
    data_dir: str = "./recommender_data"
) -> tuple:
    """
    创建推荐服务器
    
    Args:
        port: 服务器端口
        data_dir: 数据存储目录
        
    Returns:
        (server, adapter) 元组
    """
    adapter = PersonalRecommendationAdapter(data_dir)
    server = RecommendationAPIServer(port)
    server.set_provider(adapter)
    
    return server, adapter


# 扩展API处理器，添加正负反馈端点
def extend_api_handler():
    """
    扩展HTTP API处理器
    
    添加以下端点:
    - POST /api/feedback/positive - 正向反馈
    - POST /api/feedback/negative - 负向反馈
    - GET /api/stats - 获取学习统计
    - POST /api/session/reset - 重置会话
    """
    # 这需要修改recommendation_api.py中的RecommendationAPIHandler
    # 这里提供一个扩展方案
    pass


if __name__ == "__main__":
    # 测试代码
    print("=== 个人推荐系统适配器测试 ===\n")
    
    # 创建适配器
    adapter = PersonalRecommendationAdapter("./test_data")
    
    # 模拟歌曲池
    test_songs = [
        {'path': '/music/song1.mp3', 'title': '歌曲1', 'artist': '艺术家A', 'duration': 180},
        {'path': '/music/song2.mp3', 'title': '歌曲2', 'artist': '艺术家B', 'duration': 200},
        {'path': '/music/song3.mp3', 'title': '歌曲3', 'artist': '艺术家A', 'duration': 220},
        {'path': '/music/song4.mp3', 'title': '歌曲4', 'artist': '艺术家C', 'duration': 190},
        {'path': '/music/song5.mp3', 'title': '歌曲5', 'artist': '艺术家B', 'duration': 210},
    ]
    
    adapter.set_song_pool(test_songs)
    
    # 模拟播放行为
    print("模拟播放行为...")
    
    # 播放歌曲1（完整播放）
    adapter.on_song_start(test_songs[0])
    time.sleep(0.1)
    adapter.on_song_played(test_songs[0], 180, completed=True)
    
    # 播放歌曲2（跳过）
    adapter.on_song_start(test_songs[1])
    time.sleep(0.1)
    adapter.on_song_skipped(test_songs[1], 30)
    
    # 播放歌曲3（完整播放）
    adapter.on_song_start(test_songs[2])
    time.sleep(0.1)
    adapter.on_song_played(test_songs[2], 220, completed=True)
    
    # 获取推荐
    print("\n获取推荐...")
    context = PlayContext(time_of_day='evening', mood='calm')
    rec = adapter.get_next_song(test_songs[2], test_songs[:3], context)
    
    if rec:
        print(f"推荐歌曲: {rec.song_info['title']}")
        print(f"推荐理由: {rec.reason}")
        print(f"置信度: {rec.confidence:.2f}")
    
    # 显示统计
    print("\n学习统计:")
    stats = adapter.get_statistics()
    print(f"  总歌曲数: {stats['total_songs']}")
    print(f"  总播放次数: {stats['total_plays']}")
    print(f"  跳过率: {stats['skip_rate']:.2%}")
    print(f"  会话跳过率: {stats['session']['skip_rate']:.2%}")
    
    # 测试正向反馈
    print("\n发送正向反馈...")
    adapter.on_positive_feedback()
    
    # 保存
    adapter.save()
    print("\n数据已保存")
