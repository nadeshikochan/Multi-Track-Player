"""
个人音乐推荐系统 - 集成模块

这个模块提供了与现有音乐播放器集成的简单接口。

使用方法:
--------

方法1: 作为RecommendationProvider使用
```python
from personal_music_recommender import PersonalRecommendationAdapter

# 创建适配器
recommender = PersonalRecommendationAdapter(data_dir="./my_learning_data")

# 在播放器中注册
player.set_recommendation_provider(recommender)

# 设置歌曲池（可选，也会自动从播放历史中学习）
recommender.set_song_pool(player.get_all_songs())
```

方法2: 作为独立HTTP服务器
```python
from personal_music_recommender import PersonalRecommendationServer

# 创建并启动服务器
server = PersonalRecommendationServer(port=23331, data_dir="./my_learning_data")
server.set_song_pool(songs)  # 设置歌曲池
server.start()

# 服务器会监听以下端点:
# POST /api/recommend/next - 获取下一首推荐
# POST /api/feedback/played - 报告歌曲播放完成
# POST /api/feedback/skipped - 报告歌曲被跳过
# POST /api/feedback/positive - 正向反馈
# POST /api/feedback/negative - 负向反馈
# GET /api/stats - 获取学习统计
```

方法3: 直接使用核心推荐器
```python
from personal_music_recommender import PersonalMusicRecommender

# 创建推荐器
recommender = PersonalMusicRecommender(data_dir="./my_learning_data")

# 注册歌曲
recommender.register_song_pool(songs)

# 报告播放行为
recommender.on_song_start(song_info)
recommender.on_song_end(song_info, listen_time=120, action='complete')  # 或 'skip'

# 获取推荐
song_info, reason = recommender.get_next_recommendation(current_song)
```

核心特性:
--------
1. 基于隐式反馈学习：跳过、播放完成、中途切歌
2. 双层偏好模型：单首歌偏好 + 歌曲转换偏好
3. 自适应学习率：挑剔模式/宽松模式
4. 嵌入空间学习：相似歌曲聚类
5. 正负反馈按钮支持
6. 数据持久化
"""

# 导出所有公共接口
from personal_recommender import (
    PersonalMusicRecommender,
    SongFeatures,
    ListeningEvent,
    TransitionPair,
    SessionState
)

from adapter import (
    PersonalRecommendationAdapter,
    create_recommendation_server
)

from server import (
    PersonalRecommendationServer,
    ExtendedAPIHandler
)

__version__ = "1.0.0"
__author__ = "Personal Music Recommender"

__all__ = [
    # 核心类
    'PersonalMusicRecommender',
    'SongFeatures',
    'ListeningEvent',
    'TransitionPair',
    'SessionState',
    
    # 适配器
    'PersonalRecommendationAdapter',
    'create_recommendation_server',
    
    # 服务器
    'PersonalRecommendationServer',
    'ExtendedAPIHandler',
]


def quick_start(data_dir: str = "./recommender_data", port: int = 23331):
    """
    快速启动推荐服务器
    
    Args:
        data_dir: 数据存储目录
        port: HTTP服务器端口
        
    Returns:
        PersonalRecommendationServer实例
    """
    server = PersonalRecommendationServer(port=port, data_dir=data_dir)
    server.start()
    return server


if __name__ == "__main__":
    # 运行测试
    print("个人音乐推荐系统 v" + __version__)
    print("=" * 50)
    
    # 测试核心功能
    print("\n测试核心推荐器...")
    recommender = PersonalMusicRecommender("./test_recommender_data")
    
    # 模拟歌曲
    test_songs = [
        {'path': f'/test/song{i}.mp3', 'title': f'测试歌曲{i}', 'artist': f'艺术家{i%3}', 'duration': 180 + i*10}
        for i in range(10)
    ]
    
    recommender.register_song_pool(test_songs)
    print(f"注册了 {len(test_songs)} 首测试歌曲")
    
    # 模拟一些播放行为
    import random
    
    for i in range(20):
        song = random.choice(test_songs)
        recommender.on_song_start(song)
        
        # 随机决定播放结果
        r = random.random()
        if r < 0.3:
            # 早期跳过
            recommender.on_song_end(song, listen_time=random.uniform(5, 18), action='skip')
        elif r < 0.5:
            # 中间跳过
            recommender.on_song_end(song, listen_time=random.uniform(30, 90), action='skip')
        else:
            # 完整播放
            recommender.on_song_end(song, listen_time=song['duration'], action='complete')
    
    print("模拟了 20 次播放行为")
    
    # 获取推荐
    print("\n获取推荐:")
    for _ in range(3):
        result = recommender.get_next_recommendation(test_songs[0])
        if result:
            song_info, reason = result
            print(f"  - {song_info['title']}: {reason}")
    
    # 显示统计
    stats = recommender.get_statistics()
    print(f"\n学习统计:")
    print(f"  总播放次数: {stats['total_plays']}")
    print(f"  跳过率: {stats['skip_rate']:.1%}")
    print(f"  会话模式: {'挑剔' if stats['session']['is_picky_mode'] else '宽松' if stats['session']['is_relaxed_mode'] else '正常'}")
    
    if stats['top_songs']:
        print(f"\n偏好最高的歌曲:")
        for s in stats['top_songs'][:3]:
            print(f"  - {s['path']}: {s['score']:.2f} (置信度: {s['confidence']:.2f})")
    
    print("\n测试完成!")
