"""
播放器集成示例

这个文件展示了如何将个人推荐系统集成到你现有的音乐播放器中。
根据你的播放器架构选择合适的集成方式。
"""

import sys
import os
import time

# ============================================================
# 方式1: 完全集成 - 直接在播放器代码中使用
# ============================================================

class IntegratedPlayerExample:
    """完全集成示例 - 推荐系统作为播放器的一部分"""
    
    def __init__(self):
        # 导入推荐系统
        from adapter import PersonalRecommendationAdapter
        
        # 初始化推荐适配器
        self.recommender = PersonalRecommendationAdapter(
            data_dir="./user_data/recommender"
        )
        
        # 当前播放状态
        self.current_track = None
        self.current_start_time = None
        self.play_history = []
        
    def load_library(self, songs: list):
        """加载音乐库"""
        self.recommender.set_song_pool(songs)
        
    def play(self, track: dict):
        """播放歌曲"""
        # 如果有正在播放的歌曲，先处理它
        if self.current_track:
            self._handle_track_end(interrupted=True)
        
        # 通知推荐系统新歌开始
        self.recommender.on_song_start(track)
        
        self.current_track = track
        self.current_start_time = time.time()
        
        print(f"▶ 正在播放: {track.get('title', '未知')}")
    
    def skip(self):
        """跳过当前歌曲"""
        if not self.current_track:
            return
        
        listen_time = time.time() - self.current_start_time
        
        # 通知推荐系统
        self.recommender.on_song_skipped(self.current_track, listen_time)
        
        print(f"⏭ 跳过: {self.current_track.get('title')} (听了 {listen_time:.1f}秒)")
        
        self.play_history.append(self.current_track)
        self.current_track = None
        
        # 自动播放下一首
        self.play_next()
    
    def on_track_complete(self):
        """歌曲自然播放完成"""
        if not self.current_track:
            return
        
        listen_time = time.time() - self.current_start_time
        
        # 通知推荐系统
        self.recommender.on_song_played(
            self.current_track, 
            listen_time, 
            completed=True
        )
        
        print(f"✓ 播放完成: {self.current_track.get('title')}")
        
        self.play_history.append(self.current_track)
        self.current_track = None
        
        # 自动播放下一首
        self.play_next()
    
    def _handle_track_end(self, interrupted=False):
        """处理歌曲结束"""
        if not self.current_track:
            return
        
        listen_time = time.time() - self.current_start_time
        duration = self.current_track.get('duration', 0)
        
        # 判断是完成还是跳过
        if not interrupted and duration > 0 and listen_time >= duration * 0.9:
            self.recommender.on_song_played(self.current_track, listen_time, True)
        else:
            self.recommender.on_song_skipped(self.current_track, listen_time)
        
        self.play_history.append(self.current_track)
    
    def play_next(self):
        """播放推荐的下一首"""
        from adapter import PlayContext
        
        # 获取当前上下文
        context = PlayContext(
            time_of_day=self._get_time_of_day(),
            mood="",
            activity=""
        )
        
        # 获取推荐
        result = self.recommender.get_next_song(
            self.current_track,
            self.play_history[-50:],
            context
        )
        
        if result:
            print(f"🎵 推荐理由: {result.reason}")
            self.play(result.song_info)
        else:
            print("没有更多推荐")
    
    def thumbs_up(self):
        """用户点击喜欢 - 强化当前推荐策略"""
        self.recommender.on_positive_feedback()
        print("👍 已记录：你喜欢这样的推荐")
    
    def thumbs_down(self):
        """用户点击不喜欢 - 增加多样性"""
        self.recommender.on_negative_feedback()
        print("👎 已记录：将推荐更多不同风格的歌曲")
    
    def like_current(self):
        """收藏当前歌曲"""
        if self.current_track:
            self.recommender.on_song_liked(self.current_track, True)
            print(f"❤ 已收藏: {self.current_track.get('title')}")
    
    def show_stats(self):
        """显示学习统计"""
        stats = self.recommender.get_statistics()
        print("\n📊 学习统计:")
        print(f"  总歌曲数: {stats['total_songs']}")
        print(f"  总播放次数: {stats['total_plays']}")
        print(f"  跳过率: {stats['skip_rate']:.1%}")
        print(f"  当前模式: ", end="")
        if stats['session']['is_picky_mode']:
            print("挑剔模式 🔍")
        elif stats['session']['is_relaxed_mode']:
            print("宽松模式 😌")
        else:
            print("正常模式")
        
        if stats['top_songs']:
            print("\n  最喜欢的歌曲:")
            for s in stats['top_songs'][:3]:
                print(f"    - 偏好度 {s['score']:.0%}")
    
    def save(self):
        """保存学习数据"""
        self.recommender.save()
        print("💾 数据已保存")
    
    def _get_time_of_day(self) -> str:
        """获取当前时段"""
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"


# ============================================================
# 方式2: HTTP API集成 - 通过网络与推荐服务器通信
# ============================================================

