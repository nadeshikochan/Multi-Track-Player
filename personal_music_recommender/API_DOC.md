# 音乐推荐 API 使用说明

## 服务启动
- 运行 `run_api.bat`（默认端口 8000，单 worker）。
- 如需自定义端口：编辑 `run_api.bat` 中的 `--port`，或手动执行  
  `python -m uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1`.
- API 默认使用本地索引文件 `music_index.pt` 和配置文件 `config.json`。

## 基础信息
- Base URL：`http://127.0.0.1:8000`（按需替换端口/主机）。
- 请求/响应格式：`application/json`。
- 鉴权：无（本地测试）。对外部署请自行添加鉴权/网关。

## 端点一览
| 方法 | 路径        | 说明                                   |
| ---- | ----------- | -------------------------------------- |
| GET  | /health     | 健康检查                               |
| GET  | /config     | 获取当前配置                           |
| POST | /config     | 更新配置（支持部分字段覆盖）           |
| POST | /index      | 扫描目录，构建/增量索引，保存 .pt      |
| GET  | /tracks     | 返回已索引歌曲路径列表                 |
| POST | /recommend  | 给定歌曲路径，返回推荐列表             |

## 配置结构（config.json）
```json
{
  "similarity": {"like_min": 0.85, "like_max": 1.0},
  "dislike": {"min_sim": 0.2, "max_sim": 0.6},
  "history": {"allow_duplicates": false, "history_size": 50},
  "mmr": {"lambda": 0.7, "prelim_k_min": 20, "prelim_k_multiplier": 4}
}
```
- similarity/dislike：喜欢/不喜欢的相似度区间，用于过滤推荐。
- history：是否允许重复、历史去重长度。
- mmr：多样性重排参数（lambda 越大越偏相似度，越小越偏多样）。

## 端点详情与示例

### 1) GET /health
健康检查。
```
→ 200 {"ok": true}
```

### 2) GET /config
获取当前配置。
```
→ 200 { ...同上配置结构... }
```

### 3) POST /config
更新配置，传入字段会深度合并，未提供的保持不变。
请求：
```json
{
  "audio_dir": "C:\\Users\\lenovo\\Desktop\\歌曲temp",
  "similarity": {"like_min": 0.9, "like_max": 1.0},
  "history": {"allow_duplicates": false, "history_size": 50}
}
```
响应：
```
→ 200 {"ok": true, "config": { ...合并后的完整配置... }}
```

### 4) POST /index
扫描目录并构建/增量索引，保存为 `music_index.pt`。
请求：
```json
{
  "folder": "C:\\Users\\lenovo\\Desktop\\歌曲temp",  // 可选，缺省用 config 中的 audio_dir
  "overwrite": false                               // false=增量补算；true=全量重建
}
```
响应：
```
→ 200 {"ok": true, "count": 123}
```

### 5) GET /tracks
返回已索引的歌曲路径列表。
```
→ 200 {"tracks": ["C:\\Users\\lenovo\\Desktop\\歌曲temp\\foo.mp3", ...]}
```

### 6) POST /recommend
给定歌曲路径，返回推荐列表；可临时覆盖部分配置。
请求：
```json
{
  "track_path": "C:\\Users\\lenovo\\Desktop\\歌曲temp\\foo.mp3",  // 必填，绝对路径
  "top_k": 50,                                                    // 可选，默认 20，超出可用数量则返回实际可用数量
  "params": {                                                     // 可选，临时覆盖配置
    "similarity": {"like_min": 0.9, "like_max": 1.0},
    "dislike": {"min_sim": 0.3, "max_sim": 0.6},
    "history": {"allow_duplicates": false, "history_size": 50},
    "mmr": {"lambda": 0.7}
  },
  "history": [                                                    // 可选，最近播放列表，用于去重
    "C:\\\\Users\\\\lenovo\\\\Desktop\\\\歌曲temp\\\\played1.mp3",
    "C:\\\\Users\\\\lenovo\\\\Desktop\\\\歌曲temp\\\\played2.mp3"
  ],
  "dislike_random_k": 500                                         // 可选，不喜欢时跳过前 k 名，从后面随机一首（默认 500）
}
```
响应：
```json
{
  "results": [
    {"path": "C:\\Users\\lenovo\\Desktop\\歌曲temp\\bar.mp3", "sim": 0.98, "sim_secondary": 0.98},
    ...
  ],
  "top_k": 50
}
```

## 注意事项
- `track_path` 必须存在于本地；若索引中没有该歌，会现场计算 embedding 并写回索引。
- 默认仅取每首歌前 2 分钟做向量，控制显存/时间。
- 索引文件 `music_index.pt` 默认增量更新；需全量重建时 `/index` 传 `overwrite=true`。
- 推荐的 `top_k` 越大计算量越高，可按需调整。
- 如果喜欢/不喜欢的相似度区间过滤后没有结果：客户端会为“喜欢”兜底返回全局最相似的一首；“不喜欢”兜底返回从不喜欢上限向上最近的一首（若无则取全局首个）。
- 服务端会用 `history` 和 `allow_duplicates` 做去重；若去重后为空，会从可用候选中兜底至少返回 1 条，避免返回自身或空列表。
- 不喜欢推荐：可传 `dislike_random_k`，会跳过前 k 名（更相似的部分），从后面的候选中随机返回 1 条。
- UI（`run_webui.bat`）是通过这些 API 调用的外部示例客户端。

## 常用 curl 示例（PowerShell）
```powershell
curl http://127.0.0.1:8000/health

curl http://127.0.0.1:8000/config

curl -X POST http://127.0.0.1:8000/config ^
  -H "Content-Type: application/json" ^
  -d "{\"similarity\":{\"like_min\":0.9,\"like_max\":1.0}}"

curl -X POST http://127.0.0.1:8000/index ^
  -H "Content-Type: application/json" ^
  -d "{\"folder\":\"C:\\\\Users\\\\lenovo\\\\Desktop\\\\歌曲temp\",\"overwrite\":false}"

curl -X POST http://127.0.0.1:8000/recommend ^
  -H "Content-Type: application/json" ^
  -d "{\"track_path\":\"C:\\\\Users\\\\lenovo\\\\Desktop\\\\歌曲temp\\\\foo.mp3\",\"top_k\":50}"
```
