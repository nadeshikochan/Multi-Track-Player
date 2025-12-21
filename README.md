# Multi-Track Audio Player v3.0

高性能多音轨音乐播放器，支持MSST音轨分离、歌词显示、封面显示、歌曲推荐系统接口和落雪音乐在线播放。

## ✨ 新特性 (v3.0)

- **双页面UI**: 音轨控制页 + 精美歌词页面，一键切换
- **可折叠歌曲列表**: 点击可折叠/展开歌曲列表
- **速度滑动条**: 使用滑动条实现0.25x-2.0x变速播放
- **歌曲推荐系统接口**: 提供HTTP API供外部推荐系统对接
- **落雪音乐在线播放**: 支持接入lx-music-api-server播放在线歌曲
- **精美歌词显示**: 逐句滚动高亮显示歌词和翻译

## 📦 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 🎵 基本功能

- 扫描本地音乐文件夹
- 读取嵌入式/外部歌词和封面
- 多种播放模式(顺序/随机/单曲循环)
- 变速播放 (0.25x - 2.0x)
- 快进快退 (5秒)
- 键盘快捷键控制

## 🎚️ MSST音轨分离

本播放器支持使用MSST(Music Source Separation Training)进行音轨分离。

### 配置步骤

1. 下载并安装 [MSST-WebUI](https://github.com/SUC-DriverOld/MSST-WebUI)
2. 在MSST目录下安装依赖: `pip install -r requirements.txt`
3. 确保安装了librosa: `pip install librosa`
4. 在播放器中点击"MSST设置"，配置:
   - MSST WebUI安装路径
   - 分离音轨保存路径
   - 模型类型(推荐bs_roformer)
   - 模型配置文件(.yaml)
   - 模型权重文件(.ckpt)

### 常见问题

**Q: 提示"无法导入MSST模块: No module named 'librosa'"**

A: 请在MSST目录下运行:
```bash
pip install librosa
pip install -r requirements.txt
```

**Q: 分离失败**

A: 
1. 确保MSST路径设置正确(指向MSST-WebUI根目录)
2. 确保配置文件和模型文件路径正确
3. 首次运行会自动下载模型，请确保网络通畅

---

## 🎯 歌曲推荐系统接口

播放器提供HTTP API接口，供外部歌曲推荐系统对接。

### 启用API服务

API服务默认启用，端口23331。可在设置中修改。

### API接口说明

#### 获取播放器状态

```
GET http://127.0.0.1:23331/api/player/status
```

响应:
```json
{
    "playing": true,
    "current_song": {
        "title": "歌曲名",
        "artist": "歌手",
        "path": "/path/to/song.mp3"
    },
    "progress": 120.5,
    "duration": 240.0
}
```

#### 获取下一首推荐

```
POST http://127.0.0.1:23331/api/recommend/next
Content-Type: application/json

{
    "current_song": {"title": "...", "artist": "...", "path": "..."},
    "history": [...],
    "context": {
        "time_of_day": "evening",
        "mood": "calm"
    }
}
```

响应:
```json
{
    "song_info": {"title": "...", "artist": "...", "path": "..."},
    "reason": "推荐理由",
    "confidence": 0.95
}
```

#### 生成推荐播放列表

```
POST http://127.0.0.1:23331/api/recommend/playlist
Content-Type: application/json

{
    "seed_songs": [...],
    "count": 10,
    "context": {}
}
```

#### 控制播放器

```
POST http://127.0.0.1:23331/api/player/play
Content-Type: application/json

{"song": {"path": "/path/to/song.mp3"}}
```

```
POST http://127.0.0.1:23331/api/player/next
```

#### 反馈接口

```
POST http://127.0.0.1:23331/api/feedback/played
Content-Type: application/json

{
    "song": {...},
    "duration": 180.5,
    "completed": true
}
```

```
POST http://127.0.0.1:23331/api/feedback/skipped
Content-Type: application/json

{
    "song": {...},
    "position": 30.0
}
```

### 自定义推荐提供者

```python
from core.recommendation_api import RecommendationProvider, SongRecommendation

class MyRecommender(RecommendationProvider):
    def get_next_song(self, current_song, history, context):
        # 你的推荐逻辑
        return SongRecommendation(
            song_info={"path": "...", "title": "...", "artist": "..."},
            reason="基于听歌历史推荐"
        )
        
    def get_playlist(self, seed_songs, count, context):
        # 生成播放列表逻辑
        return [...]
```

---

## 🌐 落雪音乐在线播放接口

支持接入lx-music-api-server实现在线歌曲搜索和播放。

### 部署API服务器

1. 克隆仓库:
```bash
git clone https://github.com/MeoProject/lx-music-api-server.git
cd lx-music-api-server
```

2. 安装依赖(推荐使用uv):
```bash
# 使用 pip
pip install -r requirements.txt

# 或使用 uv
uv sync
```

3. 启动服务器:
```bash
python main.py
# 或
uv run main.py
```

默认端口: 9763

### 配置播放器

1. 打开设置 -> API设置
2. 在"落雪音乐API服务器"中填入API地址，如: `http://127.0.0.1:9763`
3. 点击"测试连接"验证

### 使用在线搜索

1. 点击顶部的"🌐 在线搜索"按钮
2. 输入歌曲名或歌手名
3. 选择音源(酷我/酷狗/QQ音乐/网易云/咪咕)
4. 双击搜索结果播放

### 支持的音源

| 代码 | 名称 | 说明 |
|------|------|------|
| kw | 酷我音乐 | 推荐 |
| kg | 酷狗音乐 | - |
| tx | QQ音乐 | - |
| wy | 网易云音乐 | - |
| mg | 咪咕音乐 | - |

### 注意事项

- API服务器需要自行部署和维护
- 部分音源可能需要登录才能获取高音质
- 请遵守相关服务条款和法律法规

---

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| Space | 播放/暂停 |
| ← | 快退5秒 |
| → | 快进5秒 |
| ↑ | 上一首 |
| ↓ | 下一首 |
| Ctrl+F | 聚焦搜索框 |
| Ctrl+L | 切换到歌词页面 |
| Ctrl+T | 切换到音轨控制页面 |
| Esc | 清除搜索 |

---

## 📁 项目结构

```
multi_track_player_v3/
├── main.py                 # 程序入口
├── requirements.txt        # 依赖列表
├── README.md              # 说明文档
├── core/                  # 核心模块
│   ├── __init__.py
│   ├── models.py          # 数据模型
│   ├── msst.py            # MSST分离
│   ├── recommendation_api.py  # 推荐API
│   └── lxmusic_api.py     # 落雪音乐API
└── ui/                    # UI模块
    ├── __init__.py
    ├── main_window.py     # 主窗口
    ├── track_control.py   # 音轨控制
    ├── lyrics_page.py     # 歌词页面
    └── dialogs.py         # 设置对话框
```

---

## 🔧 技术栈

- Python 3.10+
- PyQt6 - GUI框架
- mutagen - 音频元数据读取
- Qt Multimedia - 音频播放

---

## 📝 许可证

MIT License