class HTTPClientExample:
    """HTTP API客户端示例"""
    
    def __init__(self, server_url: str = "http://127.0.0.1:23331"):
        self.server_url = server_url
    
    def _post(self, endpoint: str, data: dict = None) -> dict:
        """发送POST请求"""
        import urllib.request
        import json
        
        url = f"{self.server_url}{endpoint}"
        body = json.dumps(data or {}).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=body,
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"请求失败: {e}")
            return {}
    
    def _get(self, endpoint: str) -> dict:
        """发送GET请求"""
        import urllib.request
        import json
        
        url = f"{self.server_url}{endpoint}"
        
        try:
            with urllib.request.urlopen(url) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"请求失败: {e}")
            return {}
    
    def get_next_recommendation(self, current_song: dict = None, history: list = None):
        """获取下一首推荐"""
        return self._post('/api/recommend/next', {
            'current_song': current_song,
            'history': history or [],
            'context': {}
        })
    
    def report_played(self, song: dict, duration: float, completed: bool):
        """报告歌曲播放完成"""
        return self._post('/api/feedback/played', {
            'song': song,
            'duration': duration,
            'completed': completed
        })
    
    def report_skipped(self, song: dict, position: float):
        """报告歌曲被跳过"""
        return self._post('/api/feedback/skipped', {
            'song': song,
            'position': position
        })
    
    def positive_feedback(self):
        """正向反馈"""
        return self._post('/api/feedback/positive')
    
    def negative_feedback(self):
        """负向反馈"""
        return self._post('/api/feedback/negative')
    
    def get_stats(self):
        """获取统计"""
        return self._get('/api/stats')
    
    def register_songs(self, songs: list):
        """注册歌曲池"""
        return self._post('/api/songs/register', {'songs': songs})


# ============================================================
# 方式3: 与你现有的recommendation_api.py集成
# ============================================================

def integrate_with_existing_api():
    """
    展示如何与现有的recommendation_api.py集成
    
    假设你的播放器已经使用了recommendation_api.py中的RecommendationAPIServer
    """
    
    # 导入你现有的API服务器
    # from recommendation_api import RecommendationAPIServer
    
    # 导入我们的适配器
    from adapter import PersonalRecommendationAdapter
    
    # 创建个人推荐适配器
    adapter = PersonalRecommendationAdapter(data_dir="./recommender_data")
    
    # 在你的播放器初始化代码中:
    # server = RecommendationAPIServer(port=23331)
    # server.set_provider(adapter)  # 设置为推荐提供者
    # server.start()
    
    print("集成方式:")
    print("1. 创建 PersonalRecommendationAdapter 实例")
    print("2. 调用 server.set_provider(adapter)")
    print("3. 播放器通过现有API调用推荐功能")
    print("4. 在播放器的回调中调用 adapter.on_song_start/skipped/played")
    
    return adapter


# ============================================================
# 演示
# ============================================================

def demo():
    """运行演示"""
    print("=" * 60)
    print("个人音乐推荐系统 - 集成演示")
    print("=" * 60)
    
    # 创建模拟歌曲库
    songs = [
        {'path': f'/music/pop/song{i}.mp3', 'title': f'流行歌曲{i}', 'artist': '流行歌手', 'duration': 200, 'genre': 'pop'}
        for i in range(1, 11)
    ] + [
        {'path': f'/music/rock/song{i}.mp3', 'title': f'摇滚歌曲{i}', 'artist': '摇滚乐队', 'duration': 240, 'genre': 'rock'}
        for i in range(1, 11)
    ] + [
        {'path': f'/music/jazz/song{i}.mp3', 'title': f'爵士歌曲{i}', 'artist': '爵士乐手', 'duration': 300, 'genre': 'jazz'}
        for i in range(1, 6)
    ]
    
    print(f"\n📚 加载了 {len(songs)} 首歌曲")
    
    # 创建播放器
    player = IntegratedPlayerExample()
    player.load_library(songs)
    
    print("\n🎮 模拟听歌行为...\n")
    
    # 模拟一系列播放行为
    import random
    
    # 场景1: 喜欢流行音乐
    print("--- 场景1: 你似乎喜欢流行音乐 ---")
    for song in songs[:5]:  # 播放几首流行歌曲
        player.play(song)
        time.sleep(0.05)
        if 'pop' in song['path']:
            player.on_track_complete()  # 流行歌曲听完
        else:
            player.skip()  # 其他跳过
    
    # 场景2: 跳过很多摇滚
    print("\n--- 场景2: 你跳过了很多摇滚歌曲 ---")
    for song in songs[10:15]:  # 播放摇滚歌曲
        player.play(song)
        time.sleep(0.05)
        player.skip()  # 全部跳过
    
    # 发送负向反馈
    print("\n点击了👎按钮...")
    player.thumbs_down()
    
    # 场景3: 系统调整后的推荐
    print("\n--- 场景3: 系统学习后的推荐 ---")
    for _ in range(3):
        player.play_next()
        time.sleep(0.05)
        # 假设用户喜欢新推荐
        player.on_track_complete()
    
    # 发送正向反馈
    print("\n点击了👍按钮...")
    player.thumbs_up()
    
    # 显示统计
    player.show_stats()
    
    # 保存
    player.save()
    
    print("\n✨ 演示完成!")
    print("\n要在你的播放器中使用，请参考上面的代码示例。")


if __name__ == "__main__":
    demo()
