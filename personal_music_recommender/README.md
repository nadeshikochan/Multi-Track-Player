# 个人音乐推荐系统

一个基于用户行为学习的本地音乐推荐系统，通过分析你的听歌习惯（跳过、完整播放、中途切歌等）来学习你的音乐偏好。

## 核心特性

### 1. 隐式反馈学习

系统从你的日常听歌行为中学习，无需明确打分：

| 行为 | 信号强度 | 学习效果 |
|------|---------|---------|
| 秒切（<10%） | 强负面 | 大幅降低该歌曲偏好，远离类似歌曲 |
| 中间切（10-50%） | 弱负面 | 轻微降低偏好 |
| 后期切（50-90%） | 弱正面 | 轻微提升偏好 |
| 完整播放 | 强正面 | 大幅提升偏好，强化相似歌曲关联 |

### 2. 双层偏好模型

- **宏观喜好度**：你对单首歌曲的整体偏好
- **转换喜好度**：歌曲A播完后播歌曲B的满意度

### 3. 自适应学习率

系统会根据你当前的听歌状态调整学习速度：

- **挑剔模式**：最近频繁跳过歌曲 → 增加学习率，快速远离不喜欢的风格
- **宽松模式**：大多数歌曲都听完 → 降低学习率，避免过度拟合当前偏好

### 4. 正负反馈按钮

- **👍 推荐很棒**：强化最近的推荐策略，表示"继续这样推荐"
- **👎 推荐不好**：削弱最近的策略，增加推荐多样性

## 安装

将 `personal_music_recommender` 文件夹复制到你的音乐播放器项目目录中。

## 使用方法

### 方法1：集成到播放器（推荐）

```python
import sys
sys.path.append('./personal_music_recommender')

from personal_music_recommender import PersonalRecommendationAdapter

# 创建适配器
recommender = PersonalRecommendationAdapter(data_dir="./my_music_learning")

# 设置歌曲池
recommender.set_song_pool(player.get_all_songs())

# 在播放器中注册为推荐提供者
player.set_recommendation_provider(recommender)
```

### 方法2：HTTP API服务器

```python
from personal_music_recommender import PersonalRecommendationServer

# 启动服务器
server = PersonalRecommendationServer(
    port=23331,
    data_dir="./my_music_learning"
)
server.start()
```

然后通过HTTP API与播放器通信。

### 方法3：直接使用

```python
from personal_music_recommender import PersonalMusicRecommender

recommender = PersonalMusicRecommender(data_dir="./my_music_learning")

# 注册歌曲
recommender.register_song_pool(songs)

# 报告播放行为
recommender.on_song_start(song_info)
recommender.on_song_end(song_info, listen_time=120, action='complete')

# 获取推荐
song_info, reason = recommender.get_next_recommendation(current_song)
print(f"推荐: {song_info['title']}, 原因: {reason}")
```

## API 端点

### 推荐相关

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/recommend/next` | POST | 获取下一首推荐歌曲 |
| `/api/recommend/playlist` | POST | 生成推荐播放列表 |

### 反馈相关

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/feedback/played` | POST | 报告歌曲播放完成 |
| `/api/feedback/skipped` | POST | 报告歌曲被跳过 |
| `/api/feedback/liked` | POST | 报告收藏/取消收藏 |
| `/api/feedback/positive` | POST | 正向反馈按钮 |
| `/api/feedback/negative` | POST | 负向反馈按钮 |

### 数据管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/stats` | GET | 获取学习统计 |
| `/api/songs` | GET | 获取所有歌曲学习数据 |
| `/api/session/reset` | POST | 重置会话 |
| `/api/data/save` | POST | 保存学习数据 |
| `/api/data/export` | POST | 导出模型 |
| `/api/data/import` | POST | 导入模型 |

## API 示例

### 获取推荐

```bash
curl -X POST http://localhost:23331/api/recommend/next \
  -H "Content-Type: application/json" \
  -d '{
    "current_song": {"path": "/music/song1.mp3", "title": "当前歌曲"},
    "history": [],
    "context": {"mood": "calm", "time_of_day": "evening"}
  }'
```

响应：
```json
{
  "song_info": {"path": "/music/song5.mp3", "title": "推荐歌曲"},
  "reason": "风格连贯；你之前很喜欢这首歌",
  "confidence": 0.75,
  "source": "personal_learning"
}
```

### 报告跳过

```bash
curl -X POST http://localhost:23331/api/feedback/skipped \
  -H "Content-Type: application/json" \
  -d '{
    "song": {"path": "/music/song3.mp3"},
    "position": 15.5
  }'
```

### 正向反馈

```bash
curl -X POST http://localhost:23331/api/feedback/positive
```

### 获取统计

```bash
curl http://localhost:23331/api/stats
```

响应：
```json
{
  "total_songs": 150,
  "total_plays": 500,
  "skip_rate": 0.23,
  "session": {
    "songs_played": 15,
    "skip_rate": 0.2,
    "is_picky_mode": false,
    "consecutive_good": 3
  },
  "top_songs": [
    {"path": "/music/favorite.mp3", "score": 0.92, "confidence": 0.85}
  ]
}
```

## 与播放器集成

在你的 `recommendation_api.py` 所在的播放器项目中，修改初始化代码：

```python
# player.py 或 main.py

from personal_music_recommender import PersonalRecommendationAdapter

class MusicPlayer:
    def __init__(self):
        # ... 其他初始化 ...
        
        # 初始化个人推荐系统
        self.recommender = PersonalRecommendationAdapter(
            data_dir="./user_data/recommender"
        )
        
        # 设置歌曲池
        self.recommender.set_song_pool(self.library.get_all_songs())
    
    def on_track_start(self, track):
        """歌曲开始播放时调用"""
        self.recommender.on_song_start(track.to_dict())
    
    def on_track_end(self, track, position, completed):
        """歌曲结束时调用"""
        if completed:
            self.recommender.on_song_played(track.to_dict(), position, True)
        else:
            self.recommender.on_song_skipped(track.to_dict(), position)
    
    def get_next_recommendation(self):
        """获取下一首推荐"""
        result = self.recommender.get_next_song(
            self.current_track.to_dict() if self.current_track else None,
            [t.to_dict() for t in self.play_history[-50:]],
            self._get_context()
        )
        return result
    
    def on_thumbs_up(self):
        """用户点击喜欢按钮"""
        self.recommender.on_positive_feedback()
    
    def on_thumbs_down(self):
        """用户点击不喜欢按钮"""
        self.recommender.on_negative_feedback()
```

## 数据存储

学习数据存储在指定的 `data_dir` 目录中：

```
data_dir/
├── songs.json      # 歌曲特征和偏好数据
├── transitions.json # 歌曲转换关系数据
└── history.json    # 播放历史记录
```

## 算法说明

### 偏好分数计算

综合考虑以下因素：

1. **基础偏好** (40%): 历史播放反馈累积的偏好分数
2. **转换偏好** (30%): 与当前歌曲的接续合适度
3. **嵌入相似度** (15%): 基于学习的歌曲嵌入向量相似度
4. **多样性** (-): 避免重复最近播放的歌曲
5. **时间衰减**: 避免总是推荐同一首歌

### Epsilon-Greedy 探索

默认 15% 的概率进行探索，随机选择低置信度（不确定性高）的歌曲，帮助发现新的偏好。

### 嵌入学习

每首歌曲维护一个 32 维嵌入向量。当用户对歌曲转换给出正/负反馈时，系统会调整向量使得：
- 正反馈：拉近两首歌的嵌入距离
- 负反馈：推远两首歌的嵌入距离

## 最佳实践

1. **初期使用**：前 50-100 次播放是学习期，推荐质量会逐渐提升
2. **定期保存**：系统每 10 次播放自动保存，也可以手动调用 save
3. **使用反馈按钮**：当推荐连续很好或很差时，使用反馈按钮加速学习
4. **重置会话**：长时间不听后重新开始，可以重置会话状态

## 文件结构

```
personal_music_recommender/
├── __init__.py              # 包入口和导出
├── personal_recommender.py  # 核心推荐算法
├── adapter.py               # RecommendationProvider适配器
├── server.py                # HTTP API服务器
└── README.md                # 本文档
```

## License

MIT License
